"""Explicit one-shot TradingView OAuth PKCE connection; never starts trading."""
import base64,hashlib,hmac,json,os,secrets,time
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from urllib.parse import urlencode,urlsplit,parse_qs
import requests

ROOT=Path('/home/trading/sector-heatmap/.private/nifty-ai-options/tradingview')
RESOURCE='https://mcp.tradingview.com/mcp'
ISSUER='https://www.tradingview.com'
REDIRECT='http://127.0.0.1:19874/callback'

def private_write(path,value):
    temp=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'w') as out:
            json.dump(value,out);out.flush();os.fsync(out.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def connect():
    client=json.loads((ROOT/'oauth-client.json').read_text())
    verifier=secrets.token_urlsafe(64)
    state=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    received={}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            parsed=urlsplit(self.path);query=parse_qs(parsed.query)
            valid=(parsed.path=='/callback' and self.headers.get('Host')=='127.0.0.1:19874'
                   and len(query.get('state',[]))==1 and hmac.compare_digest(query['state'][0],state))
            if not valid:
                self.send_response(400);self.end_headers();self.wfile.write(b'Invalid OAuth callback.');return
            if len(query.get('code',[]))==1:received['code']=query['code'][0]
            elif query.get('error'):received['error']='Authorization declined or failed'
            else:
                self.send_response(400);self.end_headers();return
            self.send_response(200);self.send_header('Content-Type','text/plain')
            self.send_header('Cache-Control','no-store');self.end_headers()
            self.wfile.write(b'TradingView authorization received. You can close this tab.')
    server=HTTPServer(('127.0.0.1',19874),Callback);server.timeout=1
    params=dict(response_type='code',client_id=client['client_id'],redirect_uri=REDIRECT,
                scope='mcp:read mcp:tools',state=state,code_challenge=challenge,
                code_challenge_method='S256',resource=RESOURCE)
    print('AUTHORIZE_URL='+ISSUER+'/mcp/oauth/authorize?'+urlencode(params),flush=True)
    try:
        deadline=time.monotonic()+600
        while not received and time.monotonic()<deadline:server.handle_request()
    finally:server.server_close()
    if 'code' not in received:raise RuntimeError(received.get('error','Authorization timed out'))
    response=requests.post(ISSUER+'/mcp/oauth/token',data=dict(grant_type='authorization_code',
        client_id=client['client_id'],code=received['code'],redirect_uri=REDIRECT,
        code_verifier=verifier,resource=RESOURCE),timeout=(5,25),allow_redirects=False)
    if response.status_code!=200:raise RuntimeError('Token exchange failed: HTTP '+str(response.status_code))
    token=response.json()
    if not isinstance(token.get('access_token'),str) or str(token.get('token_type','')).lower()!='bearer':
        raise RuntimeError('Invalid OAuth token response')
    token['obtained_at']=time.time()
    private_write(ROOT/'oauth-token.json',token)
    print('CONNECTED: private OAuth credentials stored; no broker or trading action.',flush=True)


def access_token():
    """Refresh only this explicitly authorized MCP grant; no browser/session tokens."""
    import fcntl
    with (ROOT/'oauth-refresh.lock').open('a+') as lock:
        os.chmod(ROOT/'oauth-refresh.lock',0o600)
        fcntl.flock(lock,fcntl.LOCK_EX)
        token=json.loads((ROOT/'oauth-token.json').read_text())
        if time.time() < token['obtained_at']+float(token['expires_in'])-30:
            return token['access_token']
        if not token.get('refresh_token'):raise RuntimeError('TradingView reauthorization required')
        client=json.loads((ROOT/'oauth-client.json').read_text())
        response=requests.post(ISSUER+'/mcp/oauth/token',data=dict(grant_type='refresh_token',
            client_id=client['client_id'],refresh_token=token['refresh_token'],resource=RESOURCE),
            timeout=(5,25),allow_redirects=False)
        if response.status_code!=200:raise RuntimeError('TradingView refresh failed: HTTP '+str(response.status_code))
        updated=response.json()
        if not isinstance(updated.get('access_token'),str) or str(updated.get('token_type','')).lower()!='bearer':
            raise RuntimeError('Invalid TradingView refresh response')
        if set(updated.get('scope',token['scope']).split())-set(token['scope'].split()):
            raise RuntimeError('TradingView refresh expanded scopes')
        updated.setdefault('refresh_token',token['refresh_token'])
        updated.setdefault('scope',token['scope'])
        updated['obtained_at']=time.time()
        if not isinstance(updated.get('expires_in'),(int,float)) or updated['expires_in']<=30:
            raise RuntimeError('Invalid TradingView token lifetime')
        private_write(ROOT/'oauth-token.json',updated)
        return updated['access_token']

if __name__=='__main__':connect()
