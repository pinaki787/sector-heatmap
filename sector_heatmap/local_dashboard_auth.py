"""Owner sign-in for an existing dashboard; never changes broker or runner state."""
from http.cookies import SimpleCookie
import json
from pathlib import Path
from urllib.parse import quote
from .workspaces import WorkspaceStore, WorkspaceRuntime, COOKIE, cookie_token

PUBLIC = {'/auth/login', '/dashboard-login.js', '/workspace-portal.css',
          '/sector-pulse-background.css', '/workspace-portal.js', '/assets/currency-motifs.svg', '/assets/bull-bear-algo.png'}

class LocalDashboardAuth:
    def __init__(self, root, port, store=None):
        self.root, self.port = Path(root), int(port)
        self.store = store or WorkspaceStore(self.root / '.private/dashboard-login/registry.sqlite3')

    @classmethod
    def configured(cls, root, port):
        return cls(root, port) if (Path(root)/'.private/dashboard-auth-enabled.json').exists() else None

    def token(self, headers):
        return cookie_token(headers)

    def portal(self, handler, mutation=False):
        path=handler.path.split('?',1)[0]
        if path not in {'/accounts','/user-master'} and not path.startswith('/api/workspaces/'):
            return False
        if not mutation and path == '/user-master':
            try:
                user=self.authorize(handler.headers)
                self.store.users(user)
            except PermissionError as e:
                self.json(handler,403,{'error':str(e)});return True
        if not hasattr(self,'portal_handler'):
            from .workspace_portal import handler_factory
            self.runtime=WorkspaceRuntime(self.store,self.root,self.port)
            self.portal_handler=handler_factory(self.store,self.runtime,self.port)
        proxy=object.__new__(self.portal_handler);proxy.__dict__.update(handler.__dict__)
        if path in {'/accounts','/user-master'}:proxy.path='/'
        (proxy.do_POST if mutation else proxy.do_GET)()
        return True

    def local(self, headers, mutation=False):
        host=headers.get('Host', '')
        if host not in {f'127.0.0.1:{self.port}', f'localhost:{self.port}'}:
            raise PermissionError('Use the local dashboard address.')
        if mutation and headers.get('Origin') != 'http://'+host:
            raise PermissionError('Dashboard actions require the same origin.')

    def authorize(self, headers, mutation=False):
        self.local(headers, mutation); return self.store.session(self.token(headers))

    def setup_required(self):
        with self.store.db() as db:return db.execute('SELECT count(*) FROM users').fetchone()[0] == 0

    def json(self, handler, code, value, token=None):
        body=json.dumps(value).encode();handler.send_response(code)
        handler.send_header('Content-Type','application/json');handler.send_header('Cache-Control','no-store')
        if token is not None:
            age=28800 if token else 0
            handler.send_header('Set-Cookie','sector_pulse_local_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0')
            handler.send_header('Set-Cookie',f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}')
        handler.send_header('Content-Length',str(len(body)));handler.end_headers();handler.wfile.write(body)

    def get(self, handler):
        path=handler.path.split('?',1)[0]
        if path != '/api/dashboard-auth/status':return False
        try:
            self.local(handler.headers)
            try:user=self.authorize(handler.headers)
            except PermissionError:user=None
            self.json(handler,200,{'authenticated':bool(user),'setup_required':self.setup_required(),'username':user['username'] if user else None,'admin':bool(user and user['admin'])})
        except PermissionError as e:self.json(handler,403,{'error':str(e)})
        return True

    def post(self, handler):
        path=handler.path.split('?',1)[0]
        if path not in {'/api/dashboard-auth/login','/api/dashboard-auth/setup','/api/dashboard-auth/logout'}:return False
        try:
            self.local(handler.headers,True);payload=handler.read_json()
            if path.endswith('/logout'):
                self.authorize(handler.headers,True);self.store.logout(self.token(handler.headers));self.json(handler,200,{'signed_out':True},'');return True
            if path.endswith('/setup'):
                if not self.setup_required():raise PermissionError('Dashboard owner is already configured. Sign in.')
                self.store.create_user(payload.get('username',''),payload.get('password',''),bootstrap=True)
            token,user=self.store.login(payload.get('username',''),payload.get('password',''))
            self.json(handler,200,{'authenticated':True,'username':user['username']},token)
        except (ValueError,PermissionError) as e:self.json(handler,403,{'error':str(e)})
        return True

    def check(self, handler, mutation=False):
        path=handler.path.split('?',1)[0]
        if not mutation and path in PUBLIC:
            try:self.local(handler.headers);return True
            except PermissionError:pass
        try:
            user=self.authorize(handler.headers,mutation)
            if not user['admin']:
                if not mutation and path in {'/','/index.html','/workspace-entry'}:
                    handler.send_response(303);handler.send_header('Location','/accounts');handler.send_header('Content-Length','0');handler.end_headers();return False
                self.json(handler,403,{'error':'Open your own broker account workspace.'});return False
            return True
        except PermissionError:
            if not mutation and path in {'/','/index.html','/workspace-entry'}:
                handler.send_response(303);handler.send_header('Location','/auth/login?next='+quote(handler.path,safe=''));handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length','0');handler.end_headers()
            else:self.json(handler,401,{'error':'Sign in to Sector Pulse.'})
            return False
