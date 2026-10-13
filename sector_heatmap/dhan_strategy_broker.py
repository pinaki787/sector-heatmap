"""User-owned Dhan adapter for durable option strategy runners.

Construction is inert. Order intent belongs to the runner; submissions are never
retried here. Unknown acknowledgements reconcile by the persisted correlation ID.
"""
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import math
import threading
import time

from .dhan_execution import IST, number, contract_underlying, DhanAPIError
from strategies.ema_crossover.runner import TIMEFRAMES

STATES={'CANCELLED':1,'TRADED':2,'TRANSIT':4,'REJECTED':5,'PENDING':6,'PART_TRADED':6,'EXPIRED':7}


def whole(value,label):
    result=number(value,label)
    if isinstance(value,bool) or result!=int(result):raise ValueError(label+' must be a whole number.')
    return int(result)

from .dhan_execution import fresh_quote_snapshot

class Broker:
    def __init__(self, service, clock=time.time):
        self.service=service; self.clock=clock
        self.lock=threading.RLock(); self.account_identity=None
        self.connected=False; self.generation=0; self.symbols=set()
        self.history_cache={}; self.contracts={}; self.on_tick=None
        self.stream_history_refresh=set(); self.stream_history_errors={}
        self.owned_tags={}; self.stream_error=None

    def live_enabled(self):
        return bool(self.service.account.get('live_enabled')) and self.service.execution_allowed()

    def authenticated_client(self):
        client=self.service._client()
        profile=client.request('GET','/profile')
        if str(profile.get('dhanClientId'))!=str(client.client_id):
            raise PermissionError('Dhan token does not belong to this broker account.')
        identity=hashlib.sha256(('DHAN:'+str(client.client_id)).encode()).hexdigest()
        if self.account_identity and identity!=self.account_identity:
            raise PermissionError('Dhan strategy account identity changed.')
        self.account_identity=identity
        if str(profile.get('dataPlan','')).lower()!='active':
            raise ValueError('Dhan Data API subscription must be active.')
        return client

    def _rows(self): return self.service.master.load(datetime.fromtimestamp(self.clock(),IST))

    @staticmethod
    def _segment(row):
        if row['SEM_SEGMENT']=='I': return 'IDX_I'
        return row['SEM_EXM_EXCH_ID']+{'E':'_EQ','D':'_FNO'}.get(row['SEM_SEGMENT'],'_UNSUPPORTED')

    def _meta(self,row):
        raw_lot=number(row['SEM_LOT_UNITS'],'Master lot size',True)
        if raw_lot!=int(raw_lot): raise ValueError('Invalid Dhan lot size.')
        segment=self._segment(row)
        return dict(symbol=segment+':'+row['SEM_SMST_SECURITY_ID'],
                    security_id=row['SEM_SMST_SECURITY_ID'],exchange_segment=segment,
                    trading_symbol=row['SEM_TRADING_SYMBOL'],lot_size=int(raw_lot),
                    tick_size=float(number(row['SEM_TICK_SIZE'],'Master tick',True)/100),
                    quantity_multiplier=1,dhan_exchange_rate=(0.000355299 if segment=='NSE_FNO' else 0.000325 if row.get('SEM_INSTRUMENT_NAME')=='OPTIDX' else 0.00005) if segment in ('NSE_FNO','BSE_FNO') else None,option_type=row.get('SEM_OPTION_TYPE'),
                    expiry=row.get('SEM_EXPIRY_DATE','')[:10],product='MARGIN',broker='DHAN')

    def underlying(self,symbol):
        exchange,ticker=symbol.split(':',1)
        aliases={'NIFTY50-INDEX':'NIFTY','NIFTYBANK-INDEX':'BANKNIFTY','SENSEX-INDEX':'SENSEX'}
        ticker=aliases.get(ticker,ticker.removesuffix('-EQ'))
        matches=[r for r in self._rows() if r['SEM_EXM_EXCH_ID']==exchange and
                 r['SEM_SEGMENT'] in ('I','E') and r['SEM_TRADING_SYMBOL']==ticker]
        if len(matches)!=1: raise ValueError('Underlying missing or ambiguous in current Dhan master.')
        return matches[0]

    def search(self,text):
        text=text.upper();rows=self._rows()
        today=datetime.fromtimestamp(self.clock(),IST).date().isoformat()
        eligible={(r['SEM_EXM_EXCH_ID'],contract_underlying(r)) for r in rows
                  if r['SEM_SEGMENT']=='D' and r['SEM_OPTION_TYPE'] in ('CE','PE') and r['SEM_EXPIRY_DATE'][:10]>=today}
        hosts=[r for r in rows if r['SEM_EXM_EXCH_ID'] in ('NSE','BSE') and r['SEM_SEGMENT'] in ('I','E')
               and text in r['SEM_TRADING_SYMBOL'] and (r['SEM_EXM_EXCH_ID'],r['SEM_TRADING_SYMBOL']) in eligible]
        hosts.sort(key=lambda r:(r['SEM_TRADING_SYMBOL']!=text,r['SEM_SEGMENT']!='I',r['SEM_TRADING_SYMBOL']))
        return [dict(symbol=r['SEM_EXM_EXCH_ID']+':'+r['SEM_TRADING_SYMBOL'],
                     description=r.get('SEM_CUSTOM_SYMBOL') or r['SEM_TRADING_SYMBOL'],underlying=r['SEM_TRADING_SYMBOL']) for r in hosts[:50]]

    def host_tick_size(self,symbol):
        row=self.underlying(symbol)
        return float(number(row['SEM_TICK_SIZE'],'Host tick',True)/(1 if row['SEM_SEGMENT']=='I' else 100))

    def session_policy(self,config):
        self.underlying(config['underlying'])
        return dict(session_open='09:15',session_deadline='15:10',session_segment='NSE_FNO',
                    session_source='INDIAN_CASH_MARKET',seven_day_session=False)

    def route_availability(self,config):
        row=self.underlying(config['underlying']); ticker=row['SEM_TRADING_SYMBOL']
        kinds={r['SEM_OPTION_TYPE'] for r in self._rows() if r['SEM_EXM_EXCH_ID']==row['SEM_EXM_EXCH_ID']
               and r['SEM_SEGMENT']=='D' and contract_underlying(r)==ticker
               and r['SEM_EXPIRY_DATE'][:10]>=datetime.fromtimestamp(self.clock(),IST).date().isoformat()}
        return dict(available={'CE','PE'}<=kinds,message='Dhan nearest-expiry ATM bought Call / Put; no broker fallback.')

    def validate_config(self,config):
        self.session_policy(config)
        if not self.route_availability(config)['available']: raise ValueError('No current Dhan Call/Put pair for this underlying.')
        self.authenticated_client()
        self.subscribe(config['underlying'],TIMEFRAMES[config['timeframe']])
        if config.get('mode')=='LIVE':
            if not self.live_enabled(): raise PermissionError('Dhan live capability is disabled.')
            self.orders(); self.positions()
        return dict(broker='DHAN',account_identity=self.account_identity,account_id=self.service.account['id'],
                    underlying=config['underlying'],execution='Bullish buys Call; bearish buys Put',
                    order_type='Marketable LIMIT IOC',product='MARGIN',
                    risk='IOC can fill partially. Fresh quotes, funds, static IP and exact owned quantities are required. No historical signal replay.')

    def subscribe(self,symbol,seconds=None): self.symbols.add(symbol)
    def start(self):
        if not self.connected: self.generation+=1
        self.connected=True
    def stop(self): self.connected=False
    def stream_status(self):
        return dict(connected=self.connected,generation=self.generation,
                    source='Dhan REST polling',error=self.stream_error,subscribed=sorted(self.symbols))

    def contract(self,symbol):
        segment,security=symbol.split(':',1)
        matches=[r for r in self._rows() if r['SEM_SMST_SECURITY_ID']==security and self._segment(r)==segment]
        if len(matches)!=1: raise ValueError('Dhan contract missing or ambiguous.')
        meta=self._meta(matches[0])
        if meta['option_type'] not in ('CE','PE') or meta['expiry']<datetime.fromtimestamp(self.clock(),IST).date().isoformat():
            raise ValueError('Only current bought Call/Put contracts are supported.')
        self.contracts[symbol]=meta
        return meta

    def _market(self,meta,depth=True):
        row, stamp = fresh_quote_snapshot(self.service._client(), meta['exchange_segment'], meta['security_id'], self.clock)
        if not depth: return float(number(row['last_price'],'Last price',True)),stamp
        bid=float(number(row['depth']['buy'][0]['price'],'Bid',True))
        ask=float(number(row['depth']['sell'][0]['price'],'Ask',True))
        if bid>ask or (ask-bid)/ask>.03: raise ValueError('Dhan quote crossed or spread exceeds 3%.')
        return dict(bid=bid,ask=ask,received_at=stamp,exchange_at=stamp, timestamp_basis='DHAN_REST_SNAPSHOT', last_trade_time=row.get('last_trade_time'))

    def quote(self,symbol): return self._market(self.contract(symbol))

    def live_price(self,config,now):
        row=self.underlying(config['underlying'])
        return self._market(dict(security_id=row['SEM_SMST_SECURITY_ID'],exchange_segment=self._segment(row)),False)

    def resolve(self,config,direction):
        if direction not in ('BULLISH','BEARISH'): raise ValueError('Explicit signal direction required.')
        host=self.underlying(config['underlying']); spot,_=self.live_price(config,self.clock())
        kind='CE' if direction=='BULLISH' else 'PE'
        today=datetime.fromtimestamp(self.clock(),IST).date().isoformat()
        rows=[r for r in self._rows() if r['SEM_EXM_EXCH_ID']==host['SEM_EXM_EXCH_ID'] and
              r['SEM_SEGMENT']=='D' and contract_underlying(r)==host['SEM_TRADING_SYMBOL']
              and r['SEM_OPTION_TYPE']==kind and r['SEM_EXPIRY_DATE'][:10]>=today]
        if not rows: raise ValueError('No current Dhan option for this direction.')
        expiry=min(r['SEM_EXPIRY_DATE'] for r in rows)
        candidates=[r for r in rows if r['SEM_EXPIRY_DATE']==expiry]
        strike=min(abs(float(r['SEM_STRIKE_PRICE'])-spot) for r in candidates)
        matches=[r for r in candidates if abs(float(r['SEM_STRIKE_PRICE'])-spot)==strike]
        # Deterministic lower strike for an exact half-step tie.
        row=min(matches,key=lambda r:float(r['SEM_STRIKE_PRICE']))
        meta=self._meta(row);self.contracts[meta['symbol']]=meta
        return meta

    def warm_options(self,config): pass

    @contextmanager
    def history_lock(self,path):
        import os
        from .file_lock import lock_file,unlock_file
        fd=os.open(path.with_suffix('.lock'),os.O_RDWR|os.O_CREAT,0o600)
        try:
            lock_file(fd)
            yield
        finally:
            unlock_file(fd);os.close(fd)

    def candles(self,config):
        seconds=TIMEFRAMES[config['timeframe']]; now=self.clock()
        key=(config['underlying'],seconds,config.get('history_start'))
        with self.lock:
            cached=self.history_cache.get(key)
            if cached and now-cached[0]<15: return deepcopy(cached[1])
        row=self.underlying(config['underlying'])
        import json,os
        history=self.service.folder/'dhan-strategy-history'
        history.mkdir(mode=0o700,exist_ok=True)
        history_key=hashlib.sha256(json.dumps(key).encode()).hexdigest()
        history_path=history/(history_key+'.json')
        with self.service.lock:
            saved=json.loads(history_path.read_text()) if history_path.exists() else dict(rows=[])
        # Preserve the original runtime anchor across days and server restarts.
        # Refresh the tail; merge broker revisions rather than fabricate gaps.
        begin=max((saved['rows'][-1]['timestamp']-2*86400) if saved['rows'] else config.get('history_start',now-45*86400),now-89*86400)
        interval=seconds//60 if seconds//60 in (1,5,15,25,60) else 1
        raw=self.service._client().request('POST','/charts/intraday',dict(
            securityId=row['SEM_SMST_SECURITY_ID'],exchangeSegment=self._segment(row),
            instrument=row['SEM_INSTRUMENT_NAME'],interval=str(interval),oi=False,
            fromDate=datetime.fromtimestamp(begin,IST).strftime('%Y-%m-%d %H:%M:%S'),
            toDate=datetime.fromtimestamp(now,IST).strftime('%Y-%m-%d %H:%M:%S')))
        fields=('timestamp','open','high','low','close','volume')
        if any(not isinstance(raw.get(k),list) for k in fields) or len({len(raw[k]) for k in fields})!=1:
            raise ValueError('Dhan returned incomplete OHLCV arrays.')
        rows=[];seen=set()
        for values in zip(*(raw[k] for k in fields)):
            bar={k:float(v) for k,v in zip(fields,values)}
            if not all(math.isfinite(v) for v in bar.values()) or min(bar[k] for k in fields[:-1])<=0 or bar['volume']<0:
                raise ValueError('Invalid Dhan OHLCV values.')
            if bar['timestamp'] in seen or bar['high']<max(bar['open'],bar['close']) or bar['low']>min(bar['open'],bar['close']):
                raise ValueError('Invalid or duplicate Dhan candle.')
            seen.add(bar['timestamp']);rows.append(bar)
        rows.sort(key=lambda r:r['timestamp'])
        if interval*60!=seconds:
            buckets={}
            for bar in rows:
                dt=datetime.fromtimestamp(bar['timestamp'],IST)
                anchor=dt.replace(hour=9,minute=15,second=0,microsecond=0).timestamp()
                opening=anchor+int((bar['timestamp']-anchor)//seconds)*seconds
                buckets.setdefault(opening,[]).append(bar)
            aggregate=[]
            for opening,bars in sorted(buckets.items()):
                expected=list(range(int(opening),int(opening+seconds),60))
                actual=[int(b['timestamp']) for b in bars]
                if actual!=expected: continue  # Gaps never manufacture a completed candle.
                aggregate.append(dict(timestamp=opening,open=bars[0]['open'],close=bars[-1]['close'],
                    high=max(b['high'] for b in bars),low=min(b['low'] for b in bars),volume=sum(b['volume'] for b in bars)))
            rows=aggregate
        with self.service.lock,self.history_lock(history_path):
            previous=json.loads(history_path.read_text()) if history_path.exists() else dict(rows=[])
            merged={r['timestamp']:r for r in previous['rows']}
            merged.update({r['timestamp']:r for r in rows})
            rows=[merged[t] for t in sorted(merged)]
            if len(rows)>150000:raise ValueError('Dhan history limit reached; explicit archive required.')
            temporary=history_path.with_suffix('.tmp')
            with temporary.open('w') as f:
                os.chmod(temporary,0o600);json.dump(dict(rows=rows),f,allow_nan=False);f.flush();os.fsync(f.fileno())
            temporary.replace(history_path)
        for bar in rows: bar['is_forming']=bar['timestamp']+seconds>now
        with self.lock:self.history_cache[key]=(now,deepcopy(rows))
        return rows

    def forming_for_stream(self, config, now):
        # History HTTP/disk work must not stall the SSE heartbeat and quote checks.
        key=(config['underlying'],TIMEFRAMES[config['timeframe']],config.get('history_start'))
        with self.lock:
            cached=self.history_cache.get(key)
            fresh=cached is not None and now-cached[0]<15
            if not fresh and key not in self.stream_history_refresh:
                self.stream_history_refresh.add(key)
                def refresh():
                    try:
                        self.candles(config)
                        with self.lock:self.stream_history_errors.pop(key,None)
                    except Exception:
                        with self.lock:self.stream_history_errors[key]='Dhan candle refresh failed; retrying.'
                    finally:
                        with self.lock:self.stream_history_refresh.discard(key)
                threading.Thread(target=refresh,daemon=True,name='dhan-chart-history').start()
            error=self.stream_history_errors.get(key)
        if not fresh:
            raise ValueError(error or 'Dhan candle refresh in progress; live quote checked separately.')
        return self.forming(config,cached[1],now)

    def forming(self,config,rows,now):
        rows=rows or self.candles(config)
        current=[r for r in rows if r['timestamp']<=now<r['timestamp']+TIMEFRAMES[config['timeframe']]]
        if len(current)!=1: raise ValueError('Broker-verified Dhan forming OHLC unavailable.')
        return dict(current[0],host_open_verified=True)

    def order(self,symbol,qty,side,quote):
        meta=self.contract(symbol);tick=Decimal(str(meta['tick_size']))
        price=(Decimal(str(quote['ask' if side==1 else 'bid']))/tick).to_integral_value(
            rounding=ROUND_CEILING if side==1 else ROUND_FLOOR)*tick
        return dict(symbol=symbol,qty=qty,side=side,type=1,productType='MARGIN',
                    limitPrice=float(price),stopPrice=0,validity='IOC',offlineOrder=False)

    def validate_order(self,order):
        meta=self.contract(order['symbol']);qty=number(order['qty'],'Quantity',True)
        price=number(order['limitPrice'],'Limit price',True);tick=number(meta['tick_size'],'Tick',True)
        if qty!=int(qty) or int(qty)%meta['lot_size'] or order['side'] not in (1,-1) or order['type']!=1 or order['productType']!='MARGIN' or order.get('validity')!='IOC' or price%tick or order.get('stopPrice')!=0 or order.get('offlineOrder') is not False:
            raise ValueError('Whole-lot Dhan LIMIT IOC option order required.')

    def _account_rows(self,path):
        client=self.authenticated_client();rows=client.request('GET',path)
        if not isinstance(rows,list) or any(str(r.get('dhanClientId',''))!=str(client.client_id) for r in rows):
            raise PermissionError('Dhan account rows have missing or mixed ownership.')
        return rows

    def positions(self):
        return [dict(symbol=r['exchangeSegment']+':'+str(r['securityId']),netQty=whole(r['netQty'],'Position quantity'),
                     netAvg=float(r.get('costPrice',0)),productType=r['productType'],broker='DHAN')
                for r in self._account_rows('/positions')]

    def _order_row(self,r):
        status=STATES.get(r.get('orderStatus'))
        if status is None: raise ValueError('Unknown Dhan order status; reconciliation required.')
        qty=whole(r['quantity'],'Order quantity');filled=whole(r.get('filledQty',0),'Filled quantity')
        if not 0<=filled<=qty or qty<=0:raise ValueError('Invalid Dhan filled quantity.')
        if filled:number(r.get('averageTradedPrice'),'Average fill price',True)
        return dict(id=str(r['orderId']),symbol=r['exchangeSegment']+':'+str(r['securityId']),
                    side={'BUY':1,'SELL':-1}[r['transactionType']],qty=whole(r['quantity'],'Order quantity'),
                    filledQty=whole(r.get('filledQty',0),'Filled quantity'),tradedPrice=float(r.get('averageTradedPrice',0)),
                    productType=r['productType'],status=status,orderTag=r.get('correlationId'))

    def orders(self):
        import json,os
        raw=self._account_rows('/orders')
        client=self.service._client()
        for path in (self.service.folder/'dhan-strategy-intents').glob('*.json'):
            intent=json.loads(path.read_text());tag=intent['ticket']['correlationId']
            matches=[r for r in raw if r.get('correlationId')==tag]
            if intent['status']=='SUBMITTING' and not matches:
                # Reads by correlation recover lost acknowledgements; never POST again.
                try:
                    found=client.request('GET','/orders/external/'+tag)
                except Exception:continue
                if isinstance(found,dict) and found.get('orderId'):
                    if str(found.get('dhanClientId',''))!=str(client.client_id):
                        raise PermissionError('Dhan external order ownership mismatch.')
                    raw.append(found);matches=[found]
            if len(matches)>1:raise ValueError('Dhan correlation ownership ambiguous.')
            if len(matches)==1 and intent['status']=='SUBMITTING':
                intent.update(status='ACKNOWLEDGED',order_id=str(matches[0]['orderId']))
                temporary=path.with_suffix('.tmp')
                with temporary.open('w') as f:
                    os.chmod(temporary,0o600);json.dump(intent,f);f.flush();os.fsync(f.fileno())
                temporary.replace(path)
        return [self._order_row(r) for r in raw]

    def reconcile_position(self,symbol,qty):
        rows=[r for r in self.positions() if r['symbol']==symbol and r['netQty']]
        if qty==0 and not rows:return
        if len(rows)!=1 or rows[0]['productType']!='MARGIN' or rows[0]['netQty']!=qty:
            raise ValueError('Dhan position differs from exact owned quantity; exit blocked.')

    def preflight(self,order,config):
        self.validate_order(order);client=self.authenticated_client()
        self.reconcile_position(order['symbol'],0)
        if any(r['symbol']==order['symbol'] and r['status'] not in (1,2,5,7) for r in self.orders()):
            raise ValueError('Pending Dhan order blocks this contract.')
        import json
        for folder in ('dhan-strategy-intents','dhan-orders'):
            for path in (self.service.folder/folder).glob('*.json'):
                if json.loads(path.read_text()).get('status') in ('SUBMITTING','UNKNOWN'):
                    raise ValueError('Uncertain Dhan submission requires reconciliation before another entry.')
        quote=self.quote(order['symbol'])
        funds=client.request('GET','/fundlimit')
        if str(funds.get('dhanClientId'))!=str(client.client_id):raise PermissionError('Dhan funds ownership mismatch.')
        available=number(funds.get('availabelBalance',funds.get('availableBalance')),'Available funds')
        premium=Decimal(str(quote['ask']))*order['qty']
        if available<premium*Decimal('1.01'):raise ValueError('Dhan funds insufficient for premium plus reserve.')
        native=self._native(order,client)
        margin=client.request('POST','/margincalculator',{k:v for k,v in native.items() if k in
            ('dhanClientId','exchangeSegment','transactionType','quantity','productType','securityId','price','triggerPrice')})
        if number(margin.get('totalMargin'),'Margin')>min(available,number(margin.get('availableBalance',available),'Margin available balance')):
            raise ValueError('Dhan margin unavailable or insufficient.')

    def _native(self,order,client):
        meta=self.contract(order['symbol'])
        return dict(dhanClientId=client.client_id,correlationId=order.get('orderTag'),
                    transactionType='BUY' if order['side']==1 else 'SELL',exchangeSegment=meta['exchange_segment'],
                    securityId=meta['security_id'],quantity=int(order['qty']),productType='MARGIN',
                    orderType='LIMIT',validity='IOC',price=order['limitPrice'],triggerPrice=0,
                    disclosedQuantity=0,afterMarketOrder=False)

    def place(self,order):
        attempt={'post_started':False}
        try:
            return self._place_checked(order,attempt)
        except Exception as error:
            if attempt['post_started']:
                return dict(s='error',code=201,message='Dhan submission outcome is uncertain; reconcile the saved correlation ID.')
            return dict(s='error',code=400,message='Dhan preflight rejected before submission: '+str(error))

    def _place_checked(self,order,attempt):

        if not self.live_enabled():raise PermissionError('Dhan live capability disabled.')
        self.validate_order(order);client=self.authenticated_client()
        now=datetime.fromtimestamp(self.clock(),IST)
        if now.weekday()>4 or not 9*60+15<=now.hour*60+now.minute<15*60+30:
            raise ValueError('Dhan exchange session closed.')
        ips=client.request('GET','/ip/getIP')
        if self.service.egress() not in (ips.get('primaryIP'),ips.get('secondaryIP')):
            raise PermissionError('Server IP is not registered for this Dhan account.')
        # Existing runner persists intent before this function. Never resend a tag.
        tag=order.get('orderTag')
        if not isinstance(tag,str) or not 1<=len(tag)<=30:raise ValueError('Durable Dhan correlation ID required.')
        with self.service._submission_lock():
            journal=self.service.folder/'dhan-strategy-intents'
            journal.mkdir(mode=0o700,exist_ok=True)
            import json,os
            path=journal/(hashlib.sha256(tag.encode()).hexdigest()+'.json')
            if path.exists():raise ValueError('Dhan correlation ID already submitted; reconcile without retry.')
            quote=self.quote(order['symbol'])
            if order['side']==-1:self.reconcile_position(order['symbol'],order['qty'])
            else:self.preflight(order,{})
            # Preserve the exact previewed limit; a moved market is not silently chased.
            if order['side']==1 and quote['ask']>order['limitPrice'] or order['side']==-1 and quote['bid']<order['limitPrice']:
                raise ValueError('Dhan executable quote moved beyond the order limit.')
            native=self._native(order,client)
            with path.open('x') as f:
                os.chmod(path,0o600);json.dump(dict(status='SUBMITTING',ticket=native),f);f.flush();os.fsync(f.fileno())
            attempt['post_started']=True
            try:result=client.request('POST','/orders',native)
            except DhanAPIError as error:
                if error.definitive_rejection:
                    with path.open('w') as f:
                        json.dump(dict(status='REJECTED',ticket=native,reason=str(error)),f);f.flush();os.fsync(f.fileno())
                    return dict(s='error',code=400,message=str(error))
                return dict(s='error',code=201,message='Dhan acknowledgement unknown; reconcile correlation ID.')
            except Exception:return dict(s='error',code=201,message='Dhan acknowledgement unknown; reconcile correlation ID.')
            if not isinstance(result,dict) or not result.get('orderId'):
                return dict(s='error',code=201,message='Dhan acknowledgement unknown; reconcile correlation ID.')
            with path.open('w') as f:
                json.dump(dict(status='ACKNOWLEDGED',ticket=native,order_id=str(result['orderId'])),f);f.flush();os.fsync(f.fileno())
            return dict(s='ok',id=str(result['orderId']))

    def cancel(self,order_id):
        if not self.live_enabled():raise PermissionError('Dhan live capability disabled.')
        rows=[r for r in self.orders() if r['id']==str(order_id)]
        if len(rows)!=1 or not rows[0].get('orderTag'):
            raise PermissionError('Dhan cancellation ownership unavailable.')
        import json
        tag=rows[0]['orderTag']
        path=self.service.folder/'dhan-strategy-intents'/(hashlib.sha256(tag.encode()).hexdigest()+'.json')
        if not path.exists():raise PermissionError('Dhan order is not owned by this strategy adapter.')
        return self.authenticated_client().request('DELETE','/orders/'+str(order_id))
