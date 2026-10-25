"""Owned FYERS adapter: exact-position exits only, streamed price triggers."""
import json,os,sqlite3,time
from pathlib import Path
from threading import Lock,Thread
from .handoff_exit_monitor import Store,Service

class Broker:
    def __init__(self,folder,account_id,registry):
        self.folder,self.account_id,self.registry=Path(folder),account_id,Path(registry)
        self.lock=Lock();self.socket=None;self.symbols=[];self.ticks={};self.connected=False;self.token=None
    def allowed(self,p):
        with sqlite3.connect('file:'+str(self.registry)+'?mode=ro',uri=True) as d:
            r=d.execute('SELECT a.user_id,a.broker,a.live_enabled,u.admin FROM accounts a JOIN users u ON u.id=a.user_id WHERE a.id=?',(self.account_id,)).fetchone()
            feature=r and (r[3] or d.execute('SELECT 1 FROM user_features WHERE user_id=? AND feature=?',(r[0],'handoff')).fetchone())
        return bool(r and r[0]==p.get('user_id') and r[1]=='FYERS' and r[2] and feature and p.get('account_id')==self.account_id)
    def client(self):
        from .fyers_execution import _current_client
        return _current_client()
    def snapshot(self):
        c=self.client();book=c.orderbook();positions=c.positions()
        if book.get('s')!='ok' or positions.get('s')!='ok' or not isinstance(book.get('orderBook'),list) or not isinstance(positions.get('netPositions'),list):
            raise ValueError('Fresh owned FYERS order and position books unavailable.')
        return dict(orders=book['orderBook'],positions=positions['netPositions'],at=time.time())
    def session_open(self):
        from .market_calendar import market_session
        return market_session()['status']=='OPEN'
    def entry_result(self,preview):
        if not preview or any(not (c.isalnum() or c in '-_') for c in preview):return None
        from .fyers_execution import DailyRiskLedger
        p=DailyRiskLedger().path.parent/'entry-evidence'/(preview+'-result.json')
        try:return json.loads(p.read_text()).get('result')
        except (OSError,ValueError):return None
    def subscribe(self,symbols):
        from .config import load_config
        token=load_config().get('FYERS_ACCESS_TOKEN')
        if not symbols:
            if self.socket:self.close()
            self.symbols=[];return
        if self.socket and self.token==token:
            additions=sorted(set(symbols)-set(self.symbols));self.symbols=symbols
            if additions:
                try:self.socket.subscribe(symbols=additions,data_type='SymbolUpdate')
                except Exception:
                    with self.lock:self.connected=False
            return
        self.close();self.symbols=symbols;self.token=token
        if not token:return
        from .market_data import configure_websocket_ca_bundle
        from fyers_apiv3.FyersWebsocket import data_ws
        configure_websocket_ca_bundle()
        def connect():
            with self.lock:self.connected=True
            socket.subscribe(symbols=self.symbols,data_type='SymbolUpdate')
        def message(m):
            if not isinstance(m,dict) or m.get('symbol') not in self.symbols:return
            try:
                price=float(m.get('ltp'));provider=float(m.get('last_traded_time') or m.get('exch_feed_time') or 0)
                if provider>1e10:provider/=1000
            except (TypeError,ValueError):return
            with self.lock:self.ticks[m['symbol']]=dict(price=price,provider_at=provider,received_at=time.time())
        def disconnected(*_):
            with self.lock:self.connected=False;self.ticks={}
        socket=data_ws.FyersDataSocket(access_token=token,litemode=False,reconnect=True,write_to_file=False,on_connect=connect,on_message=message,on_error=disconnected,on_close=disconnected)
        self.socket=socket
        Thread(target=socket.connect,daemon=True,name='handoff-held-price-feed').start()
    def quote(self,symbol):
        with self.lock:return dict(self.ticks.get(symbol,{}) or {},connected=self.connected)
    def preflight_takeover(self,r,pos):
        from .handoff import FyersFoMaster,FyersCmMaster
        master=FyersCmMaster() if r['symbol'].endswith('-EQ') else FyersFoMaster()
        meta=master.lookup([r['symbol']]).get(r['symbol'])
        if not meta or not pos or abs(int(pos['netQty']))%int(meta.get('lot_size') or 1):raise ValueError('Current exact master/owned lot evidence unavailable; native exits retained.')
        funds=self.client().funds()
        if not isinstance(funds,dict) or funds.get('s')!='ok':raise ValueError('Fresh broker account evidence unavailable; native exits retained.')
    def cancel_entry(self,r):return self.client().cancel_order({'id':r['entry_id']})
    def detach(self,r,pos,parent):
        if not pos or pos.get('id')!=r['symbol']+'-'+r['product']:raise ValueError('Exact owned position id required.')
        if parent and parent.get('status') in (2,4,6):return self.client().modify_order({'id':r['entry_id'],'stopLoss':None,'takeProfit':None})
        # Official position-leg API; installed SDK predates this convenience method.
        from fyers_apiv3.fyersModel import Config
        c=self.client()
        return c.service.patch_call(Config.positions,c.header,{'positionId':pos['id'],'stopLoss':None,'takeProfit':None})
    def exit_position(self,r,pos):
        ident=pos.get('id')
        if not ident or ident!=r['symbol']+'-'+r['product']:raise ValueError('A single exact owned position id is mandatory.')
        # Never call exit_positions() with an empty body: it would mean exit-all.
        from .handoff import FyersFoMaster,FyersCmMaster
        master=FyersCmMaster() if r['symbol'].endswith('-EQ') else FyersFoMaster()
        meta=master.lookup([r['symbol']]).get(r['symbol'])
        if not meta:raise ValueError('Exact owned contract is unavailable in the current broker master; exit withheld.')
        quantity=abs(int(pos['netQty']))
        if not quantity or quantity%int(meta.get('lot_size') or 1):raise ValueError('Owned exit quantity does not match the exact contract lot.')
        return self.client().exit_positions({'id':ident})
    def release(self,r):
        claims=self.folder/'handoff-schedule.claims.sqlite3';schedule=self.folder/'handoff-schedule.sqlite3'
        if claims.exists():
            with sqlite3.connect(claims) as d:d.execute("UPDATE claims SET state='CLOSED' WHERE account=? AND fingerprint=?",(self.account_id,r['id']))
        if schedule.exists():
            with sqlite3.connect(schedule) as d:
                v=d.execute('SELECT body FROM receipts WHERE fingerprint=?',(r['id'],)).fetchone()
                if v:
                    body=json.loads(v[0]);body['exit_monitor']=dict(state='CLOSED',closed_at=r.get('closed_at'),gross_realized_pnl=r.get('gross_realized_pnl'),net_pnl=None,pnl_basis=r.get('pnl_basis'))
                    d.execute("UPDATE receipts SET state='CLOSED',body=?,updated=? WHERE fingerprint=?",(json.dumps(body),time.time(),r['id']))
    def close(self):
        with self.lock:socket,self.socket=self.socket,None;self.connected=False;self.ticks={}
        if socket:
            try:socket.close_connection()
            except Exception:pass

def start_owned():
    aid=os.getenv('SECTOR_PULSE_WORKSPACE_ID');registry=os.getenv('SECTOR_PULSE_WORKSPACE_REGISTRY')
    if not aid or not registry or os.getenv('SECTOR_PULSE_WORKSPACE_BROKER')!='FYERS':return None
    folder=Path.cwd().parent
    if folder.name!=aid or Path.cwd().name!='source':raise ValueError('Owned exit monitor source identity mismatch.')
    service=Service(folder,Broker(folder,aid,registry));service.start();return service
