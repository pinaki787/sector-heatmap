"""FYERS adapter: current masters, streaming prices and fresh order preflight."""
import csv
import hashlib
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math
import os
from pathlib import Path
import threading
import time
import requests
from fyers_apiv3.FyersWebsocket import data_ws
from sector_heatmap.config import load_config
from sector_heatmap.fyers_execution import _current_client, available_funds
from sector_heatmap.market_data import configure_websocket_ca_bundle
from sector_heatmap.fyers_history import account_read
from .valuation import amount, multiplier


class IndependentDataSocket(data_ws.FyersDataSocket):
    """The SDK base class is a process singleton; runner ownership must be isolated."""
    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def reset_feed_state(self):
        # Topic IDs belong to one transport connection. The FYERS SDK retains
        # these maps on reconnect and checks scrips before indices, so a reused
        # topic ID can decode index fields as stock fields (including time).
        self.scrips_sym = {}
        self.index_sym = {}
        self.dp_sym = {}
        self.resp = {}
        self.literesp = {}


class FyersBroker:
    def __init__(self, master_dir, fetch_candles, select_atm, on_tick=None):
        self.master_dir, self.fetch_candles, self.select_atm = Path(master_dir), fetch_candles, select_atm
        self.socket, self.connected, self.ticks, self.symbols = None, False, {}, set()
        self.stream_generation = 0
        self.lock = threading.Lock()
        self.history_cache = {}
        self.subscription_lock = threading.Lock()
        self.stream_error = None
        self.stream_generation = 0
        self.last_subscribe = {}
        self.account_identity = None
        self.on_tick = on_tick
        self.instrument_masters = {}

    def live_enabled(self):
        return os.getenv('SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS') == '1'

    def rows(self, segment):
        path = self.master_dir / (segment + '.csv')
        if not path.exists() or time.time()-path.stat().st_mtime > 86400:
            raise ValueError('Current FYERS master cache required (less than 24 hours old). Refresh EMA Band master cache.')
        with path.open() as f:
            return list(csv.reader(f))

    def underlying(self, symbol):
        exchange = symbol.split(':')[0]
        segment = 'MCX_COM' if exchange == 'MCX' else exchange + '_CM'
        row = next((r for r in self.rows(segment) if len(r)>16 and r[9]==symbol), None)
        if row is None or (exchange=='MCX' and row[16]!='XX'):
            raise ValueError('Underlying is not an eligible current FYERS master instrument.')
        return row

    def contract(self, symbol):
        segment = 'MCX_COM' if symbol.startswith('MCX:') else symbol.split(':')[0]+'_FO'
        row = next((r for r in self.rows(segment) if len(r)>16 and r[9]==symbol and r[16] in {'CE','PE'}), None)
        if not row or float(row[8]) <= time.time():
            raise ValueError('Option contract is missing from current master or expired.')
        raw_lot, tick = float(row[3]), float(row[4])
        if not math.isfinite(raw_lot) or not raw_lot.is_integer() or raw_lot<1 or not math.isfinite(tick) or tick<=0:
            raise ValueError('Invalid FYERS lot/tick metadata.')
        lot = int(raw_lot)
        result = {'lot_size':lot,'tick_size':tick,'symbol':symbol}
        # CSV lacks qtyMultiplier. Validate named JSON metadata for every exchange.
        cached = self.instrument_masters.get(segment)
        if cached is None or time.time()-cached[0] > 900:
            try:
                response = requests.get(f'https://public.fyers.in/sym_details/{segment}_sym_master.json', timeout=10)
                response.raise_for_status()
                records = response.json()
                if not isinstance(records, dict):
                    raise ValueError('Invalid master response')
            except Exception as error:
                raise ValueError(f'FYERS {segment} valuation metadata unavailable; retry after the master service recovers.') from error
            self.instrument_masters[segment] = (time.time(), records)
        record = self.instrument_masters[segment][1].get(symbol, {})
        try:
            matches = (record.get('symTicker') == symbol
                       and float(record.get('minLotSize', 0)) == lot
                       and float(record.get('tickSize', 0)) == tick
                       and float(record.get('expiryDate', 0)) == float(row[8])
                       and record.get('optType') == row[16]
                       and float(record.get('strikePrice', -1)) == float(row[15])
                       and str(record.get('fyToken')) == row[0])
            if not matches:
                raise ValueError('Metadata mismatch')
            result['quantity_multiplier'] = record.get('qtyMultiplier')
            result['quantity_multiplier'] = multiplier(result)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError(f'FYERS valuation metadata missing or JSON/CSV masters disagree for {symbol}; refresh masters before entry.') from error
        return result

    def validate_config(self, c):
        row = self.underlying(c['underlying'])
        with self.lock:
            self.symbols.add(c['underlying'])
        client = _current_client()
        profile = account_read(client, 'get_profile')
        if not isinstance(profile,dict) or profile.get('s')!='ok':
            raise ValueError('FYERS authentication failed. Refresh the broker session.')
        account = (profile.get('data') or {}).get('fy_id')
        if not account:
            raise ValueError('FYERS profile did not provide a broker account identity.')
        self.account_identity = hashlib.sha256(str(account).encode()).hexdigest()
        # Preview is read-only, including outside market hours.
        if c.get('mode')=='LIVE':
            self.orders()
            self.positions()
        return dict(broker='FYERS', account_identity=self.account_identity, underlying=c['underlying'], description=row[1], execution='Nearest-expiry ATM CE for bullish / PE for bearish',
                    order_type='MARKET (FYERS MPP)', product='MARGIN', exits='Call exits on completed RSI below its selected moving average; put exits on completed RSI above its selected moving average',
                    risk='Optional limits apply only when set: premium cap bounds paid premium; daily budget excludes fees. Blank limits mean no strategy-level money cap. RSI/MA exits require completed candles and the running server. No intrabar premium stop or timed square-off; positions may carry between sessions. MARKET requests are subject to FYERS MPP conversion; fills are not guaranteed. Optional premium limits check the current quote and are not guaranteed fill-price caps.')

    def stream_status(self):
        with self.lock:
            now=time.time()
            freshness={}
            for symbol,(raw,received) in self.ticks.items():
                stamp=raw.get('exch_feed_time',raw.get('last_traded_time'))
                try:exchange=float(stamp);age=now-exchange if math.isfinite(exchange) else None
                except (TypeError,ValueError):exchange=age=None
                freshness[symbol]=dict(type=raw.get('type'),received_age_seconds=now-received,exchange_at=exchange,exchange_age_seconds=age)
            return dict(connected=self.connected, generation=getattr(self,"connection_epoch",0), error=self.stream_error, subscribed=sorted(self.symbols),freshness=freshness,revision='fyers-topic-recovery-v1')

    def subscribe_all(self):
        # The SDK resolves symbols over HTTP without a timeout. Never perform
        # that work while a strategy/status reader is holding its state lock.
        # One worker per adapter prevents repeated ticks from leaking threads.
        if not self.subscription_lock.acquire(blocking=False):
            return
        def subscribe():
            try:
                with self.lock:
                    socket=self.socket
                    generation=self.stream_generation
                    symbols=sorted(self.symbols)
                    if not socket or not self.connected:
                        return
                    now=time.time()
                    self.last_subscribe.update({symbol:now for symbol in symbols})
                socket.subscribe(symbols=symbols,data_type='SymbolUpdate')
            except Exception:
                with self.lock:
                    if generation == self.stream_generation:
                        self.stream_error='FYERS subscription failed; awaiting automatic retry.'
            finally:
                self.subscription_lock.release()
        threading.Thread(target=subscribe,daemon=True,name='ema-cross-subscriptions').start()

    def start(self):
        if self.socket:
            return
        configure_websocket_ca_bundle()
        token = load_config().get('FYERS_ACCESS_TOKEN','')
        self.stream_generation += 1
        generation=self.stream_generation
        def on_message(msg):
            if not isinstance(msg,dict) or generation != self.stream_generation:
                return
            if msg.get('s') == 'error':
                on_error(msg)
                return
            if msg.get('symbol'):
                with self.lock:
                    symbol=msg['symbol']
                    # Keep fields from partial updates; their exchange timestamp is still checked.
                    previous=self.ticks.get(symbol, ({},0))[0]
                    if 'bid_price' in msg:
                        msg={**msg,'_bid_received_at':time.time(),'_bid_exchange_at':msg.get('exch_feed_time',msg.get('last_traded_time'))}
                    self.ticks[symbol] = ({**previous,**msg},time.time())
                    self.stream_error=None
                    merged=self.ticks[symbol][0]
                if self.on_tick:
                    self.on_tick(merged)
        def on_connect():
            if generation != self.stream_generation:
                return
            # Authentication callback runs before our subscriptions/snapshots.
            self.socket.reset_feed_state()
            with self.lock:
                self.connected=True
                self.connection_epoch = getattr(self,"connection_epoch",0)+1
                self.ticks={}
                self.stream_error=None
            self.subscribe_all()
        def on_error(message):
            if generation != self.stream_generation:
                return
            # Never expose arbitrary SDK messages, which can contain credentials.
            code=message.get('code') if isinstance(message,dict) else None
            code=str(code) if isinstance(code,(int,float)) else 'unavailable'
            with self.lock:
                self.stream_error='FYERS stream error; code '+code
            # Subscription errors are not transport closes. Freshness still blocks stale data.
        def on_close(*args):
            if generation != self.stream_generation:
                return
            with self.lock:
                self.connected=False
                self.ticks={}
                self.stream_error='FYERS streaming connection closed; awaiting reconnect.'
        self.socket=IndependentDataSocket(access_token=token,litemode=False,write_to_file=False,reconnect=True,
                                          on_message=on_message,on_connect=on_connect,on_error=on_error,on_close=on_close)
        threading.Thread(target=self.socket.connect,daemon=True,name='ema-cross-quotes').start()

    def stop(self):
        with self.lock:
            self.stream_generation += 1
            socket,self.socket=self.socket,None
            self.connected=False
            self.ticks={}
            self.symbols=set()
            self.last_subscribe={}
        if socket:
            socket.close_connection()

    def tick(self,symbol):
        now=time.time()
        with self.lock:
            new=symbol not in self.symbols
            self.symbols.add(symbol)
            connected=self.connected
            item=self.ticks.get(symbol)
            error=self.stream_error
            retry=now-self.last_subscribe.get(symbol,0)>=30
        stamp=item[0].get('exch_feed_time',item[0].get('last_traded_time')) if item else None
        try:exchange_fresh=stamp is not None and math.isfinite(float(stamp)) and abs(now-float(stamp))<=60
        except (TypeError,ValueError):exchange_fresh=False
        if connected and (new or ((not item or now-item[1]>15 or not exchange_fresh) and retry)):
            self.subscribe_all()
        if not connected:
            raise ValueError(f'FYERS stream disconnected for {symbol}. {error or "Waiting for connection."}')
        if not item:
            raise ValueError(f'FYERS stream has no tick for {symbol}; subscription requested. {error or ""}'.strip())
        if now-item[1]>15:
            raise ValueError(f'FYERS stream receive age exceeds 15 seconds for {symbol}. {error or "Awaiting fresh tick."}')
        raw=item[0]
        stamp=raw.get('exch_feed_time',raw.get('last_traded_time'))
        if not exchange_fresh:
            raise ValueError(f'FYERS tick has a missing/stale exchange timestamp: {symbol}.')
        return raw

    def quote(self,symbol):
        raw=self.tick(symbol)
        bid,ask=float(raw.get('bid_price',0)),float(raw.get('ask_price',0))
        if not all(math.isfinite(v) for v in (bid,ask)) or not 0<bid<=ask:
            raise ValueError('Option bid/ask missing or crossed.')
        with self.lock:
            item=self.ticks.get(symbol)
            received=item[1] if item and item[0] is raw else None
        stamp=raw.get('_bid_exchange_at')
        try:stamp=float(stamp) if stamp is not None else None
        except (TypeError,ValueError):stamp=None
        return dict(bid=bid,ask=ask,received_at=raw.get('_bid_received_at') if received is not None else None,exchange_at=stamp)

    def candles(self,c):
        key=(c['underlying'],c['timeframe'])
        cached=self.history_cache.get(key)
        if cached and time.time()-cached[0]<1:
            return cached[1]
        data=self.fetch_candles(_current_client(),*key,include_forming=True)[-500:]
        self.history_cache[key]=(time.time(),data)
        return data

    def resolve(self,c,direction):
        row=self.underlying(c['underlying'])
        tick=self.tick(c['underlying'])
        spot=float(tick.get('ltp',0))
        if not math.isfinite(spot) or spot<=0:
            raise ValueError('Underlying spot unavailable.')
        segment='MCX_COM' if c['underlying'].startswith('MCX:') else c['underlying'].split(':')[0]+'_FO'
        result=self.select_atm(self.rows(segment),row[13],direction,spot,time.time())
        return {**result,**self.contract(result['symbol'])}

    def order(self,symbol,qty,side,quote):
        self.contract(symbol)
        # FYERS applies MPP to API MARKET requests; do not send a local limit price.
        return dict(symbol=symbol,qty=qty,type=2,side=side,productType='MARGIN',limitPrice=0,stopPrice=0,
                    validity='DAY',disclosedQty=0,offlineOrder=False)

    def validate_order(self,order):
        meta=self.contract(order['symbol'])
        if order['qty']<=0 or order['qty']%meta['lot_size'] or order['side'] not in (1,-1) or order['productType']!='MARGIN' or order['type']!=2:
            raise ValueError('Invalid whole-lot MARKET option order.')
        if order['limitPrice'] != 0 or order.get('stopPrice') != 0 or order.get('offlineOrder') is not False:
            raise ValueError('MARKET requests require zero limit/stop prices and regular-session routing.')

    def positions(self):
        r=account_read(_current_client(), 'positions')
        if not isinstance(r,dict) or r.get('s')!='ok' or not isinstance(r.get('netPositions'),list):
            raise ValueError('FYERS positions unavailable.')
        return r['netPositions']

    def orders(self):
        r=account_read(_current_client(), 'orderbook')
        if not isinstance(r,dict) or r.get('s')!='ok' or not isinstance(r.get('orderBook'),list):
            raise ValueError('FYERS orderbook unavailable.')
        return r['orderBook']

    def reconcile_position(self,symbol,qty):
        rows=[r for r in self.positions() if r.get('symbol')==symbol and float(r.get('netQty',0))!=0]
        if qty==0 and not rows:
            return
        if len(rows)!=1 or rows[0].get('productType')!='MARGIN' or float(rows[0].get('netQty',0))!=qty:
            raise ValueError('Broker position differs from this runner’s confirmed quantity. Manual reconciliation required; no SELL sent.')

    def preflight(self,order,c):
        self.validate_order(order)
        quote=self.quote(order['symbol'])
        if (quote['ask']-quote['bid'])/quote['ask']>0.03:
            raise ValueError('Entry spread exceeds 3%.')
        if any(r.get('symbol')==order['symbol'] and float(r.get('netQty',0))!=0 for r in self.positions()):
            raise ValueError('Existing position in the same option contract blocks entry; external positions are never adopted.')
        if any(r.get('symbol')==order['symbol'] and int(r.get('status',0)) not in {1,2,5,7} for r in self.orders()):
            raise ValueError('Outstanding order in the same option contract blocks entry.')
        # FYERS uses one shared Available Balance across equity and MCX.
        # Select only that limit row, never sum the non-additive fund-limit rows.
        funds=account_read(_current_client(), 'funds')
        balance=available_funds(funds)
        premium = amount(self.contract(order['symbol']), order['qty'], quote['ask'])
        if not math.isfinite(balance) or balance<premium*1.01:
            raise ValueError('Insufficient available funds for option premium plus 1% reserve.')
        token=load_config().get('FYERS_ACCESS_TOKEN','')
        response=requests.post('https://api-t1.fyers.in/api/v3/multiorder/margin',headers={'Authorization':token},json={'data':[order]},timeout=10)
        response.raise_for_status()
        margin=response.json()
        data=margin.get('data',margin)
        if margin.get('s')!='ok':
            raise ValueError('FYERS margin validation failed.')
        required=float(data.get('margin_total',data.get('margin_new_order',float('nan'))))
        if not math.isfinite(required) or required<0 or required>balance:
            raise ValueError('FYERS margin unavailable or exceeds available funds.')

    def authenticated_client(self):
        client=_current_client()
        profile=account_read(client, 'get_profile')
        account=(profile.get('data') or {}).get('fy_id') if isinstance(profile,dict) and profile.get('s')=='ok' else None
        if not account or hashlib.sha256(str(account).encode()).hexdigest()!=self.account_identity:
            raise ValueError('FYERS account changed or identity unavailable; execution blocked.')
        return client

    def place(self,order):
        if not self.live_enabled():
            raise ValueError('Live gate is disabled.')
        self.validate_order(order)
        return self.authenticated_client().place_order(order)

    def cancel(self,order_id):
        if not self.live_enabled():
            raise ValueError('Live gate is disabled.')
        return self.authenticated_client().cancel_order({'id':order_id})
