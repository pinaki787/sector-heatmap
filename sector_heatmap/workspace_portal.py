"""Authenticated localhost setup portal for separate users and broker accounts."""
import argparse
import getpass
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse
from .workspaces import COOKIE, WorkspaceRuntime, WorkspaceStore, cookie_token

ROOT=Path(__file__).resolve().parents[1]


def handler_factory(store,runtime,port):
    class Handler(BaseHTTPRequestHandler):
        def response(self,status,payload,content_type='application/json',cookie=None):
            data=json.dumps(payload).encode() if content_type=='application/json' else payload
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if cookie:self.send_header('Set-Cookie',cookie)
            self.end_headers();self.wfile.write(data)

        def trusted_host(self):
            return self.headers.get('Host')==f'127.0.0.1:{port}'

        def do_GET(self):
            if not self.trusted_host():
                self.response(403,{'error':'Use the displayed 127.0.0.1 portal address.'});return
            path=urlparse(self.path).path
            files={'/':'workspace-portal.html','/workspace-portal.js':'workspace-portal.js','/workspace-portal.css':'workspace-portal.css'}
            if path in files:
                name=files[path];mime='text/html' if name.endswith('.html') else 'text/javascript' if name.endswith('.js') else 'text/css'
                self.response(200,(ROOT/name).read_bytes(),mime);return
            try:
                user=store.session(cookie_token(self.headers))
                if path=='/api/workspaces/me':
                    self.response(200,user);return
                if path=='/api/workspaces/accounts':
                    rows=store.accounts(user)
                    for a in rows:
                        a.update(running=runtime.running(a['id']),configured=(store.folder(a)/'credentials.json').exists(),url=f"http://127.0.0.1:{a['port']}/")
                    for a in rows:
                        if a['running']:
                            owner=store.folder(a)/'dashboard-owner.lock'
                            try:a['dashboard_pid']=json.loads(owner.read_text())['pid']
                            except (OSError,ValueError,KeyError):pass
                    self.response(200,{'accounts':rows});return
                self.response(404,{'error':'Unknown setup endpoint.'})
            except PermissionError as e:self.response(401,{'error':str(e)})

        def do_POST(self):
            if not self.trusted_host() or self.headers.get('Origin')!=f'http://127.0.0.1:{port}':
                self.response(403,{'error':'Setup requires a same-origin request.'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Invalid request size.')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                    raise ValueError('Send JSON.')
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict):raise ValueError('Send an object.')
                path=urlparse(self.path).path
                if path=='/api/workspaces/login':
                    token,user=store.login(payload.get('username',''),payload.get('password',''))
                    self.response(200,user,cookie=f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800');return
                token=cookie_token(self.headers);user=store.session(token)
                if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),user['csrf']):
                    raise PermissionError('Refresh the setup page before saving.')
                if path=='/api/workspaces/logout':
                    store.logout(token)
                    self.response(200,{'signed_out':True},cookie=f'{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0');return
                if path=='/api/workspaces/password':
                    store.change_password(user,payload.get('current_password'),payload.get('new_password'))
                    self.response(200,{'signed_out':True},cookie=f'{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0');return
                if path=='/api/workspaces/users':
                    self.response(201,store.create_user(payload.get('username',''),payload.get('password',''),actor=user));return
                if path=='/api/workspaces/accounts':
                    a=store.create_account(user,payload.get('broker'),payload.get('label',''),payload.get('account_ref',''))
                    self.response(201,{k:v for k,v in a.items() if k not in ('credential_identity','user_id')});return
                if path=='/api/workspaces/configure':
                    a=runtime.configure(user,payload.get('account_id'),payload.get('credentials',{}),payload.get('live_enabled',False))
                    self.response(200,{'id':a['id'],'configured':True,'live_enabled':bool(a['live_enabled'])});return
                if path=='/api/workspaces/open':
                    self.response(200,runtime.start(user,payload.get('account_id')));return
                self.response(404,{'error':'Unknown setup endpoint.'})
            except PermissionError as e:self.response(403,{'error':str(e)})
            except (ValueError,TypeError,KeyError) as e:self.response(400,{'error':str(e)})
            except Exception as error:
                print('Workspace operation failed:',type(error).__name__,flush=True)
                self.response(500,{'error':'Workspace operation failed. Review the local portal log.'})

        def log_message(self,*args):pass
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8079)
    parser.add_argument('--registry',type=Path,default=ROOT/'.private/workspaces/registry.sqlite3')
    parser.add_argument('--bootstrap-admin',metavar='USERNAME')
    args=parser.parse_args()
    if not 1024<=args.port<=65535 or 8100<=args.port<=8999:
        parser.error('Choose a portal port outside workspace range 8100–8999.')
    store=WorkspaceStore(args.registry)
    if args.bootstrap_admin:
        password=getpass.getpass('New administrator password (12+ characters): ')
        if password!=getpass.getpass('Repeat password: '):parser.error('Passwords differ.')
        store.create_user(args.bootstrap_admin,password,bootstrap=True)
        print('Administrator created. Run this command without --bootstrap-admin to open setup.')
        return
    with store.db() as db:
        if not db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            parser.error('Create an administrator first with --bootstrap-admin USERNAME.')
    runtime=WorkspaceRuntime(store,ROOT,args.port)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_factory(store,runtime,args.port))
    print(f'Sector Pulse user and broker setup: http://127.0.0.1:{args.port}')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
