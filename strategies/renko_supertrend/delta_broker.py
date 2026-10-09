"""Independent Delta market stream and native broker adapter for shared Renko.

Construction is inert. Public stream subscription does not authorize execution.
REST verifies owned order fills; feed messages never manufacture fills.
"""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import threading
import time

from .delta_contracts import RESOLUTIONS, PRODUCT, FUTURES_PRODUCT, FUTURES_ROUTE, perpetual_contract, contract_metadata, option_contract, position, owned_order, whole
from .delta_execution import Execution
from .runner import Broker as FyersRenkoBroker
from strategies.ema_crossover.runner import TIMEFRAMES
HISTORY_LOCK=threading.RLock()


class Broker:
    observe = FyersRenkoBroker.observe
    forming = FyersRenkoBroker.forming
    live_price = FyersRenkoBroker.live_price

    def __init__(self, delta, history_path, on_tick=None):
        self.delta = delta; self.execution = Execution(delta)
        self.path = Path(history_path)
        self.lock = threading.RLock(); self.connected = False
        self.socket = None; self.thread = None; self.stopping = threading.Event()
        self.generation = 0; self.stream_error = None; self.account_identity = None
        self.ticks = {}; self.quotes = {}; self.forming_bars = {}; self.frame_seconds = {}
        self.symbols = set(); self.on_tick = on_tick
        self.history_lock = HISTORY_LOCK; self.history_cache = {}; self.resolved_contracts={}

    def live_enabled(self): return self.delta._gate()

    def session_policy(self, config):
        self.underlying(config['underlying'])
        deadline = config.get('session_deadline')
        if config.get('carry_policy') == 'DAILY_SQUARE_OFF' and not deadline: raise ValueError('Select a daily strategy cutoff in IST.')
        return dict(session_open='00:00',session_deadline=deadline,session_segment='DELTA_INDIA',
                    session_source='CONTINUOUS_CRYPTO' if config.get('carry_policy') == 'CONTINUOUS' else 'EXPLICIT_USER_POLICY',seven_day_session=True)

    def _master_row(self, product):
        row = [''] * 17
        row[0] = str(product['id']); row[1] = product['symbol']; row[3] = '1'
        row[4] = str(product['tick_size']); row[9] = product['symbol']; row[13] = product['underlying']
        if product['contract_type'] in ('call_options','put_options'):
            meta = option_contract(product,self.delta.clock())
            row[8] = str(meta['expiry_epoch']); row[15] = str(meta['strike']); row[16] = meta['option_type']
        else: row[16] = 'XX'
        return row

    def rows(self, segment):
        return [self._master_row(p) for p in self.delta.catalog()['instruments']
                if p.get('contract_type') in ('call_options','put_options')
                and p.get('state')=='live' and p.get('trading_status')=='operational'
                and datetime.fromisoformat(p['settlement_time'].replace('Z','+00:00')).timestamp()>self.delta.clock()]

    def underlying(self, symbol):
        product = self.delta.product(symbol)
        if product.get('contract_type') != 'perpetual_futures':
            raise ValueError('Select a listed Delta perpetual as the Renko signal source.')
        return self._master_row(product)

    def host_tick_size(self, symbol):
        self.underlying(symbol)
        tick = float(self.delta.product(symbol)['tick_size'])
        if not math.isfinite(tick) or tick<=0: raise ValueError('Verified Delta host tick required.')
        return tick

    def contract(self, symbol): return contract_metadata(self.delta.product(symbol),self.delta.clock())

    def route_availability(self, config):
        asset = self.underlying(config['underlying'])[13]
        if config.get('execution_route') == FUTURES_ROUTE:
            meta = perpetual_contract(self.delta.product(config['underlying']))
            return dict(available=True,execution_route=FUTURES_ROUTE,contract=meta,
                        message='Exact Delta perpetual; bullish LONG / bearish SHORT; full notional collateral reserve, broker leverage unchanged.')
        rows = self.rows('DELTA_OPTIONS')
        counts = {kind:sum(r[13]==asset and r[16]==kind for r in rows) for kind in ('CE','PE')}
        return dict(available=all(counts.values()),contract_counts=counts,
                    message='Delta nearest-expiry ATM long Call/Put; no perpetual execution fallback.')

    def validate_config(self, config):
        self.session_policy(config)
        if not self.route_availability(config)['available']:raise ValueError('No currently listed Delta Call/Put pair for this signal instrument; no perpetual execution fallback.')
        if config.get('mode')=='PAPER':
            identity='PAPER-PUBLIC-DELTA-INDIA'
        else:
            identity = self.execution.authenticate(); self.account_identity = identity
            self.positions(); self.orders()
        self.subscribe(config['underlying'],TIMEFRAMES[config['timeframe']])
        self.warm_options(config)
        return dict(broker='DELTA_INDIA',account_identity=identity,underlying=config['underlying'],
                    execution='Exact perpetual LONG/SHORT' if config.get('execution_route')==FUTURES_ROUTE else 'Nearest-expiry ATM long Call/Put',order_type='Marketable LIMIT IOC',
                    product=FUTURES_PRODUCT if config.get('execution_route')==FUTURES_ROUTE else PRODUCT,price_source='Perpetual last-trade candles',
                    risk='Native quote/settlement currency, whole contracts, reduce-only exits. IOC can fill partially. Daily cutoff is an explicit policy, not an exchange close. Costs require native fee evidence.')

    def authenticated_client(self):
        account = self.execution.authenticate()
        if self.account_identity and account!=self.account_identity: raise ValueError('Delta account changed.')
        return self.delta

    def subscribe(self, symbol, seconds=None):
        with self.lock:
            self.symbols.add(symbol)
            if seconds: self.frame_seconds[(symbol,seconds)] = True
            socket = self.socket if self.connected else None
        if socket: self.subscribe_all()

    def subscribe_all(self):
        with self.lock:
            if not self.connected or not self.socket: return
            channels = [dict(name='ob_l1',symbols=sorted(self.symbols))]
            for timeframe,resolution in RESOLUTIONS.items():
                symbols = sorted(s for s,n in self.frame_seconds if n==TIMEFRAMES[timeframe])
                if symbols: channels.append(dict(name='candlestick_'+resolution,symbols=symbols))
            self.socket.send(json.dumps(dict(type='subscribe',payload=dict(channels=channels))))

    def ingest(self, message, received=None):
        received = self.delta.clock() if received is None else received
        if not isinstance(message,dict): return
        symbol = message.get('sy') or message.get('symbol'); kind = message.get('type')
        if symbol not in self.symbols: return
        try:
            stamp = float(message['ts'])/1e6
            if not math.isfinite(stamp) or not 0<=received-stamp<=15: return
            with self.lock:
                if kind=='ob_l1':
                    bid,ask = float(message['bp']),float(message['ap'])
                    if not all(math.isfinite(v) for v in (bid,ask)) or not 0<bid<=ask: return
                    if stamp<(self.quotes.get(symbol) or {}).get('exchange_at',0): return
                    self.quotes[symbol]=dict(bid=bid,ask=ask,exchange_at=stamp,received_at=received)
                    return
                if not str(kind).startswith('candlestick_'): return
                resolution = message.get('res') or str(kind).split('_',1)[1]
                timeframe = next((k for k,v in RESOLUTIONS.items() if v==resolution),None)
                if not timeframe: return
                seconds=TIMEFRAMES[timeframe]; opening=float(message['cst'])/1e6 if message.get('cst') is not None else int(stamp)//seconds*seconds
                if opening!=int(stamp)//seconds*seconds: return
                values={k:float(message[key]) for k,key in [('open','o'),('high','h'),('low','l'),('close','c')]}
                if not all(math.isfinite(v) and v>0 for v in values.values()) or values['high']<max(values['open'],values['close']) or values['low']>min(values['open'],values['close']): return
                volume=None if message.get('v') is None else float(message['v'])
                if volume is not None and (not math.isfinite(volume) or volume<0): return
                old=self.ticks.get(symbol)
                if old and stamp<old['exch_feed_time']: return
                row=dict(timestamp=opening,**values,volume=volume,is_forming=True,host_open_verified=True,stream_exchange_at=stamp)
                self.forming_bars[(symbol,seconds,opening)]=row
                raw=dict(symbol=symbol,ltp=values['close'],exch_feed_time=stamp,received_at=received)
                self.ticks[symbol]=raw
                # Keep a bounded forming cache; completed evidence comes from REST.
                if len(self.forming_bars)>200: self.forming_bars.pop(next(iter(self.forming_bars)))
            if self.on_tick: self.on_tick(raw)
        except (ValueError,TypeError,KeyError,OverflowError): return

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive(): return
            self.stopping.clear()
            def run():
                import websocket,certifi
                while not self.stopping.is_set():
                    def opened(socket):
                        with self.lock:
                            self.connected=True; self.generation+=1; self.quotes={}; self.ticks={}; self.forming_bars={}; self.stream_error=None
                        socket.send(json.dumps(dict(type='enable_heartbeat'))); self.subscribe_all()
                    def closed(*args):
                        with self.lock: self.connected=False
                    def failed(*args):
                        with self.lock: self.connected=False; self.stream_error='Delta public stream unavailable.'
                    def message(socket, text):
                        try: self.ingest(json.loads(text))
                        except (ValueError,TypeError): pass
                    self.socket=websocket.WebSocketApp('wss://public-socket.india.delta.exchange',on_open=opened,on_message=message,on_error=failed,on_close=closed)
                    self.socket.run_forever(ping_interval=20,ping_timeout=10,sslopt={'ca_certs':certifi.where()})
                    self.connected=False
                    self.stopping.wait(2)
            self.thread=threading.Thread(target=run,daemon=True,name='delta-renko-public-stream'); self.thread.start()

    def stop(self):
        self.stopping.set()
        with self.lock:
            self.connected=False
            socket=self.socket
        if socket: socket.close()

    def stream_status(self):
        return dict(connected=self.connected,generation=self.generation,error=self.stream_error)

    def tick(self, symbol):
        self.subscribe(symbol)
        with self.lock: raw=deepcopy(self.ticks.get(symbol))
        now=self.delta.clock()
        if not self.connected or not raw or any(not 0<=now-raw[k]<=15 for k in ('exch_feed_time','received_at')):
            raise ValueError('Fresh Delta backend candle stream required.')
        return raw

    def quote(self, symbol):
        self.subscribe(symbol)
        with self.lock: quote=deepcopy(self.quotes.get(symbol))
        now=self.delta.clock()
        if not self.connected or not quote or any(not 0<=now-quote[k]<=15 for k in ('exchange_at','received_at')):
            raise ValueError('Fresh executable Delta backend quote required.')
        return quote

    def candles(self, config):
        symbol=config['underlying']; timeframe=config['timeframe']; resolution=RESOLUTIONS[timeframe]
        seconds=TIMEFRAMES[timeframe]; self.subscribe(symbol,seconds)
        with self.history_lock:
            key=(symbol,timeframe,config.get('history_start')); now=self.delta.clock(); cached=self.history_cache.get(key)
            if cached and now-cached[0]<5: return deepcopy(cached[1])
            product=self.delta.product(symbol)
            file=self.path/(symbol+'-'+resolution+'.json')
            saved=json.loads(file.read_text()) if file.exists() else dict(product_id=product['id'],rows=[])
            if saved['product_id']!=product['id']: raise ValueError('Saved Delta product identity changed.')
            rows={r['timestamp']:r for r in saved['rows']}
            # Keep the same durable initialization anchor. Refresh completed revisions
            # as well as forming bars; never truncate to a moving 500-candle seed.
            requested=int(config.get('history_start') or (int(now)-seconds*500))
            ranges=[(int(max(rows)-seconds*3) if rows else requested,int(now))]
            if rows and requested<min(rows): ranges.insert(0,(requested,int(min(rows))))
            raw=[]
            for begin,end in ranges:
                while begin<end:
                    finish=min(end,begin+seconds*499)
                    batch=self.delta._get('/v2/history/candles',dict(symbol=symbol,resolution=resolution,start=begin,end=finish))['result']
                    if not isinstance(batch,list): raise ValueError('Delta host history unavailable.')
                    raw.extend(batch); begin=finish
            seen={}
            for item in raw:
                row=dict(timestamp=float(item['time']),**{k:float(item[k]) for k in ('open','high','low','close')},volume=None if item.get('volume') is None else float(item['volume']))
                if not all(math.isfinite(row[k]) and row[k]>0 for k in ('timestamp','open','high','low','close')) or row['high']<max(row['open'],row['close']) or row['low']>min(row['open'],row['close']) or row['volume'] is not None and (not math.isfinite(row['volume']) or row['volume']<0): raise ValueError('Invalid Delta host OHLCV.')
                if row['timestamp'] in seen and seen[row['timestamp']]!=row: raise ValueError('Conflicting Delta history timestamps.')
                seen[row['timestamp']]=row
            rows.update(seen); data=sorted(rows.values(),key=lambda r:r['timestamp'])
            if len(data)>150000: raise ValueError('Delta durable host history limit reached; explicit new history required.')
            self.path.mkdir(parents=True,exist_ok=True)
            temp=file.with_suffix('.tmp'); temp.write_text(json.dumps(dict(product_id=product['id'],rows=data),allow_nan=False)); os.chmod(temp,0o600); os.replace(temp,file)
            data=[dict(r,is_forming=r['timestamp']+seconds>now) for r in data]
            self.observe(config,data); self.history_cache[key]=(now,data)
            return deepcopy(data)

    def resolve(self, config, direction):
        if direction not in ('BULLISH','BEARISH'):raise ValueError('Explicit signal direction required.')
        if config.get('execution_route') == FUTURES_ROUTE:
            meta = perpetual_contract(self.delta.product(config['underlying']))
            meta['entry_side'] = 1 if direction == 'BULLISH' else -1
            self.subscribe(meta['symbol']);self.resolved_contracts[meta['symbol']]=meta
            return meta
        resolved=self.delta.chart_option(config['underlying'],'BUY' if direction=='BULLISH' else 'SELL')
        meta=self.contract(resolved['symbol'])
        if meta['expiry_epoch']-self.delta.clock() <= 60:raise ValueError('Resolved option is inside its exact expiry protection window.')
        self.subscribe(meta['symbol'])
        self.resolved_contracts[meta['symbol']]=meta
        return meta

    def warm_options(self, config):
        for direction in ('BULLISH','BEARISH'):
            try: self.resolve(config,direction)
            except ValueError: pass

    def positions(self):
        rows=self.delta.account({'refresh':True})['positions']; result=[]
        for row in rows:
            try: result.append(position(row,self.delta.product(row['product_symbol']),self.delta.clock()))
            except ValueError:
                result.append(dict(symbol=row.get('product_symbol'),netQty=row.get('size'),netAvg=row.get('entry_price'),productType='UNSUPPORTED_DELTA',broker='DELTA_INDIA'))
        return result

    def orders(self):
        self.authenticated_client()
        active=self.execution.active_orders(); rows={}
        for row in active:
            symbol=row.get('product_symbol') or (row.get('product') or {}).get('symbol')
            if not symbol:
                symbol=next((p['symbol'] for p in self.delta.catalog()['instruments'] if p['id']==row.get('product_id')),None)
            if not symbol: raise ValueError('External Delta order product cannot be resolved.')
            rows[str(row['id'])]=dict(id=str(row['id']),symbol=symbol,side=1 if row['side']=='buy' else -1,qty=whole(row['size'],'Order size',True),filledQty=whole(row['size'],'Order size')-whole(row['unfilled_size'],'Unfilled size'),productType=PRODUCT,status=6,orderTag=row.get('client_order_id'))
        for token,order in list(self.delta.live['orders'].items()):
            if order.get('strategy')!='RENKO_SUPERTREND_V1': continue
            if order['status'] not in ('closed','cancelled','REJECTED'): order=self.delta.reconcile({'request_id':token})
            row=owned_order(order,self.execution.account_identity); rows[row['id']]=row
        return list(rows.values())

    def reconcile_position(self, symbol, size):
        product=self.delta.product(symbol)
        if self.delta._position(product['id'])!=size: raise ValueError('Delta broker quantity differs from owned exposure; no closing order sent.')

    def order(self, symbol, qty, side, quote):
        meta=self.contract(symbol)
        return dict(symbol=symbol,qty=qty,side=side,productType=meta['product'],type=1,limitPrice=0,stopPrice=0,offlineOrder=False)

    def validate_order(self, order):
        meta=self.contract(order['symbol'])
        whole(order['qty'],'Order size',True)
        if order['side'] not in (1,-1) or order['productType']!=meta['product'] or order['type']!=1: raise ValueError('Exact Delta contract IOC order required.')

    def preflight(self, order, config):
        self.validate_order(order); self.authenticated_client(); quote=self.quote(order['symbol'])
        if (quote['ask']-quote['bid'])/quote['ask']>.03: raise ValueError('Entry spread exceeds 3%.')
        self.reconcile_position(order['symbol'],0)
        if any(r['symbol']==order['symbol'] and r['status'] not in (1,2,5,7) for r in self.orders()): raise ValueError('Existing Delta order blocks entry.')
        wallets=self.delta._private('GET','/v2/wallet/balances')['result']; meta=self.contract(order['symbol'])
        available=[Decimal(str(w['available_balance'])) for w in wallets if (w.get('asset_symbol') or (w.get('asset') or {}).get('symbol'))==meta['settlement_currency']]
        if meta['product']==FUTURES_PRODUCT:perpetual_contract(self.delta.product(order['symbol']))
        fee=meta['taker_commission_rate'] if meta['product']==FUTURES_PRODUCT else .035
        if len(available)!=1 or not available[0].is_finite() or available[0]<Decimal(str(order['qty']*meta['quantity_multiplier']*quote['ask']*(1+fee*1.18+.01))):
            raise ValueError('Verified same-currency balance must cover full premium/notional, fees/GST and 1% reserve; broker leverage is unchanged.')

    def place(self, order):
        self.validate_order(order); self.authenticated_client()
        result=self.execution.submit(order['symbol'],order['qty'],order['side'],self.quote(order['symbol']),order['orderTag'],getattr(self,'signal_symbol',None),getattr(self,'execution_reason','RENKO'),reduce_only=order.get('reduce_only'))
        if result['status']=='REJECTED': return dict(s='error',code=400,message='Delta rejected native IOC order.')
        if result.get('order_id'): return dict(s='ok',id=str(result['order_id']))
        return dict(s='error',code=201,message='Delta acknowledgement unknown; reconcile persisted tag.')

    def cancel(self, order_id):
        matches=[token for token,o in self.delta.live['orders'].items() if str(o.get('order_id'))==str(order_id) and o.get('strategy')=='RENKO_SUPERTREND_V1']
        if len(matches)!=1: raise ValueError('Delta cancellation ownership ambiguous.')
        return self.execution.cancel(matches[0])
