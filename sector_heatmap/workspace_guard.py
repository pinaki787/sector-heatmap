"""Authenticate every request made to an isolated account dashboard."""
import json
import os
from pathlib import Path
from .file_lock import lock_file
from .workspaces import WorkspaceStore, cookie_token


class WorkspaceGuard:
    def __init__(self, store, account_id, port, portal_port):
        self.store,self.account_id,self.port,self.portal_port=store,account_id,int(port),int(portal_port)
        self.owner_fd=None

    @classmethod
    def from_environment(cls):
        registry=os.getenv('SECTOR_PULSE_WORKSPACE_REGISTRY')
        aid=os.getenv('SECTOR_PULSE_WORKSPACE_ID')
        if not registry and not aid:return None
        if not registry or not aid:raise ValueError('Incomplete account workspace context.')
        guard=cls(WorkspaceStore(registry),aid,os.environ['HEATMAP_PORT'],os.environ['SECTOR_PULSE_PORTAL_PORT'])
        with guard.store.db() as db:
            row=db.execute('SELECT * FROM accounts WHERE id=?',(aid,)).fetchone()
        if not row or row['port']!=guard.port:raise ValueError('Workspace port/account mismatch.')
        folder=guard.store.folder(dict(row))
        if Path(__file__).resolve().parents[1] != folder/'source':
            raise ValueError('Account dashboard must run from its isolated source directory.')
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        guard.owner_fd=os.open(folder/'dashboard-owner.lock',os.O_RDWR|os.O_CREAT,0o600)
        try:lock_file(guard.owner_fd,blocking=False)
        except Exception:
            os.close(guard.owner_fd);raise RuntimeError('Account dashboard already running.') from None
        owner=json.dumps({'pid':os.getpid()}).encode()
        os.lseek(guard.owner_fd,0,os.SEEK_SET);os.write(guard.owner_fd,owner);os.ftruncate(guard.owner_fd,len(owner))
        return guard

    def authorize(self,headers,mutation=False):
        host=f'127.0.0.1:{self.port}'
        if headers.get('Host')!=host:
            raise PermissionError('Use this account’s registered 127.0.0.1 address.')
        if mutation and headers.get('Origin')!='http://'+host:
            raise PermissionError('Account actions require a same-origin request.')
        user=self.store.session(cookie_token(headers))
        account=self.store.account(user,self.account_id)
        return user,account

    def validate_action(self,account,path,payload):
        delta=path.startswith(('/api/delta-india/','/api/renko-delta/'))
        if path.startswith('/api/renko-instances/'):
            if payload.get('broker')!=account['broker']:
                raise PermissionError('Action broker differs from this account workspace.')
        elif account['broker']=='FYERS' and delta:
            raise PermissionError('Open a Delta India account workspace for this action.')
        elif account['broker']=='DELTA_INDIA' and not delta:
            raise PermissionError('Open a FYERS account workspace for this action.')
        # Credential identity cannot be changed through a running dashboard.
        if path=='/api/delta-india/connect':
            raise PermissionError('Save broker credentials in user and broker setup while the dashboard is stopped.')

    def context(self,user,account):
        return dict(username=user['username'],admin=bool(user['admin']),allowed_features=user.get('features',[]),workspace={k:account[k] for k in ('id','label','broker','account_ref','live_enabled')},
                    portal_url=f'http://127.0.0.1:{self.portal_port}/')

    def check(self,handler,mutation=False):
        try:
            user,account=self.authorize(handler.headers,mutation)
            if handler.path.split('?',1)[0].startswith('/api/whatsapp/'):
                raise PermissionError('Native WhatsApp uses the shared desktop session and is unavailable in isolated user workspaces.')
            from .section_permissions import allowed
            if not allowed(user,handler.path.split('?',1)[0]):
                raise PermissionError('This section is not assigned to your user.')
            handler.workspace_identity=(user,account)
            return True
        except PermissionError as e:
            path=handler.path.split('?',1)[0]
            if not mutation and path in ('/','/index.html','/workspace-entry'):
                body=('<!doctype html><title>Sector Pulse sign in</title><h1>Sign in to your workspace</h1>'
                      f'<p><a href="http://127.0.0.1:{self.portal_port}/">Open user and broker setup</a></p>').encode()
                handler.send_response(401);handler.send_header('Content-Type','text/html');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(body)));handler.end_headers()
                if handler.command!='HEAD':handler.wfile.write(body)
            else:handler.send_json(403,dict(error=str(e)))
            return False
