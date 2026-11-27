"""Loopback-only, account-owned Motilal dashboard and native order route."""
from datetime import datetime
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse,parse_qs
from zoneinfo import ZoneInfo
from .motilal_api import MotilalError
from .motilal_service import Service
from .workspace_guard import WorkspaceGuard
from .workspaces import cookie_token

ROOT=Path(__file__).resolve().parents[1]


def handler_factory(guard,service):
    from .motilal_login import SavedLogin
    saved_login=None
    ai_bridges={}
    import threading
    ai_lock=threading.RLock()
    def ai(fields=None):
        from strategies.nifty_ai_options.multi_runner import selected_symbol
        instrument=selected_symbol(guard.account_id,fields)
        with ai_lock:
         if instrument not in ai_bridges:
            from strategies.nifty_ai_options.ui_bridge import Service as AiService,NativeLegacyView
            ai_bridges[instrument]=AiService(guard.account_id,NativeLegacyView(guard.account_id),instrument=instrument)
        return ai_bridges[instrument]
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
                'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'"}.items():self.send_header(key,value)
            self.end_headers();self.wfile.write(data)
        def identity(self,mutation=False):
            user,account=guard.authorize(self.headers,mutation)
            if account['broker']!='MOTILAL_OSWAL':raise PermissionError('This server serves only its registered Motilal account.')
            path=urlparse(self.path).path
            if path.startswith('/api/motilal/'):
                if not user.get('admin') and 'broker' not in user.get('features',[]):raise PermissionError('Broker connection is not assigned to your user.')
                if not guard.store.sidebar_visibility().get('broker',True):raise PermissionError('Broker connection is hidden in dashboard visibility settings.')
            if path.startswith('/api/renko-supertrend/ai-options/'):
                from .section_permissions import allowed
                if not allowed(user,path) or not guard.store.sidebar_visibility().get('renko-supertrend',True):raise PermissionError('Renko strategy is not assigned or visible for this user.')
            if mutation:
                if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),user['csrf']):raise PermissionError('Refresh the dashboard before this action.')
                if not path.startswith('/api/renko-supertrend/ai-options/'):guard.validate_action(account,path,{'broker':'MOTILAL_OSWAL'})
            return user,account
        def do_GET(self):
            try:
                user,account=self.identity();path=urlparse(self.path).path
                if path.startswith('/api/renko-supertrend/ai-options/'):
                    query={k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}
                    action=path.rsplit('/',1)[-1]
                    if query.get('account_id') not in (None,account['id']):raise PermissionError('AI account binding mismatch')
                    if action=='status':result=ai(query).snapshot()
                    elif action=='chart-source':result=ai(query).chart_source(query)
                    elif action=='search':result=ai(query).search(query.get('q',''),query.get('market','ALL'),query.get('route','OPTIONS'))
                    else:raise ValueError('Unsupported native AI read action')
                    self.send_json(200,result);return
                if path in {'/','/index.html','/workspace-entry'}:self.response(200,(ROOT/'motilal-oswal.html').read_bytes());return
                files={'/motilal-oswal.js':('motilal-oswal.js','text/javascript'),'/workspace-portal.css':('workspace-portal.css','text/css')}
                files.update({name: (name.lstrip('/'), 'text/css' if name.endswith('.css') else 'text/javascript')
                              for name in ('/chart-workspace.js', '/chart-workspace-studies.js',
                                           '/chart-workspace.css', '/vendor/lightweight-charts-4.2.3.js')})
                if path in files:
                    name,mime=files[path];self.response(200,(ROOT/name).read_bytes(),mime);return
                if path == '/workspace-bootstrap.js':
                    context = {**guard.context(user, account), 'chart_workspace_available': True, 'chart_ncdex_available': True}
                    body = ('window.SectorPulseWorkspace=' + json.dumps(context).replace('<', chr(92)+'u003c') + ';').encode()
                    self.response(200, body, 'text/javascript')
                    return
                if path == '/api/chart-workspace/symbols':
                    from .chart_workspace import require_chart
                    require_chart(user, guard.store, path)
                    query = parse_qs(urlparse(self.path).query)
                    search_text = query.get('q', [''])[0][:120].strip().upper()
                    venue, separator, ticker = search_text.partition(':')
                    venue = venue if separator and venue in ('NSE', 'BSE', 'NSEFO', 'BSEFO', 'NSECD', 'MCX', 'NCDEX') else ''
                    ticker = ticker.strip() if venue else search_text
                    suffix = ticker.rpartition('-')[2] if venue in ('NSE', 'BSE') else ''
                    board = suffix if suffix in ('INDEX', 'EQ') else ''
                    if board:
                        ticker = ticker.rpartition('-')[0].strip()
                    terms = ticker.split()
                    compact = re.sub(r'[^A-Z0-9]', '', ticker)
                    segment = query.get('segment', [''])[0]
                    instrument_kind=''
                    if segment in ('MCX_FUT','MCX_OPT'):segment,instrument_kind=segment.rsplit('_',1)
                    offset = query.get('offset', ['0'])[0]
                    segments = ('INDEX_NSE', 'INDEX_BSE', 'NSE', 'BSE', 'NSEFO', 'BSEFO', 'NSECD', 'MCX', 'NCDEX')
                    if segment and segment not in segments:
                        raise ValueError('Invalid Motilal chart segment.')
                    if not offset.isascii() or not offset.isdecimal() or len(offset) > 7:
                        raise ValueError('Invalid catalog offset.')
                    service.ready()
                    matches = {}
                    exact_matches = set()
                    unavailable = []
                    selected_segments = (segment,) if segment else segments
                    today = datetime.fromtimestamp(service.clock(), ZoneInfo('Asia/Kolkata')).date().isoformat()
                    for exchange in selected_segments:
                        try:
                            rows = (service.master.indices(exchange[6:]) if exchange.startswith('INDEX_')
                                    else service.master.rows(exchange, market_data=True) if exchange == 'NCDEX'
                                    else service.master.rows(exchange))
                        except MotilalError as error:
                            if error.auth_required or segment:
                                raise
                            unavailable.append(exchange)
                            continue
                        except ValueError:
                            if segment:
                                raise
                            unavailable.append(exchange)
                            continue
                        for row in rows:
                            if instrument_kind and not row.get('instrument','').startswith(instrument_kind):continue
                            expiry = row.get('expiry')
                            if row.get('suspended') or (expiry and expiry < today):
                                continue
                            is_index = row['instrument'] == 'INDEX'
                            if venue and not row['exchange'].startswith(venue):
                                continue
                            if board and (row['exchange'] != venue or is_index != (board == 'INDEX')):
                                continue
                            underlying = row.get('underlying') or ''
                            text = f"{row['symbol']} {row['name']} {underlying}".upper()
                            index_alias = is_index and compact and compact == re.sub(r'[^A-Z0-9]', '', row['name'].upper())
                            if not index_alias and not all(term in text for term in terms):
                                continue
                            identity = row['symbol']
                            if index_alias or search_text == identity or ticker in (row['name'].upper(), underlying.upper()):
                                exact_matches.add(identity)
                            matches[identity] = {
                                'id': identity, 'symbol': row['name'], 'exchange': row['exchange'],
                                'instrument': row['instrument'], 'tick_size': row.get('tick_size'),
                            }
                    ordered = sorted(matches.values(), key=lambda row: (row['id'] not in exact_matches, row['symbol'], row['id']))
                    start = int(offset)
                    if len(unavailable) == len(selected_segments):
                        self.send_json(503, {'error': 'Motilal instrument catalogs are unavailable.'})
                        return
                    self.send_json(200, {'symbols': ordered[start:start+100], 'total': len(ordered),
                                         'unavailable_segments': unavailable})
                    return
                if path in {'/api/chart-workspace/history', '/api/chart-workspace/live'}:
                    from .chart_workspace import motilal_chart, require_chart
                    require_chart(user, guard.store, path)
                    query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
                    if any(len(query.get(key, [])) > 1 for key in ('interval', 'after', 'before', 'symbol')):
                        raise ValueError('Use one chart interval, symbol, and history cursor per request.')
                    before = query.get('before', [None])[0]
                    interval = query.get('interval', ['5'])[0]
                    symbol = query.get('symbol', [None])[0]
                    if symbol == '':
                        raise ValueError('Select a Motilal chart instrument.')
                    after = query.get('after', [None])[0]
                    live = path.endswith('/live')
                    try:
                        payload = motilal_chart(service, interval, after, live, symbol=symbol, before=before)
                    except MotilalError as error:
                        if error.auth_required:
                            self.send_json(401, {'error': str(error), 'auth_required': True})
                        else:
                            self.send_json(503, {'error': 'Motilal chart market data is unavailable.'})
                    except (OSError, RuntimeError):
                        self.send_json(503, {'error': 'Motilal chart market data is unavailable.'})
                    else:
                        self.send_json(200, payload)
                    return
                if path=='/api/workspace-context':
                    self.send_json(200,{**guard.context(user,account),'chart_ncdex_available':True,'csrf':user['csrf'],'visible':guard.store.sidebar_visibility().get('broker',True),
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
                if path.startswith('/api/renko-supertrend/ai-options/'):
                    guard.validate_action(account,path,payload)
                    action=path.rsplit('/',1)[-1]
                    methods={'prepare':'prepare','start':'start','stop':'stop','manual-entry':'manual_entry','reconfigure':'reconfigure','position-control':'position_action'}
                    if action not in methods:raise ValueError('Unsupported native AI action')
                    self.send_json(200,getattr(ai(payload),methods[action])(payload));return
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
            else:
                import traceback
                frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(error.__traceback__)]
                print(json.dumps(dict(event='motilal_request_failure',error_type=type(error).__name__,frames=frames)),flush=True)
                self.send_json(502,dict(error='Motilal request could not complete. No automatic order retry was made.'))
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
