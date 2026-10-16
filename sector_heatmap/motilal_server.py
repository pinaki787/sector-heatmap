"""Loopback-only, account-owned Motilal dashboard and native order route."""
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from .motilal_api import MotilalError
from .motilal_service import Service
from .workspace_guard import WorkspaceGuard
from .workspaces import cookie_token

ROOT=Path(__file__).resolve().parents[1]


def handler_factory(guard,service):
    from .motilal_login import SavedLogin
    saved_login=None
    def login():
        nonlocal saved_login
        if saved_login is None:saved_login=SavedLogin(service)
        return saved_login
    class Handler(BaseHTTPRequestHandler):
        def send_json(self,status,value):self.response(status,json.dumps(value,allow_nan=False).encode(),'application/json')
        def response(self,status,data,mime='text/html'):
            self.send_response(status)
            for key,value in {'Content-Type':mime,'Content-Length':str(len(data)),'Cache-Control':'no-store',
                'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
                'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'"}.items():self.send_header(key,value)
            self.end_headers();self.wfile.write(data)
        def identity(self,mutation=False):
            user,account=guard.authorize(self.headers,mutation)
            if account['broker']!='MOTILAL_OSWAL':raise PermissionError('This server serves only its registered Motilal account.')
            path=urlparse(self.path).path
            if path.startswith('/api/motilal/'):
                if not user.get('admin') and 'broker' not in user.get('features',[]):raise PermissionError('Broker connection is not assigned to your user.')
                if not guard.store.sidebar_visibility().get('broker',True):raise PermissionError('Broker connection is hidden in dashboard visibility settings.')
            if mutation:
                if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),user['csrf']):raise PermissionError('Refresh the dashboard before this action.')
                guard.validate_action(account,path,{'broker':'MOTILAL_OSWAL'})
            return user,account
        def do_GET(self):
            try:
                user,account=self.identity();path=urlparse(self.path).path
                if path in {'/','/index.html','/workspace-entry'}:self.response(200,(ROOT/'motilal-oswal.html').read_bytes());return
                files={'/motilal-oswal.js':('motilal-oswal.js','text/javascript'),'/workspace-portal.css':('workspace-portal.css','text/css')}
                if path in files:
                    name,mime=files[path];self.response(200,(ROOT/name).read_bytes(),mime);return
                if path=='/api/workspace-context':
                    self.send_json(200,{**guard.context(user,account),'csrf':user['csrf'],'visible':guard.store.sidebar_visibility().get('broker',True),
                        'permitted':bool(user.get('admin') or 'broker' in user.get('features',[]))});return
                if path=='/api/motilal/saved-login':self.send_json(200,login().status(user,cookie_token(self.headers)));return
                if path=='/api/motilal/status':self.send_json(200,service.status());return
                if path not in {'/api/motilal/status'}:
                    self.send_json(404,dict(error='Use the existing dashboard workflows for trading and analysis. This page serves broker connection details only.'));return
                self.send_json(404,dict(error='Unknown Motilal endpoint.'))
            except Exception as error:self.failure(error)
        def do_POST(self):
            try:
                user,account=self.identity(True)
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384 or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Send a bounded JSON request.')
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict):raise ValueError('Send an object.')
                path=urlparse(self.path).path
                if path=='/api/motilal/disconnect-session':self.send_json(200,login().disconnect_rechallenge(user,cookie_token(self.headers)));return
                if path=='/api/motilal/saved-login':self.send_json(200,login().save(payload));return
                if path=='/api/motilal/saved-login-forget':self.send_json(200,login().forget());return
                if path=='/api/motilal/saved-login-start':self.send_json(200,login().start(user,cookie_token(self.headers),require_otp=payload.get('require_otp') is True));return
                if path=='/api/motilal/saved-login-resend':self.send_json(200,login().resend(user,cookie_token(self.headers)));return
                if path=='/api/motilal/saved-login-verify':self.send_json(200,login().verify(user,cookie_token(self.headers),payload.get('otp')));return
                if path=='/api/motilal/login-start':self.send_json(200,service.login_start(user,cookie_token(self.headers)));return
                if path=='/api/motilal/login-complete':self.send_json(200,service.login_complete(user,cookie_token(self.headers),payload.get('auth_token')));return
                self.send_json(404,dict(error='Use the existing dashboard workflows. Standalone Motilal trading is disabled.'));return
            except Exception as error:self.failure(error)
        def failure(self,error):
            if isinstance(error,PermissionError):self.send_json(403,dict(error=str(error)))
            elif isinstance(error,MotilalError):self.send_json(409 if error.uncertain else 401 if error.auth_required else 502,dict(error=str(error),uncertain=error.uncertain,auth_required=error.auth_required))
            elif isinstance(error,(ValueError,TypeError,KeyError)):self.send_json(400,dict(error=str(error)))
            else:self.send_json(502,dict(error='Motilal request could not complete. No automatic order retry was made.'))
        def log_message(self,*args):pass
    return Handler


def main():
    guard=WorkspaceGuard.from_environment()
    if not guard:raise RuntimeError('Motilal dashboard requires its registered private workspace.')
    with guard.store.db() as db:account=dict(db.execute('SELECT * FROM accounts WHERE id=?',(guard.account_id,)).fetchone())
    if account['broker']!='MOTILAL_OSWAL':raise RuntimeError('Motilal worker account mismatch.')
    account['live_enabled']=bool(account['live_enabled']) and os.environ.get('MOTILAL_ENABLE_LIVE_ORDERS')=='1'
    service=Service(guard.store.folder(account),account)
    with ThreadingHTTPServer(('127.0.0.1',guard.port),handler_factory(guard,service)) as server:
        try:server.serve_forever()
        finally:
            if service.feed:service.feed.stop()

if __name__=='__main__':main()
