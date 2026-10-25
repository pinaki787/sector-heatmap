"""Native Motilal execution and captured candles for the shared strategy engine.

No alternate data broker, historical API guess, mutation retry or truncated tag.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
from zoneinfo import ZoneInfo
from .motilal_api import MotilalError,positive
from .file_lock import lock_file,unlock_file
from strategies.ema_crossover.runner import TIMEFRAMES

IST=ZoneInfo('Asia/Kolkata')
BROKER='MOTILAL_OSWAL'
STATES={'CANCEL':1,'TRADED':2,'SENT':4,'ERROR':5,'REJECTED':5,'CONFIRM':6,'PARTIAL':6}
INDEX_NAMES={'NSE:NIFTY50-INDEX':'NIFTY 50','NSE:NIFTYBANK-INDEX':'NIFTY BANK','BSE:SENSEX-INDEX':'SENSEX',
 'NSE:FINNIFTY-INDEX':'NIFTY FIN SERVICE','NSE:NIFTYIT-INDEX':'NIFTY IT','NSE:NIFTYAUTO-INDEX':'NIFTY AUTO',
 'NSE:NIFTYPHARMA-INDEX':'NIFTY PHARMA','NSE:NIFTYFMCG-INDEX':'NIFTY FMCG','NSE:NIFTYMETAL-INDEX':'NIFTY METAL',
 'NSE:NIFTYREALTY-INDEX':'NIFTY REALTY','NSE:NIFTYENERGY-INDEX':'NIFTY ENERGY','NSE:NIFTYPSUBANK-INDEX':'NIFTY PSU BANK',
 'NSE:NIFTYMEDIA-INDEX':'NIFTY MEDIA','NSE:NIFTYHEALTHCARE-INDEX':'NIFTY HEALTHCARE','NSE:NIFTYOILANDGAS-INDEX':'NIFTY OIL & GAS',
 'NSE:NIFTYCONSRDURBL-INDEX':'NIFTY CONSR DURBL'}
OPTION_NAMES={'NIFTY 50':'NIFTY','NIFTY BANK':'BANKNIFTY','NIFTY FIN SERVICE':'FINNIFTY','SENSEX':'SENSEX'}

def cash_row(row):
    return not row.get('expiry') and (row.get('option_type') in {'A','B','E','X','XT','T','TS','Z','M','MT','MS'} if row.get('exchange')=='BSE' else row.get('option_type') in {'EQ',''})

def normalized(value):return re.sub('[^A-Z0-9]','',str(value).upper())
def whole(value,label,zero=True):
    if isinstance(value,bool):raise ValueError(label+' must be whole.')
    number=Decimal(str(value))
    if not number.is_finite() or number!=int(number) or (not zero and number<=0):raise ValueError(label+' must be whole.')
    return int(number)

@contextmanager
def account_lock(folder):
    path=folder/'motilal-submission.lock'
    with path.open('a') as handle:
        os.chmod(path,0o600);lock_file(handle.fileno())
        try:yield
        finally:unlock_file(handle.fileno())

class Broker:
    count_confirmed_entries=True
    def __init__(self,service,clock=time.time):
        self.service=service;self.clock=clock;self.lock=threading.RLock();self.symbols=set();self.contracts={};self.on_tick=None
        self.account_identity=hashlib.sha256((BROKER+':'+service.account['id']).encode()).hexdigest()
        self.path=service.folder/'motilal-strategy-intents.sqlite3'
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS intents(full_tag TEXT PRIMARY KEY,native_tag TEXT UNIQUE,body TEXT NOT NULL,state TEXT NOT NULL,order_id TEXT,created REAL)')
        self.path.chmod(0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=2)
        try:
            with db:yield db
        finally:db.close()
    @property
    def connected(self):return bool(self.service.feed and self.service.feed.connected)
    def live_enabled(self):return bool(self.service.account.get('live_enabled')) and self.service.client.live_enabled and self.service.execution_allowed()
    def ready(self):self.service.ready();return self.service.client.profile()
    def start(self):self.service.ready();self.service.feed.start()
    def stop(self):pass # Shared account quote capture survives a stopped runner.
    def stream_status(self):
        feed=self.service.feed
        return dict(connected=self.connected,generation=self.service.install_revision*1000000+feed.generation if feed else 0,source='MOTILAL_NATIVE',error=feed.error if feed else 'Connecting',subscribed=sorted(self.symbols))
    def underlying(self,symbol):
        self.service.ready()
        if symbol in INDEX_NAMES:
            exchange=symbol.split(':')[0];names={normalized(INDEX_NAMES[symbol])}
            matches=[r for r in self.service.master.indices(exchange) if normalized(r['name']) in names]
        elif symbol.startswith(('NSE:','BSE:')):
            exchange,ticker=symbol.split(':',1);ticker=ticker.removesuffix('-EQ')
            matches=[r for r in self.service.master.rows(exchange) if r['underlying']==ticker and cash_row(r) and not r['suspended'] and not r['banned']]
        elif symbol.startswith('MCX:') and symbol[4:].isdigit():
            matches=[self.service.master.exact('MO:'+symbol)]
            if matches[0]['instrument']!='FUTCOM':raise ValueError('Select an exact native MCX futures host.')
        else:raise ValueError('Select a verified Motilal cash/index/futures underlying.')
        if len(matches)!=1:raise ValueError('Native underlying mapping is missing or ambiguous: '+symbol)
        return dict(matches[0])
    def search(self,text,market=None):
        self.service.ready();text=text.strip().upper();matches=[]
        category=market
        market=market.split('_')[0] if market and market.startswith(('NSE_','BSE_')) else market
        for symbol,name in INDEX_NAMES.items():
            if category and category.endswith(('_STOCK','_EQUITY')):continue
            if market not in (None,'ALL',symbol.split(':')[0]):continue
            if text and text not in symbol.upper() and text not in name and text not in OPTION_NAMES.get(name,''):continue
            try:self.underlying(symbol)
            except ValueError:continue
            matches.append(dict(symbol=symbol,description=name,underlying=name))
        for exchange in ('NSE','BSE','MCX'):
            if category and category.endswith('_INDEX'):continue
            if market not in (None,'ALL',exchange):continue
            rows=self.service.master.rows(exchange)
            for r in rows:
                if r.get('suspended') or r.get('banned'):continue
                if text not in (r['name']+' '+r['underlying']).upper():continue
                if exchange=='MCX':
                    if r['instrument']!='FUTCOM' or not r['expiry'] or r['expiry']<datetime.fromtimestamp(self.clock(),IST).date().isoformat():continue
                    symbol=f'MCX:{r["token"]}'
                else:
                    if not cash_row(r):continue
                    symbol=exchange+':'+r['underlying']+'-EQ'
                    if category and category.endswith('_STOCK') and not self.option_rows(symbol):continue
                matches.append(dict(symbol=symbol,description=r['name'],underlying=r['underlying']))
                if len(matches)>=100:break
        return matches[:100]
    def subscribe(self,symbol,seconds=None):
        self.service.ready()
        if symbol.startswith('MO:'):meta=self.contract(symbol)
        else:meta=self.underlying(symbol)
        feed=self.service.feed
        if meta['instrument']=='INDEX':feed.subscribe_index(meta['exchange'],meta['token'])
        else:feed.subscribe(meta['exchange'],meta['token'])
        self.symbols.add(symbol)
    def live_price(self,config,now):
        host=self.underlying(config['underlying']);self.subscribe(config['underlying']);self.start()
        return self.service.feed.price(host['exchange'],host['token'],host['instrument']=='INDEX')
    def host_tick_size(self,symbol):
        meta=self.underlying(symbol)
        # SDK index broadcasts use two-decimal display precision. This is only
        # Renko quantization, never an orderable index/execution tick.
        return .01 if meta['instrument']=='INDEX' else meta['tick_size']
    def session_policy(self,config):
        meta=self.underlying(config['underlying']);mcx=meta['exchange']=='MCX'
        if mcx:
            from .market_calendar import market_session
            # Use the existing exchange-calendar close, not a commodity fallback.
            from .motilal_calendar import trading_bounds
            opening,closing=trading_bounds(self.clock())
            start=f'{opening//60:02}:{opening%60:02}';end=f'{closing//60:02}:{closing%60:02}'
        else:start,end='09:15','15:30'
        return dict(session_open=start,session_deadline=end if mcx else '15:10',master_regular_session=start.replace(':','')+'-'+end.replace(':',''),
                    session_exchange=meta['exchange'],session_segment=meta['exchange'],session_source='EXCHANGE_CALENDAR',seven_day_session=False)
    def candles(self,config):
        meta=self.underlying(config['underlying']);self.subscribe(config['underlying']);self.start()
        seconds=TIMEFRAMES[config['timeframe']]
        rows=self.service.history.candles(meta['symbol'],seconds//60,limit=100000,session_open=self.session_policy(config)['session_open'])
        rows=[dict(r,volume=r['volume'] if r['volume_available'] else 0,is_forming=False) for r in rows if r['timestamp']>=config.get('history_start',0)]
        if config.get('fyers_history_enabled') is True:
            seed=getattr(self.service,'history_seed',None)
            if seed is None:raise ValueError('Explicit FYERS history provider is unavailable; no source fallback.')
            history=seed.candles(config,dict(meta,history_symbol=config['underlying']),seconds,self.session_policy(config)['session_open'])
            merged={r['timestamp']:r for r in history if r['timestamp']>=config.get('history_start',0)}
            boundary=seed.evidence.get((config['fyers_history_account_id'],meta['symbol']),{}).get('usable_after') or 0
            merged.update({r['timestamp']:r for r in rows if r['timestamp']>boundary})
            rows=sorted(merged.values(),key=lambda r:r['timestamp'])
        return rows
    def forming(self,config,rows,now):
        host=self.underlying(config['underlying']);seconds=TIMEFRAMES[config['timeframe']]
        dt=datetime.fromtimestamp(now,IST);hour,minute=map(int,self.session_policy(config)['session_open'].split(':'))
        anchor=int(dt.replace(hour=hour,minute=minute,second=0,microsecond=0).timestamp());opening=anchor+int((now-anchor)//seconds)*seconds
        self.live_price(config,now)
        with self.service.history.lock:minute_bar=deepcopy(self.service.history.forming.get(host['symbol']))
        if not minute_bar or not minute_bar['open_verified'] or not opening<=minute_bar['timestamp']<opening+seconds:
            raise ValueError('Verified native forming OHLC is warming up; intrabar entry blocked.')
        prefix=[r for r in self.service.history.candles(host['symbol'],1,limit=60,session_open=self.session_policy(config)['session_open']) if opening<=r['timestamp']<minute_bar['timestamp']]
        if [r['timestamp'] for r in prefix]!=list(range(opening,minute_bar['timestamp'],60)):raise ValueError('Native forming candle contains a gap; intrabar entry blocked.')
        bars=prefix+[minute_bar]
        return dict(timestamp=opening,open=bars[0]['open'],high=max(r['high'] for r in bars),low=min(r['low'] for r in bars),close=minute_bar['close'],volume=sum(r.get('volume') or 0 for r in bars),host_open_verified=True,is_forming=True)
    forming_for_stream=lambda self,config,now:self.forming(config,[],now)
    def contract(self,symbol):
        self.service.ready();meta=self.service.master.exact(symbol)
        if meta['instrument']=='INDEX':raise ValueError('Indices cannot be ordered.')
        result=dict(meta,broker=BROKER,quantity_multiplier=1,product='NORMAL',exchange_segment=meta['exchange'])
        self.contracts[symbol]=result;return result
    def option_rows(self,symbol):
        host=self.underlying(symbol)
        if host['exchange']=='MCX':
            rows=self.service.master.rows('MCX')
            if any(r.get('instrument')=='OPTFUT' and 'underlying_token' not in r for r in rows):
                rows=self.service.master.rows('MCX',refresh=True)
            today=datetime.fromtimestamp(self.clock(),IST).date().isoformat()
            matched=[r for r in rows if r.get('instrument')=='OPTFUT' and r.get('underlying_token')==host['token']
                     and r['underlying']==host['underlying'] and r['option_type'] in {'CE','PE'}
                     and r['expiry'] and today<=r['expiry']<host['expiry'] and not r['suspended'] and not r['banned']]
            if not matched:raise ValueError('No current native MCX options explicitly linked to this futures contract.')
            if any(r['lot_size']!=host['lot_size'] for r in matched):raise ValueError('Native MCX option/futures lot sizes disagree.')
            paired={}
            for row in matched:paired.setdefault((row['expiry'],row['strike']),set()).add(row['option_type'])
            return [r for r in matched if paired[(r['expiry'],r['strike'])]=={'CE','PE'}]
        exchange=host['exchange']+'FO';rows=self.service.master.rows(exchange)
        if any(r.get('option_type') in {'CE','PE'} and 'underlying_token' not in r for r in rows):rows=self.service.master.rows(exchange,refresh=True)
        today=datetime.fromtimestamp(self.clock(),IST).date().isoformat();kind='OPTIDX' if host['instrument']=='INDEX' else 'OPTSTK'
        matched=[r for r in rows if r.get('underlying_token')==host['token'] and r.get('instrument')==kind and r['option_type'] in {'CE','PE'} and r['expiry'] and r['expiry']>=today and not r['suspended'] and not r['banned']]
        paired={}
        for row in matched:paired.setdefault((row['expiry'],row['strike']),set()).add(row['option_type'])
        return [r for r in matched if paired[(r['expiry'],r['strike'])]=={'CE','PE'}]
    def route_availability(self,config):
        if config.get('execution_route')=='CASH_EQUITY':
            host=self.underlying(config['underlying']);return dict(available=host['instrument']!='INDEX' and host['exchange'] in {'NSE','BSE'},message='Motilal native cash equity LIMIT orders')
        try:rows=self.option_rows(config['underlying']);available={'CE','PE'}<={r['option_type'] for r in rows};message='Motilal native bought Call/Put · LIMIT IOC'
        except ValueError as error:available=False;message=str(error)
        return dict(available=available,message=message)
    def resolve(self,config,direction):
        if direction not in {'BULLISH','BEARISH'}:raise ValueError('Explicit direction required.')
        if config.get('execution_route')=='CASH_EQUITY':
            host=self.underlying(config['underlying'])
            if host['instrument']=='INDEX' or direction=='BEARISH':raise ValueError('Motilal cash route supports bought equity; naked cash shorts are not inferred.')
            return dict(self.contract(host['symbol']),quantity=config['quantity'],entry_side=1)
        price,_=self.live_price(config,self.clock());kind='CE' if direction=='BULLISH' else 'PE'
        rows=[r for r in self.option_rows(config['underlying']) if r['option_type']==kind]
        if not rows:raise ValueError('No native option contract for this direction.')
        from .stock_expiry_policy import stock_symbol,require_options_allowed
        if stock_symbol(config['underlying']):require_options_allowed([r['expiry'] for r in rows],datetime.fromtimestamp(self.clock(),IST))
        expiry=min(r['expiry'] for r in rows);rows=[r for r in rows if r['expiry']==expiry]
        chosen=min(rows,key=lambda r:(abs(r['strike']-price),r['strike']))
        self.subscribe(chosen['symbol']);return self.contract(chosen['symbol'])
    def quote(self,symbol):
        meta=self.contract(symbol);self.subscribe(symbol);self.start()
        quote=self.service.feed.quote(meta['exchange'],meta['token'])
        if (quote['ask']-quote['bid'])/quote['ask']>.03:raise ValueError('Native spread exceeds 3%.')
        return dict(quote,bid=round(quote['bid'],4),ask=round(quote['ask'],4))
    def warm_options(self,config):
        for direction in ('BULLISH','BEARISH'):
            try:self.resolve(config,direction)
            except ValueError:pass
    def validate_config(self,config):
        self.ready();self.session_policy(config)
        if not self.route_availability(config)['available']:raise ValueError(self.route_availability(config)['message'])
        if config.get('zone_volume_exit_enabled') or config.get('volume_filter_enabled'):raise ValueError('Native captured candles have no verified traded volume; disable volume-dependent rules.')
        self.subscribe(config['underlying']);self.start()
        if config['mode']=='LIVE':
            if not self.live_enabled():raise PermissionError('Motilal Live capability disabled.')
            self.orders();self.positions()
        return dict(broker=BROKER,account_id=self.service.account['id'],account_identity=self.account_identity,
                    source='Motilal native captured candles; warmup required',execution='Native LIMIT IOC bought options / bought cash equity')
    def order(self,symbol,qty,side,quote):
        meta=self.contract(symbol);tick=Decimal(str(meta['tick_size']))
        price=(Decimal(str(quote['ask' if side==1 else 'bid']))/tick).to_integral_value(rounding=ROUND_CEILING if side==1 else ROUND_FLOOR)*tick
        return dict(symbol=symbol,qty=qty,side=side,type=1,productType='NORMAL',limitPrice=float(price),stopPrice=0,validity='IOC',offlineOrder=False)
    def validate_order(self,order):
        meta=self.contract(order['symbol']);qty=whole(order['qty'],'Units',False);price=positive(order['limitPrice'],'Limit')
        if qty%meta['lot_size'] or order.get('side') not in (1,-1) or order.get('type')!=1 or order.get('productType')!='NORMAL' or order.get('validity')!='IOC' or order.get('offlineOrder') is not False or order.get('stopPrice')!=0 or price%Decimal(str(meta['tick_size'])):
            raise ValueError('Native whole-lot LIMIT IOC order required.')
        lots=qty//meta['lot_size']
        if meta.get('max_quantity') and lots>meta['max_quantity']:raise ValueError('Native quantity limit exceeded.')
    def positions(self):
        rows=self.service.book('positions')['data'];result=[]
        for r in rows:
            net=whole(r['buyquantity'],'Buy units')-whole(r['sellquantity'],'Sell units')
            if not net:continue
            result.append(dict(symbol=f'MO:{r["exchange"]}:{whole(r["symboltoken"],"Token",False)}',netQty=net,productType=r['productname'].upper(),broker=BROKER))
        return result
    def reconcile_position(self,symbol,qty):
        rows=[r for r in self.positions() if r['symbol']==symbol]
        if qty==0 and not rows:return
        if len(rows)!=1 or rows[0]['productType']!='NORMAL' or rows[0]['netQty']!=qty:raise ValueError('Native position differs from exact owned quantity; no exit order sent.')
    def orders(self):
        rows=self.service.book('orders')['data'];result=[]
        with self.db() as db:intents={r[0]:(r[1],json.loads(r[2])) for r in db.execute('SELECT native_tag,full_tag,body FROM intents')}
        for r in rows:
            native=str(r.get('tag') or '').strip();intent=intents.get(native)
            if not intent:continue # Unrelated native orders cannot acquire runner ownership.
            full,body=intent;status=STATES.get(str(r.get('orderstatus') or '').strip().upper())
            if status is None:raise ValueError('Unknown native order status; reconciliation required.')
            qty=whole(r['orderqty'],'Order units',False);filled=whole(r.get('totalqtytraded',0),'Filled units')
            meta=self.contract(body['symbol']);lot=whole(r['lotsize'],'Native lot',False)
            if qty!=body['qty'] or lot!=meta['lot_size'] or not 0<=filled<=qty or str(r['symboltoken'])!=str(meta['token']) or r['exchange']!=meta['exchange'] or str(r.get('buyorsell') or '').strip().upper()!=('BUY' if body['side']==1 else 'SELL') or r['producttype'].upper()!=body['productType']:
                raise PermissionError('Native order identity or quantity differs from the durable intent.')
            price=float(r.get('averageprice') or 0)
            if filled and (not math.isfinite(price) or price<=0):raise ValueError('Verified native fill price unavailable.')
            if filled and abs(price-body['limitPrice'])>max(body['limitPrice']*.05,meta['tick_size']*10):raise ValueError('Native fill-price units/improvement require reconciliation; ownership not inferred.')
            oid=str(r['uniqueorderid'])
            result.append(dict(id=oid,orderTag=full,symbol=body['symbol'],side=body['side'],qty=qty,filledQty=filled,tradedPrice=price,productType=body['productType'],status=status))
            with self.db() as db:db.execute('UPDATE intents SET state=?,order_id=? WHERE native_tag=?',('TERMINAL' if status in (1,2,5,7) else 'ACKNOWLEDGED',oid,native))
        if len({r['orderTag'] for r in result})!=len(result):raise ValueError('Native intent has multiple matching orders.')
        return result
    def funds(self,exchange):
        code=105 if exchange=='MCX' else 103 if exchange.endswith('FO') else 104 if exchange.endswith('CD') else 102
        matches=[r for r in self.service.book('margin')['data'] if whole(r['srno'],'Margin row')==code]
        if len(matches)!=1:raise ValueError('Native segment funds unavailable.')
        return float(positive(matches[0]['amount'],'Available funds'))
    def preflight(self,order,config):
        self.validate_order(order);self.ready();self.reconcile_position(order['symbol'],0)
        self.orders() # Resolve durable acknowledgements before allowing another intent.
        # Every broker order, including externally placed ones, participates in duplicate checks.
        meta=self.contract(order['symbol'])
        for r in self.service.book('orders')['data']:
            if r['exchange']==meta['exchange'] and str(r['symboltoken'])==str(meta['token']) and str(r.get('orderstatus') or '').strip().upper() not in {'CANCEL','TRADED','REJECTED','ERROR'}:raise ValueError('Native pending order blocks entry.')
        with self.db() as db:
            if db.execute("SELECT 1 FROM intents WHERE state IN ('SUBMITTING','UNCERTAIN','ACKNOWLEDGED') LIMIT 1").fetchone():raise ValueError('Reconcile outstanding native intent before another entry.')
        with self.service.tickets.db() as db:
            if db.execute("SELECT 1 FROM tickets WHERE state IN ('SUBMITTING','UNCERTAIN') LIMIT 1").fetchone():raise ValueError('Reconcile uncertain manual ticket before another entry.')
            accepted=db.execute("SELECT id,user_id FROM tickets WHERE state IN ('ACCEPTED','BROKER_CONFIRM','BROKER_PARTIAL','BROKER_SENT')").fetchall()
        for ticket_id,user_id in accepted:
            result=self.service.tickets.reconcile(user_id,ticket_id)
            if result['state'] not in {'BROKER_TRADED','BROKER_CANCEL','BROKER_REJECTED','BROKER_ERROR'}:raise ValueError('Native reviewed order is still pending; entry blocked.')
        quote=self.quote(order['symbol'])
        if self.funds(meta['exchange'])<max(order['limitPrice'],quote['ask'])*order['qty']*1.01:raise ValueError('Native funds insufficient for premium/value plus reserve.')
    def place(self,order):
        started=False
        try:
            if not self.live_enabled():raise PermissionError('Motilal Live capability disabled.')
            self.validate_order(order);meta=self.contract(order['symbol']);self.ready()
            profile=self.service.client.profile()
            if str(profile.get('usertype','')).strip().casefold() not in {'investorclient','investor client'}:raise PermissionError('Native investor-client profile required; no dealer route inferred.')
            if meta['exchange'] not in profile['exchanges'] or 'NORMAL' not in {p.upper() for p in profile['products']}:raise PermissionError('Native segment/product not enabled.')
            tag=order.get('orderTag')
            if not isinstance(tag,str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',tag):raise ValueError('Durable full strategy intent required.')
            now=datetime.fromtimestamp(self.clock(),IST)
            if now.weekday()>4 or not (9*60+15<=now.hour*60+now.minute<15*60+30) and meta['exchange']!='MCX':raise ValueError('Exchange order session is closed.')
            with account_lock(self.service.folder):
                with self.db() as db:
                    if db.execute('SELECT 1 FROM intents WHERE full_tag=?',(tag,)).fetchone():raise ValueError('Intent already attempted; reconcile without replay.')
                if order['side']==1:self.preflight(order,{})
                else:
                    self.reconcile_position(order['symbol'],order['qty'])
                    for r in self.service.book('orders')['data']:
                        if r['exchange']==meta['exchange'] and str(r['symboltoken'])==str(meta['token']) and str(r.get('orderstatus') or '').strip().upper() not in {'CANCEL','TRADED','REJECTED','ERROR'}:raise ValueError('Native pending order could change owned quantity; exit blocked.')
                quote=self.quote(order['symbol'])
                if order['side']==1 and quote['ask']>order['limitPrice'] or order['side']==-1 and quote['bid']<order['limitPrice']:return dict(s='error',code=400,entry_deferred=True,message='Native depth moved beyond the saved limit; no order sent.')
                native='MS'+secrets.token_hex(4)
                body=dict(exchange=meta['exchange'],symboltoken=meta['token'],buyorsell='BUY' if order['side']==1 else 'SELL',ordertype='LIMIT',producttype='NORMAL',orderduration='IOC',price=order['limitPrice'],triggerprice=0,quantityinlot=order['qty']//meta['lot_size'],disclosedquantity=0,amoorder='N',algoid='',participantcode='',tag=native)
                if not self.live_enabled():raise PermissionError('Motilal Live capability changed during preflight; no order sent.')
                with self.db() as db:db.execute('INSERT INTO intents VALUES (?,?,?,?,?,?)',(tag,native,json.dumps(order),'SUBMITTING',None,self.clock()))
                started=True;reply=self.service.client.request('place',body);oid=str(reply.get('uniqueorderid') or '')
                if not re.fullmatch('[A-Za-z0-9_-]{1,50}',oid):raise MotilalError('Uncertain native acceptance.',uncertain=True)
                with self.db() as db:db.execute("UPDATE intents SET state='ACKNOWLEDGED',order_id=? WHERE full_tag=?",(oid,tag))
                return dict(s='ok',id=oid)
        except Exception as error:
            uncertain=started and (not isinstance(error,MotilalError) or error.uncertain)
            if started:
                with self.db() as db:db.execute('UPDATE intents SET state=? WHERE full_tag=?',('UNCERTAIN' if uncertain else 'REJECTED',tag))
            return dict(s='error',code=201 if uncertain else 400,message='Motilal: '+str(error))
    def cancel(self,order_id):
        if not self.live_enabled():raise PermissionError('Motilal Live disabled.')
        rows=[r for r in self.orders() if r['id']==str(order_id)]
        if len(rows)!=1:raise PermissionError('No unique native strategy-owned order to cancel.')
        with account_lock(self.service.folder):return self.service.client.request('cancel',dict(uniqueorderid=str(order_id)))
