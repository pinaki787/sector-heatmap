"""Independent Renko state using the existing durable FYERS lifecycle."""
import hashlib
import json
import math
from copy import deepcopy
import time
import re
import secrets
import threading
from queue import SimpleQueue, Empty
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from strategies.ema_crossover.runner import TIMEFRAMES
from strategies.ema_crossover.runner import Runner as BaseRunner, configuration as rsi_configuration
from strategies.ema_crossover.broker import FyersBroker as BaseBroker
from . import sideways,costs
from .ema_exit import settings as ema_exit_settings, confirmed_values
from .risk import levels, hard_exit, validate_spot_levels
from . import preferences
from .history import trade_history
from .execution_audit import entry_orders
from . import trailing_stop
from . import ema_proximity
from .signals import Engine, completed, settings

STRATEGY = 'RENKO_SUPERTREND_V1'


def price_fingerprint(row):
    return hashlib.sha256(json.dumps({'timestamp':int(row['timestamp']),**{key:float(row[key]) for key in ('open','high','low','close')}},sort_keys=True).encode()).hexdigest()


def price_state(state):
    result=deepcopy(state)
    if isinstance(result.get('previous'),dict):result['previous'].pop('volume',None)
    return result


class HistoryRevision(ValueError):
    """Valid completed OHLC changed; requires explicit same-anchor replay."""


def analysis(candles, config, tick_size, saved=None, retain=500):
    """Shared chart/runner continuation; never silently reseed a saved recurrence."""
    rows = completed(candles)
    if not rows:
        raise ValueError('No completed Renko host candles available.')
    identity = dict(engine_version='ema-session-history-v5', config=settings(config), symbol=config['underlying'], timeframe=config['timeframe'], tick_size=tick_size, session_deadline=config.get('session_deadline','15:10'))
    if saved and saved['identity'] != identity:
        saved = None
    engine = Engine(config, tick_size, saved['state'] if saved else None)
    fingerprints = dict(saved.get('fingerprints', {})) if saved else {}
    price_fingerprints = dict(saved.get('price_fingerprints', {})) if saved else {}
    last = saved.get('last') if saved else None
    outputs = list(saved.get('rows', [])) if saved else []
    if last and last['timestamp'] not in {r['timestamp'] for r in rows}:
        raise ValueError('Renko continuity lost; reload complete history before resuming. No state reseed or order.')
    if saved and not price_fingerprints:
        # Legacy OHLCV hashes cannot identify which field changed. Replaying
        # the entire SAME anchor up to the saved last bar must reproduce every
        # indicator and lifecycle state before migrating to price-only hashes.
        if rows[0]['timestamp'] != saved['anchor']:
            raise ValueError('Full original history required to verify legacy Renko price continuity.')
        retained={row['timestamp']:row for row in saved.get('rows',[])}
        verified=Engine(config,tick_size)
        for row in rows:
            if row['timestamp']>last['timestamp']:break
            old=retained.get(row['timestamp'])
            if old and price_fingerprint(old)!=price_fingerprint(row):
                raise HistoryRevision('Completed Renko price history changed after processing; signals blocked.')
            verified.update(row)
            price_fingerprints[str(row['timestamp'])]=price_fingerprint(row)
        if price_state(verified.state)!=price_state(saved['state']):
            raise HistoryRevision('Completed Renko price history changed after processing; signals blocked.')
    for row in rows:
        stamp = str(row['timestamp'])
        digest = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        if stamp in price_fingerprints and price_fingerprints[stamp] != price_fingerprint(row):
            raise HistoryRevision('Completed Renko candle changed after processing; signals blocked.')
        if last and row['timestamp'] <= last['timestamp']:
            continue
        last = engine.update(row)
        outputs.append(last)
        fingerprints[stamp] = digest
        price_fingerprints[stamp] = price_fingerprint(row)
    return dict(identity=identity, state=deepcopy(engine.state), last=last, rows=outputs[-retain:] if retain else outputs,
                fingerprints=dict(list(fingerprints.items())[-1000:]),
                price_fingerprints=dict(list(price_fingerprints.items())[-1000:]),
                anchor=saved['anchor'] if saved else rows[0]['timestamp'])


IST = ZoneInfo('Asia/Kolkata')

def ema_adverse(sig, direction):
    value=sig.get('ema_exit',sig.get('ema10'))
    return sig.get('ema_exit_enabled',True) and value is not None and (sig['close'] < value if direction == 'BULLISH' else sig['close'] > value)

def overnight(config):
    return (config.get('execution_route') == 'CASH_EQUITY' and config.get('cash_product') == 'CNC') or (config.get('underlying','').startswith('MCX:') and config.get('commodity_holding') == 'CARRY_FORWARD')

def commodity_expiry_exit_at(expiry, session):
    if not isinstance(expiry,(int,float)) or not math.isfinite(expiry) or expiry <= 0:
        raise ValueError('Exact MCX option master expiry required for overnight carry.')
    day=datetime.fromtimestamp(expiry,IST)-timedelta(days=1)
    while day.weekday() >= 5:day-=timedelta(days=1)
    end=session.split('-')[-1]
    if not re.fullmatch(r'\d{4}',end):raise ValueError('Verified MCX regular session required.')
    return (day.replace(hour=int(end[:2]),minute=int(end[2:]),second=0,microsecond=0)-timedelta(minutes=30)).timestamp()

def after_cutoff(now, config=None):
    if overnight(config or {}):return False
    if (config or {}).get('broker') == 'DELTA_INDIA' and (config or {}).get('carry_policy') == 'CONTINUOUS':return False
    t = datetime.fromtimestamp(now, IST)
    h,m = (config or {}).get('session_deadline','15:10').split(':')
    return (t.hour,t.minute) >= (int(h),int(m))

def master_session_policy(row):
    exchange = {'10':'NSE','12':'BSE','11':'MCX'}.get(str(row[10])) if len(row)>11 else None
    if exchange is None or row[9].split(':')[0] != exchange:
        raise ValueError('Authoritative master exchange is unavailable or inconsistent.')
    segment = 'MCX_COM' if exchange=='MCX' and str(row[11])=='20' else exchange+'_CM' if exchange!='MCX' and str(row[11])=='10' else None
    if segment is None:raise ValueError('Unsupported master segment; no alternate instrument route.')
    match=re.fullmatch(r'(\d{4})-(\d{4})',str(row[6]).split('|')[0])
    if not match:raise ValueError('Verified regular-session bounds required.')
    opening,ending=match.groups();requested=ending if exchange=='MCX' else '1510';effective=min(requested,ending)
    if opening>=effective:raise ValueError('No usable regular-session interval before cutoff.')
    return dict(session_segment=segment,session_exchange=exchange,session_open=opening[:2]+':'+opening[2:],session_deadline=effective[:2]+':'+effective[2:],requested_deadline=requested[:2]+':'+requested[2:],session_source='Current FYERS master exchange/segment and regular-session bounds',master_regular_session=str(row[6]).split('|')[0])

def ema_exit_observation(confirmed, price, stamp, config, now):
    seconds = TIMEFRAMES[config['timeframe']]
    if not math.isfinite(price) or price <= 0 or not 0 <= now-stamp <= 15:
        raise ValueError('Fresh underlying price required for EMA10 exit.')
    opening = int(stamp)//seconds*seconds
    if confirmed['last']['timestamp']+seconds != opening or not opening <= now < opening+seconds:
        raise ValueError('EMA10 exit needs the immediately preceding confirmed EMA state.')
    previous_ema = confirmed['state']['ema10']
    ema10=2/11*price+9/11*previous_ema
    ema30=2/31*price+29/31*confirmed['state']['ema30']
    return dict(timestamp=opening,close=price,ema10=ema10,ema30=ema30,ema_gap=ema10-ema30,market_event_at=stamp,provisional=True)


def provisional(confirmed, forming, config, tick_size, now):
    """Evaluate one forming host candle from a fresh clone, never commit ticks."""
    seconds = TIMEFRAMES[config['timeframe']]
    c = dict(forming)
    stamp = c.get('stream_exchange_at')
    if stamp is None or not 0 <= now - stamp <= 15:
        raise ValueError('Fresh underlying market update (at most 15 seconds old) required.')
    if not c.get('is_forming') or not c['timestamp'] <= now < c['timestamp'] + seconds:
        raise ValueError('A current forming host candle is required for intrabar entry.')
    if confirmed['last']['timestamp'] + seconds != c['timestamp']:
        raise ValueError('Confirmed history must reach the bar immediately before the forming candle.')
    c['is_forming'] = False
    e = Engine({**config,'retest_enabled':False}, tick_size, confirmed['state'])
    r = e.update(c)
    # A confirmed setup can still be live-qualified; candle identity prevents repeats.
    candidate = r['direction'] if r['entry_qualified'] and not after_cutoff(now, config) else None
    return {**r, 'is_forming': True, 'provisional': True, 'entry_direction': candidate,
            'entry_buy_signal': candidate == 'BULLISH', 'entry_sell_signal': candidate == 'BEARISH', 'entry_diagnostic':'ENTRY_CUTOFF' if after_cutoff(now, config) else r['entry_diagnostic'],
            'evaluated_at': now, 'market_event_at': stamp,
            'scope': 'Provisional live candidate; can disappear. Not a confirmed historical signal or broker fill.'}


def configuration(payload):
    if not isinstance(payload.get('intrabar_entries', False), bool):
        raise ValueError('Intrabar entry mode must be explicitly enabled or disabled.')
    if payload.get('strategy') != STRATEGY:
        raise ValueError('Review the Renko Supertrend Strategy before activation.')
    if payload.get('exit_policy') != 'OPPOSITE_CONFIRMED_SIGNAL':
        raise ValueError('Confirm opposite confirmed-signal exits; no same-candle re-entry.')
    route = payload.get('execution_route', 'OPTIONS')
    if route not in ('OPTIONS', 'CASH_EQUITY'):
        raise ValueError('Choose options or cash equity explicitly.')
    if route == 'CASH_EQUITY' and payload.get('sideways_enabled',False):
        raise ValueError('Cash equity after-cost sideways filter is unavailable; clear that optional filter before starting cash equity.')
    holding=payload.get('commodity_holding') or 'INTRADAY'
    if holding not in ('INTRADAY','CARRY_FORWARD'):raise ValueError('Choose MCX Intraday or Carry forward.')
    if holding == 'CARRY_FORWARD' and not str(payload.get('underlying','')).startswith('MCX:'):raise ValueError('Commodity carry-forward requires an MCX underlying.')
    quantity = None
    cash_product = str(payload.get('cash_product', 'INTRADAY')).upper()
    if route == 'CASH_EQUITY' and cash_product not in ('INTRADAY','CNC'):
        raise ValueError('Cash holding must be Intraday or Carry forward (CNC).')
    if route == 'CASH_EQUITY':
        raw = payload.get('quantity')
        try:
            quantity = int(raw)
        except (ValueError, TypeError):
            raise ValueError('Cash equity quantity must be a positive whole number of shares.')
        if isinstance(raw,bool) or str(raw) != str(quantity) or not 1 <= quantity <= 1000000:
            raise ValueError('Cash equity quantity must be 1–1000000 whole shares.')
    # Share capital, lot, timeframe and mode validation; discard RSI-only settings.
    shared = rsi_configuration({**payload, 'strategy': 'RSI_BASED_EMA_V1', 'rsi_length': 14,
                                'ma_length': 14, 'ma_type': 'SMA', 'lots': 1 if route == 'CASH_EQUITY' else payload.get('lots'), 'trailing_enabled': False, 'spot_target':None, 'spot_stop':None})
    for key in ('rsi_length', 'ma_length', 'ma_type'):
        shared.pop(key)
    return {**shared, **settings(payload), **levels(payload), **sideways.settings(payload), **costs.settings(payload), **trailing_stop.settings(payload), **ema_proximity.settings(payload), **ema_exit_settings({**payload,'ema_exit_enabled':payload.get('ema_exit_enabled',True)}), 'strategy': STRATEGY,
            'commodity_holding': holding if str(payload.get('underlying','')).startswith('MCX:') else None, 'execution_route': route, 'quantity': quantity, 'cash_product': cash_product if route == 'CASH_EQUITY' else None, 'label': 'Renko Supertrend Strategy', 'intrabar_entries': payload.get('intrabar_entries', False),  'exit_policy': 'OPPOSITE_CONFIRMED_SIGNAL'}


class Broker(BaseBroker):
    def cash_contract(self, symbol):
        row = self.underlying(symbol)
        exchange = symbol.split(':', 1)[0]
        if exchange not in ('NSE', 'BSE') or symbol.endswith('-INDEX') or not (symbol.endswith('-EQ') if exchange == 'NSE' else str(row[2]) == '0'):
            raise ValueError('Cash equity requires an exact NSE/BSE cash-master stock; indices and derivatives are excluded.')
        master_session_policy(row)
        tick = float(row[4])
        if not math.isfinite(tick) or tick <= 0:
            raise ValueError('Cash equity master tick size is invalid.')
        return dict(symbol=symbol, lot_size=1, tick_size=tick, quantity_multiplier=1, execution_route='CASH_EQUITY')

    def contract(self, symbol):
        if symbol.endswith('-EQ') or (symbol.startswith('BSE:') and not symbol.endswith(('CE','PE','-INDEX'))):
            return self.cash_contract(symbol)
        result=super().contract(symbol)
        if symbol.startswith('MCX:'):
            row=next(r for r in self.rows('MCX_COM') if len(r)>16 and r[9]==symbol)
            result.update(expiry_epoch=float(row[8]),option_type=row[16],strike=float(row[15]))
        return result

    def order(self, symbol, qty, side, quote):
        result = super().order(symbol, qty, side, quote)
        if self.contract(symbol).get('execution_route') == 'CASH_EQUITY':
            result['productType'] = getattr(self,'cash_products',{}).get(symbol,'INTRADAY')
        return result

    def validate_order(self, order):
        if self.contract(order['symbol']).get('execution_route') != 'CASH_EQUITY':
            return super().validate_order(order)
        if isinstance(order['qty'],bool) or not isinstance(order['qty'],int) or order['qty'] <= 0 or order['side'] not in (1,-1) or order['productType'] not in ('INTRADAY','CNC') or order['type'] != 2:
            raise ValueError('Cash equity requires whole-share INTRADAY or CNC MARKET orders.')
        if order.get('limitPrice') != 0 or order.get('stopPrice') != 0 or order.get('offlineOrder') is not False:
            raise ValueError('Cash equity MARKET orders require regular-session routing and zero limit/stop prices.')

    def reconcile_position(self, symbol, qty):
        if self.contract(symbol).get('execution_route') != 'CASH_EQUITY':
            return super().reconcile_position(symbol, qty)
        rows = [r for r in self.positions() if r.get('symbol') == symbol and float(r.get('netQty',0)) != 0]
        product = getattr(self,'cash_products',{}).get(symbol,'INTRADAY')
        if product == 'CNC':
            holdings = [r for r in self.holdings() if r.get('symbol') == symbol and float(r.get('remainingQuantity',r.get('quantity',0))) != 0]
            if holdings:
                if rows:
                    raise ValueError('CNC holdings and day positions overlap; ownership cannot be proven uniquely. Reconcile before automated exit.')
                held = sum(float(r.get('remainingQuantity',r.get('quantity',0))) for r in holdings)
                if held == qty and qty >= 0:
                    return
                raise ValueError('Broker CNC holdings differ from runner-owned shares; no exit order sent.')
        if qty == 0 and not rows:
            return
        if len(rows) != 1 or rows[0].get('productType') != product or float(rows[0].get('netQty',0)) != qty:
            raise ValueError('Broker cash position differs from the runner signed share quantity; reconciliation required.')

    def holdings(self):
        from sector_heatmap.fyers_execution import _current_client
        response = _current_client().holdings()
        if not isinstance(response,dict) or response.get('s') != 'ok' or not isinstance(response.get('holdings'),list):
            raise ValueError('Fresh FYERS holdings unavailable; cash ownership validation blocked.')
        return response['holdings']

    def preflight(self, order, c):
        if c.get('execution_route') == 'CASH_EQUITY':
            if c.get('cash_product') == 'CNC' and order['side'] != 1:
                raise ValueError('Carry forward CNC cannot open an overnight cash short; bearish entry blocked.')
            if any(r.get('symbol') == order['symbol'] and float(r.get('remainingQuantity',r.get('quantity',0))) != 0 for r in self.holdings()):
                raise ValueError('Existing holdings block new cash entry; external holdings are never adopted.')
        return super().preflight(order,c)

    def stop(self):
        # SDK close joins its message thread. That thread may be waiting for
        # Runner.lock in on_tick while Stop holds it: detach synchronously,
        # then join outside the runner's call stack. Old-generation ticks fail
        # the existing callback guard; a later Start owns a separate socket.
        with self.lock:
            self.stream_generation += 1
            socket,self.socket=self.socket,None
            self.connected=False
            self.ticks={};self.symbols=set();self.last_subscribe={}
        if socket:
            def close():
                try:socket.close_connection()
                except Exception:pass  # SDK errors can include credentials.
            self.close_thread=threading.Thread(target=close,name='renko-quote-close',daemon=True)
            self.close_thread.start()

    def __init__(self, *args, on_tick=None, **kwargs):
        self.forming_bars = {}
        self.frame_seconds = {}
        def ingest(raw):
            symbol = raw.get('symbol')
            stamp = raw.get('exch_feed_time', raw.get('last_traded_time'))
            price = raw.get('ltp')
            if isinstance(stamp,(int,float)) and isinstance(price,(int,float)) and price > 0 and 0 <= time.time()-stamp <= 15:
                with self.lock:
                    for (selected,seconds) in list(self.frame_seconds):
                        if selected != symbol: continue
                        opening = int(stamp)//seconds*seconds
                        key = (symbol,seconds,opening)
                        bar = self.forming_bars.setdefault(key,dict(timestamp=opening,open=price,high=price,low=price,close=price,is_forming=True,host_open_verified=False))
                        bar.update(high=max(bar['high'],price),low=min(bar['low'],price),close=price,stream_exchange_at=stamp)
                    for key in list(self.forming_bars):
                        if key[2]+key[1] < stamp-key[1]: del self.forming_bars[key]
            if on_tick: on_tick(raw)
        super().__init__(*args,on_tick=ingest,**kwargs)

    def observe(self, c, rows):
        seconds = TIMEFRAMES[c['timeframe']]
        with self.lock:
            self.frame_seconds[(c['underlying'],seconds)] = True
            for row in rows:
                if not row.get('is_forming'): continue
                key = (c['underlying'],seconds,row['timestamp'])
                bar = self.forming_bars.get(key,{})
                self.forming_bars[key] = {**row,**bar,'open':row['open'],'high':max(row['high'],bar.get('high',row['high'])),'low':min(row['low'],bar.get('low',row['low'])),'host_open_verified':True}

    def candles(self, c):
        from sector_heatmap.fyers_execution import _current_client
        key = (c['underlying'], c['timeframe'])
        cached = self.history_cache.get(key)
        if cached and time.time() - cached[0] < 1:
            return cached[1]
        rows = self.fetch_candles(_current_client(), *key, include_forming=True)
        self.history_cache[key] = (time.time(), rows)
        self.observe(c, rows)
        return rows

    def live_price(self, c, now):
        raw = self.tick(c['underlying'])
        stamp = float(raw.get('exch_feed_time',raw.get('last_traded_time',0)))
        price = float(raw.get('ltp',0))
        if not math.isfinite(price) or price <= 0 or not 0 <= now-stamp <= 15:
            raise ValueError('Fresh underlying market price required.')
        return price,stamp

    def quote(self, symbol):
        quote = super().quote(symbol)
        now = time.time()
        if any(not isinstance(quote.get(key),(int,float)) or not 0 <= now-quote[key] <= 15
               for key in ('received_at','exchange_at')):
            raise ValueError('Fresh executable option bid required; valuation unavailable.')
        return quote

    def forming(self, c, rows, now):
        raw = self.tick(c['underlying'])
        stamp = float(raw.get('exch_feed_time', raw.get('last_traded_time', 0)))
        price = float(raw.get('ltp', 0))
        if not math.isfinite(price) or price <= 0 or not 0 <= now-stamp <= 15:
            raise ValueError('Fresh positive underlying last-traded price required.')
        seconds = TIMEFRAMES[c['timeframe']]
        opening = int(stamp)//seconds*seconds
        self.observe(c, rows)
        with self.lock:
            host = deepcopy(self.forming_bars.get((c['underlying'],seconds,opening)))
        if not host or not host.get('host_open_verified'):
            raise ValueError('Broker forming OHLC unavailable; intrabar entry blocked.')
        return {**host, 'close':price, 'high':max(host['high'],price), 'low':min(host['low'],price), 'stream_exchange_at':stamp}

    def route_availability(self,c):
        if c.get('execution_route') == 'CASH_EQUITY':
            self.cash_contract(c['underlying'])
            return dict(available=True,message='Cash equity · bullish BUY / bearish SELL · intraday whole shares')
        row=self.underlying(c['underlying']);policy=master_session_policy(row)
        segment='MCX_COM' if policy['session_exchange']=='MCX' else policy['session_exchange']+'_FO'
        counts={kind:sum(1 for r in self.rows(segment) if len(r)>16 and r[13]==row[13] and r[16]==kind and float(r[8] or 0)>time.time()) for kind in ('CE','PE')}
        available=all(counts.values())
        return dict(available=available,contract_counts=counts,message='Nearest-expiry ATM Call/Put route available in current master' if available else 'ATM Call/Put unavailable for this underlying in the current master; no futures fallback.')

    def session_policy(self,c):
        return master_session_policy(self.underlying(c['underlying']))

    def resolve(self,c,direction):
        if c.get('execution_route') == 'CASH_EQUITY':
            if direction not in ('BULLISH','BEARISH'):
                raise ValueError('Unknown cash equity entry direction.')
            if c.get('cash_product','INTRADAY') == 'CNC' and direction == 'BEARISH':
                raise ValueError('Carry forward CNC cannot open an overnight cash short; bearish entry blocked. Existing long shares still exit on bearish signals.')
            self.cash_products=getattr(self,'cash_products',{})
            self.cash_products[c['underlying']]=c.get('cash_product','INTRADAY')
            result={**self.cash_contract(c['underlying']), 'entry_side':1 if direction == 'BULLISH' else -1,
                    'quantity':c['quantity']}
        else:
            result=super().resolve(c,direction)
            if c.get('commodity_holding') == 'CARRY_FORWARD':
                cutoff=commodity_expiry_exit_at(result.get('expiry_epoch'),self.session_policy(c)['master_regular_session'])
                if time.time() >= cutoff:raise ValueError('Nearest MCX option is inside the pre-expiry carry protection window; overnight entry blocked.')
                result['expiry_protection_at']=cutoff
        self.resolved_contracts=getattr(self,'resolved_contracts',{})
        self.resolved_contracts[result['symbol']]=deepcopy(result)
        return result

    def warm_options(self,c):
        now=time.time()
        if now-getattr(self,'last_option_warmup',0)<10:return
        self.last_option_warmup=now
        for direction in ('BULLISH','BEARISH'):
            try:
                contract=self.resolve(c,direction)
                self.tick(contract['symbol'])  # Subscribe before an entry; no order route.
            except (ValueError,RuntimeError):
                pass  # Fresh bid/ask remains mandatory at actual entry preflight.

    def host_tick_size(self, symbol):
        tick = float(self.underlying(symbol)[4])
        if not math.isfinite(tick) or tick <= 0:
            raise ValueError('Host-symbol master tick size is invalid.')
        return tick

    def validate_config(self, c):
        result = super().validate_config(c)
        if c.get('execution_route') == 'CASH_EQUITY':
            self.cash_products=getattr(self,'cash_products',{})
            self.cash_products[c['underlying']]=c['cash_product']
            result.update(execution='Cash equity: bullish BUY / bearish SELL; exit uses the opposite side',
                          product=c['cash_product'], quantity=c['quantity'], sizing='Whole shares; no option lot multiplier',
                          holding_policy='Carry forward CNC: bought shares can stay overnight; new bearish shorts blocked; exits require verified ownership and broker delivery sell authorization.' if c['cash_product']=='CNC' else 'Intraday long/short; 15:10 IST strategy square-off')
        policy=self.session_policy(c)
        if c.get('session_deadline') and any(c.get(k)!=v for k,v in policy.items()):
            raise ValueError('Master session policy changed; stop/reload before activation.')
        result.update(**policy)
        route=self.route_availability(c)
        if not route['available']:raise ValueError(route['message'])
        result.update(option_route=route, execution_route=c.get('execution_route','OPTIONS'))
        result.update(host_tick_size=self.host_tick_size(c['underlying']),
                      exits='Fresh underlying EMA10 adverse breach (independent of ADX), opposite confirmed Supertrend reversal (selected ADX gate), or 15:10 IST wall-clock square-off. No same-candle re-entry.',
                      entry_timing='INTRABAR_PROVISIONAL' if c.get('intrabar_entries',False) else 'COMPLETED_CANDLE', squareoff_time=policy['session_deadline']+' Asia/Kolkata',
                      entries=f"Host-price EMA10/30 aligned with existing Supertrend regime; close beyond EMA10; strictly widening signed gap for {c['widening_window']} completed candles. Signal on qualification onset; re-arm when qualification breaks.",
                      risk='Research reconstruction. Provisional candidates can disappear; OHLC replay cannot prove tick fills. EMA10 breach exits independently of ADX; opposite confirmed Supertrend exits honor ADX. Wall-clock 15:10 IST square-off and entry cutoff require a running server; broker fills require fresh execution quotes and reconciliation. Existing FYERS sizing, preflight, durable intent and reconciliation apply.')
        if c.get('underlying','').startswith('MCX:'):
            result.update(product='MARGIN',holding_policy='Carry forward with pre-expiry protection' if c.get('commodity_holding') == 'CARRY_FORWARD' else 'Intraday strategy square-off; commodity options use MARGIN',squareoff_time='None · overnight carry; exact option pre-expiry protection applies' if c.get('commodity_holding') == 'CARRY_FORWARD' else result['squareoff_time'])
        return result


class Runner(BaseRunner):
    strategy_id = STRATEGY
    runtime_revision = 'renko-supertrend-assessment-recovery-v14'
    signal_policy = 'OPT_IN_INTRABAR_REGIME_EMA_ENTRY__EMA10_ST_OR_MARKET_CUTOFF_EXIT'
    activation_name = 'RENKO SUPERTREND'
    entry_reason = 'RENKO_EMA_ENTRY'
    exit_reason = 'RENKO_ST_EXIT'
    configure = staticmethod(configuration)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        # Legacy saved runs retain their explicit pre-filter behavior. New setups default ON.
        if self.state.get('config'):self.state['config'].setdefault('rsi_slope_enabled',False)
        self.position_ticks=SimpleQueue()
        prior=getattr(self.adapter,'on_tick',None)
        def wake_on_tick(tick):
            if prior:prior(tick)
            # Never wait for the strategy lock on the websocket receive thread.
            # History requests hold it; waiting here backs up provider frames
            # while misleadingly refreshing their local receive timestamps.
            if tick.get('symbol')==(self.state.get('config') or {}).get('underlying'):
                self.position_ticks.put((dict(tick),self.clock()))
            self.wake.set()
        self.adapter.on_tick=wake_on_tick

    def read_preferences(self):
        return preferences.read(self.path.with_name('renko-supertrend-settings.json'))

    def drain_position_ticks(self):
        changed=False
        for _ in range(self.position_ticks.qsize()):
            try:tick,received_at=self.position_ticks.get_nowait()
            except Empty:break
            changed=self.observe_position_tick(tick,received_at,persist=False) or changed
        if changed:self.save()

    def observe_position_tick(self,tick,received_at=None,persist=True):
        c=self.state.get('config') or {}
        pending=self.state.get('pending')
        p=self.state.get('position') or (pending.get('position') if pending and self.is_entry_order(pending['order'],pending['position']) else None)
        if not p or tick.get('symbol')!=c.get('underlying'):return
        entry=(p.get('exposure_range') or {}).get('entry_at',p.get('opened_at'))
        if entry is None:return
        stamp=tick.get('exch_feed_time',tick.get('last_traded_time'))
        # Freshness is checked at the actual callback observation, not at the
        # later queue drain. Provider timestamps and all exposure bounds remain.
        updated=sideways.observe(p.get('exposure_range'),entry,tick.get('ltp'),stamp,self.clock() if received_at is None else received_at)
        if updated!=p.get('exposure_range'):
            p['exposure_range']=updated
            if persist:self.save()
            return True

    def sideways_entry_gate(self):
        c=self.state.get('config') or {}
        lock=self.state.get('sideways_lock')
        if not c.get('sideways_enabled') or not lock or not lock.get('active'):return True
        if lock.get('underlying')!=c.get('underlying'):
            # A new explicitly selected instrument cannot inherit another
            # instrument's price range. Require immutable prior-run ownership
            # before archiving it; unknown provenance remains blocked.
            prior_owned = any(o.get('side') == 'BUY' and o.get('underlying_symbol') == lock.get('underlying')
                and o.get('run_id') and o['run_id'] != self.state.get('run_id')
                and o.get('mode') in ('PAPER','LIVE')
                and lock.get('trade_id') == f"{o['mode']}-TRADE-{o.get('lifecycle_id')}"
                for o in self.state.get('order_history', []))
            if not prior_owned or self.state.get('position') or self.state.get('pending'):
                self.state['message']='Sideways lock belongs to another underlying; entries blocked pending review.'
                return False
            archived = dict(deepcopy(lock), archived_at=self.clock(), archive_reason='NEW_RUN_DIFFERENT_UNDERLYING',
                            selected_underlying=c['underlying'])
            self.state['sideways_archived'] = (self.state.get('sideways_archived', [])+[archived])[-50:]
            self.state['sideways_lock'] = None
            self.state['eligible_since'] = self.clock()
            self.event('SIDEWAYS_RANGE_ARCHIVED', 'Prior-run sideways range retained in audit; new instrument requires fresh post-selection entry signals.')
            return True
        try:
            price,stamp=self.adapter.live_price(c,self.clock())
            reason=sideways.breakout(lock,price,stamp,self.clock())
        except (ValueError,RuntimeError,AttributeError):reason=None
        if reason:
            lock.update(active=False,released_at=self.clock(),release_exchange_at=stamp,release_price=price,release_reason=reason)
            self.state['eligible_since']=self.clock()
            self.state.setdefault('sideways_events',[]).append(deepcopy(lock))
            self.save()
            return True
        self.state.update(status='SIDEWAYS_LOCKED',message=f"Sideways locked inside position range {lock['low']:.2f}–{lock['high']:.2f}; only a strict fresh breakout unlocks new entries.")
        self.save()
        return False

    def indicator_snapshot(self,sig=None,reason=None):
        sig=sig or {}
        c=self.state.get('config') or {}
        engine=self.state.get('renko_engine') or {}
        return dict(schema_version=1,captured_at=self.clock(),reason=reason,
            settings=deepcopy(c),settings_revision=self.runtime_revision,
            initialization_anchor=engine.get('anchor'),host_bar_count=(engine.get('state') or {}).get('count'),
            observation_mode='INTRABAR' if sig.get('provisional') else 'CONFIRMED' if sig else 'WALL_CLOCK / INDICATORS_UNAVAILABLE',
            market_event_at=sig.get('market_event_at'),
            indicators={k:deepcopy(sig.get(k)) for k in ('timestamp','close','rsi14','rsi14_previous','rsi14_slope','rsi_slope_enabled','rsi_slope_pass','rsi_slope_diagnostic','ema10','ema30','ema_gap','ema_exit','ema_exit_length','ema_exit_enabled','ema_widening','retest_signal','retest_touched','retest_reference_ema10','retest_bounce','retest_patterns','retest_pattern_bars','retest_touch_evidence','entry_qualified','entry_diagnostic','supertrend','direction','pine_direction','box','auto_box','host_atr','synthetic_atr','regime_atr','low_atr','volatility_ratio','effective_factor','adx','signal_allowed')},
            confirmed_gap_history=deepcopy((engine.get('state') or {}).get('ema_gaps',[])),
            confirmed_indicator_reference=deepcopy(engine.get('last')),
            provenance='Captured at strategy event; missing observations remain unknown. Confirmation and broker fill times are separate.')

    def save_preferences(self,payload):
        with self.lock:
            return preferences.write(self.path.with_name('renko-supertrend-settings.json'),payload,self.clock())

    def preview(self,payload):
        p=super().preview(payload)
        if hasattr(self.adapter,'session_policy'):
            policy=self.adapter.session_policy(p['config'])
            self.preview_value['config'].update(policy)
            p=deepcopy(self.preview_value)
        return p

    def activate(self,payload,background=True):
        # One explicit UI click. Prepare/start remain atomic and fully validated.
        with self.lock:
            if payload.get('configuration_revision') != self.runtime_revision:
                raise ValueError('Strategy revision changed; reload the dashboard before Start Runner.')
            if self.state.get('position') or self.state.get('pending'):
                raise ValueError('Existing exposure must finish stopping/reconciliation before a new start.')
            p=self.preview(payload)
            if after_cutoff(self.clock(),p['config']):
                raise ValueError('Selected segment entry cutoff has passed.')
            tick=self.adapter.host_tick_size(p['config']['underlying'])
            analysis(self.adapter.candles(p['config']),p['config'],tick)
            if payload.get('resume_run_id'):
                old=deepcopy(self.state)
                expected=self.configure(old['config'])
                if hasattr(self.adapter,'session_policy'):expected.update(self.adapter.session_policy(expected))
                if payload['resume_run_id']!=old.get('run_id') or expected!=p['config'] or p['config']['mode']!='PAPER' or p['context'].get('account_identity')!=old.get('account_identity'):
                    raise ValueError('Guarded recovery requires the identical saved Paper run and account.')
                super().start(dict(preview_id=p['id'],confirmation=p['confirmation']),False)
                for key in ('run_id','trades_used','realized_pnl','started_at','last_exit_bar','rearm_after_exit','seen','losses','sideways_lock','sideways_events','execution_signals','order_history'):
                    if key in old:self.state[key]=deepcopy(old[key])
                self.state['recovered_at']=self.clock()
                self.event('WATCHING','Existing Paper run recovered with trade quota, P&L and journal preserved. Fresh post-recovery signals only.')
                if background:
                    self.wake.clear()
                    self.thread=threading.Thread(target=self.loop,name='renko-supertrend-runner',daemon=True)
                    self.thread.start()
                return self.snapshot()
            self.state['run_id']='RENKO-RUN-'+secrets.token_hex(10)
            result=super().start(dict(preview_id=p['id'],confirmation=p['confirmation']),background)
            self.event('WATCHING','Renko armed in '+p['config']['mode']+'; '+('fresh intrabar candidates' if p['config'].get('intrabar_entries') else 'completed-candle qualifications')+'; segment cutoff '+p['config'].get('session_deadline','15:10')+' IST. No historical signal replay.')
            return self.snapshot()

    def stop(self):
        with self.lock:
            if (self.state.get('position') or self.state.get('pending')) and not self.state.get('running'):
                c=deepcopy(self.state['config'])
                context=self.adapter.validate_config(c)
                if context.get('account_identity') != self.state.get('account_identity'):
                    raise ValueError('Saved exposure belongs to a different account; no closing order.')
                self.preview_value=dict(id=secrets.token_hex(16),config=c,confirmation=secrets.token_hex(16),expires_at=self.clock()+120,context=context)
                p=self.preview_value
                super().start(dict(preview_id=p['id'],confirmation=p['confirmation']))
            reason=(self.state.get('position') or {}).get('exit_reason')
            result=super().stop()
            if reason and self.state.get('position'):
                self.state['position']['exit_reason']=reason;self.save()
            return self.snapshot()

    def session_bounds(self,c):
        if c.get('broker') == 'DELTA_INDIA' and c.get('carry_policy') == 'CONTINUOUS':return 0,1440
        opening=c.get('session_open','09:15');ending=c.get('session_deadline','15:10')
        def minutes(v):h,m=map(int,v.split(':'));return h*60+m
        return minutes(opening),minutes(ending)

    def snapshot(self):
        result = super().snapshot()
        if result.get('running') and result.get('status')=='WATCHING_NO_ENTRY' and not result.get('position') and not result.get('pending') and hasattr(self.adapter,'tick'):
            try:
                self.adapter.live_price(result['config'],self.clock())
                result['message']='Waiting for a new eligible entry signal; underlying stream timestamp is fresh.'
            except ValueError as error:
                result.update(status='WAITING_FOR_STREAM',message=str(error))
        state = result.pop('renko_engine', None)
        if state:
            result['initialization_anchor'] = state['anchor']
            result['host_bar_count'] = state['state']['count']
        if result.get('status')=='STOPPED' and not result.get('running') and not result.get('position') and not result.get('pending'):
            result['message']='Runner stopped. Start Runner uses the selected visible mode and settings.'
        result['shutdown_pending']=bool(self.thread and self.thread.is_alive() and not self.state.get('running'))
        valuation=None
        if result.get('position') and result['pnl'].get('available'):
            try:
                quote=self.adapter.quote(result['position']['symbol'])
                valuation=dict(bid=quote.get('bid'),exchange_at=quote.get('exchange_at'),received_at=quote.get('received_at'),observed_at=self.clock(),basis='Fresh executable option bid; before fees')
                pos=result['position']
                mark=quote['ask' if pos.get('entry_side',1)==-1 else 'bid']
                valuation.update(price=mark,basis='Fresh executable ask for short / bid for long; before fees')
                result['pnl']['unrealized']=(mark-pos['entry_price'])*pos.get('entry_side',1)*pos['quantity']*pos.get('quantity_multiplier',1)
            except Exception:
                result['pnl'].update(available=False,unrealized=None)
        result['trade_history']=trade_history(self.state.get('order_history',[]),self.state.get('position'),result['pnl'].get('unrealized') if result['pnl'].get('available') else None,valuation)
        for trade in result['trade_history']:
            trade['sideways_lock_release']=next((deepcopy(e) for e in reversed(self.state.get('sideways_events',[])) if e.get('trade_id')==trade['trade_id'] and e.get('released_at')),None)
        if (self.state.get('config') or {}).get('mode') == 'PAPER':
            try:result['paper_capital']=self.paper_funds()
            except (ValueError,AttributeError,KeyError) as error:result['paper_capital']=dict(available=False,error=str(error))
        current=[t for t in result['trade_history'] if t.get('run_id')==self.state.get('run_id') and t.get('entry_filled')]
        net_realized=sum(t['costs']['realized_net'] for t in current) if all(t['costs'].get('realized_net') is not None for t in current) else None
        opened=[t for t in current if t.get('remaining_quantity')]
        net_open=sum(t['costs']['unrealized_net'] for t in opened) if all(t['costs'].get('unrealized_net') is not None for t in opened) else None
        result['cost_pnl']=dict(realized_net=net_realized,unrealized_net=net_open,total_net=net_realized+net_open if net_realized is not None and net_open is not None else None,basis='After estimated charges and configured additional slippage; open value assumes liquidation at fresh option bid.',brokerage_per_executed_order=15,additional_slippage_points=(self.state.get('config') or {}).get('additional_slippage_points',0),model=costs.MODEL)
        if (self.state.get('config') or {}).get('execution_route') == 'CASH_EQUITY':
            result['cost_pnl'].update(model={'id':'CASH_EQUITY_FEES_UNVERIFIED'},basis='Cash gross P&L only; verified cash charge model unavailable. After-cost values unavailable.',realized_net=None,unrealized_net=None,total_net=None)
        result['sideways_status']=dict(enabled=(self.state.get('config') or {}).get('sideways_enabled',False),max_candles=(self.state.get('config') or {}).get('sideways_max_candles',3),loss_basis='AFTER_ESTIMATED_COSTS',lock=deepcopy(self.state.get('sideways_lock')),events=deepcopy(self.state.get('sideways_events',[])))
        signals=deepcopy([event for event in self.state.get('execution_signals',[]) if event.get('run_id')==self.state.get('run_id')])
        for event in signals:
            if event.get('status')=='WAITING FOR OPTION QUOTE' and self.clock()-event['event_at']>TIMEFRAMES[self.state['config']['timeframe']]:
                event.update(status='EXPIRED',reason='Option quote was unavailable before signal freshness expired; no historical replay.')
            orders=entry_orders(event,self.state.get('order_history',[]),TIMEFRAMES[self.state['config']['timeframe']])
            if orders:
                event['first_assessment']={k:event.get(k) for k in ('status','reason','eligible','event_at','observed_at')}
                event['status']='FILLED' if any(row.get('filled',0)>0 for row in orders) else 'ORDER '+str(orders[-1].get('status','PENDING'))
                event['reason']='Runner-owned order journal; acceptance and fill remain distinct.'
                event['entry_event_at']=orders[-1].get('entry_event_at')
                event['first_fill_confirmed_at']=next((row.get('first_fill_confirmed_at') for row in orders if row.get('filled',0)>0),None)
            elif event.get('eligible') and event==signals[-1] and result.get('status')=='BLOCKED':
                event['status']='BLOCKED';event['reason']=result.get('message')
        result['execution_signals']=signals
        result['session_policy']={k:(self.state.get('config') or {}).get(k) for k in ('session_segment','session_deadline','requested_deadline','session_source')}
        return result

    def signal_key(self, sig):
        c = self.state['config']
        digest = hashlib.sha256(json.dumps(settings(c), sort_keys=True).encode()).hexdigest()[:16]
        return f"RENKO_ST:{c['underlying']}:{c['timeframe']}:{digest}:{sig['timestamp']}"

    def deadline(self):
        c=self.state.get('config') or {}
        if c.get('underlying','').startswith('MCX:') and c.get('commodity_holding') == 'CARRY_FORWARD':
            pending=self.state.get('pending') or {}
            held=self.state.get('position') or (pending.get('position') if pending and self.is_entry_order(pending['order'],pending['position']) else None)
            if self.state.get('running') and held:
                try:
                    cutoff=commodity_expiry_exit_at(held.get('expiry_epoch'),c.get('master_regular_session',''))
                    if self.clock() >= cutoff:held.update(exit_requested=True,exit_reason='MCX_PRE_EXPIRY_EXIT',expiry_protection_at=cutoff)
                except ValueError as error:
                    self.state['accepting_entries']=False
                    held.update(exit_requested=True,exit_reason='MCX_EXPIRY_UNVERIFIED',expiry_error=str(error))
                self.save()
            return
        if c.get('execution_route') == 'CASH_EQUITY' and c.get('cash_product') == 'CNC':
            return  # Keep monitoring ownership across days; signal exits still apply.
        p=self.state.get('position') or {}
        pending=self.state.get('pending') or {}
        owned_at=p.get('opened_at') or pending.get('submitted_at')
        overdue=owned_at is not None and datetime.fromtimestamp(owned_at,IST).date()<datetime.fromtimestamp(self.clock(),IST).date()
        if self.state.get('running') and (after_cutoff(self.clock(),self.state.get('config')) or overdue):
            self.state['accepting_entries'] = False
            p = self.state.get('position')
            if p and not p.get('exit_requested'):
                p.update(exit_requested=True, exit_reason='TIMED_SQUARE_OFF_'+self.state['config'].get('session_deadline','15:10').replace(':',''))
                p['exit_indicator_snapshot']=self.indicator_snapshot(reason=p['exit_reason'])
            self.save()

    def step(self):
        with self.lock:
            self.drain_position_ticks()
            c=self.state.get('config') or {}
            if self.state.get('running') and overnight(c):
                self.deadline()
                now=datetime.fromtimestamp(self.clock(),IST)
                regular_end=c.get('master_regular_session','0915-1530').split('-')[-1]
                end=int(regular_end[:2])*60+int(regular_end[2:])
                opening=self.session_bounds(c)[0]
                if now.weekday() >= 5 or not opening <= now.hour*60+now.minute < end:
                    self.state.update(status='CARRY_FORWARD_WAITING',message='Position retained overnight; resume signal exits, stops and ownership reconciliation in the next regular market session.')
                    self.save()
                    return
            self.deadline()
            c = self.state.get('config')
            p = self.state.get('position')
            pending = self.state.get('pending')
            owned = p or (pending['position'] if pending and self.is_entry_order(pending['order'],pending['position']) else None)
            if self.state.get('running') and c and owned and not owned.get('exit_requested') and c.get('trailing_enabled'):
                try:
                    now=self.clock()
                    # The entry's recorded fill/confirmed exposure owns this stop.
                    opened=(owned.get('exposure_range') or {}).get('entry_at',owned.get('opened_at'))
                    if opened is None:raise ValueError('Trailing waits for confirmed filled exposure.')
                    if c.get('trailing_basis','OPTION_PREMIUM_PERCENT')=='OPTION_PREMIUM_PERCENT':
                        quote=self.adapter.quote(owned['symbol'])
                        price,stamp,received=quote.get('ask' if owned.get('entry_side',1)==-1 else 'bid'),quote.get('exchange_at'),quote.get('received_at')
                    else:
                        price,stamp=self.adapter.live_price(c,now);received=now
                    trail,hit=trailing_stop.advance(owned.get('renko_trailing'),c,owned['direction'],price,stamp,received,now,opened)
                    owned['renko_trailing']=trail;owned.pop('trailing_error',None)
                    if hit:
                        owned.update(exit_requested=True,exit_reason='RENKO_TRAILING_STOP',exit_event_at=stamp)
                        self.state['last_exit_bar']=int(stamp//TIMEFRAMES[c['timeframe']])*TIMEFRAMES[c['timeframe']]
                        owned['exit_indicator_snapshot']=self.indicator_snapshot(dict(close=price,market_event_at=stamp,provisional=True),'RENKO_TRAILING_STOP')
                        if pending and not p:
                            self.state['pending_entry_exit_reason']='RENKO_TRAILING_STOP'
                            self.state['pending_entry_exit_resume']=self.state.get('accepting_entries',False)
                            self.state['accepting_entries']=False
                    self.save()
                except (ValueError,RuntimeError,AttributeError) as error:
                    owned['trailing_error']=str(error)
            if self.state.get('running') and c and not owned and not pending and self.state.get('accepting_entries') and hasattr(self.adapter,'warm_options'):
                self.adapter.warm_options(c)
            if self.state.get('running') and c and owned and not owned.get('exit_requested') and any(c.get(k) is not None for k in ('spot_target','spot_stop')):
                try:
                    price,stamp=self.adapter.live_price(c,self.clock())
                    if not 0<=self.clock()-stamp<=15:raise ValueError('Fresh underlying tick required for hard boundary.')
                    reason=hard_exit(price,owned['direction'],c)
                    if reason:
                        owned.update(exit_requested=True,exit_reason=reason,exit_event_at=stamp)
                        owned['exit_indicator_snapshot']=self.indicator_snapshot(dict(close=price,market_event_at=stamp,provisional=True),reason)
                        self.state['last_exit_bar']=int(stamp//TIMEFRAMES[c['timeframe']])*TIMEFRAMES[c['timeframe']]
                        if p:p.update(exit_requested=True,exit_reason=reason,exit_event_at=stamp)
                        else:
                            self.state['pending_entry_exit_reason']=reason
                            self.state['pending_entry_exit_resume']=self.state.get('accepting_entries',False)
                            self.state['accepting_entries']=False
                        self.save()
                except (ValueError,RuntimeError,AttributeError) as error:
                    self.state['hard_boundary_error']=str(error)
            if self.state.get('running') and c and c.get('intrabar_entries',False) and owned and not owned.get('exit_requested') and not after_cutoff(self.clock(),self.state.get('config')) and hasattr(self.adapter,'forming'):
                try:
                    rows = self.adapter.candles(c)
                    tick = self.adapter.host_tick_size(c['underlying'])
                    analyzed = self.current_analysis(rows,c,tick)
                    self.state['renko_engine'] = analyzed
                    price,stamp = self.adapter.live_price(c,self.clock())
                    sig = ema_exit_observation(analyzed,price,stamp,c,self.clock())
                    if c.get('ema_exit_length',10)!=10:
                        length=c['ema_exit_length']
                        base=self.exit_ema(rows,c)
                        sig.update(ema_exit=2/(length+1)*price+(1-2/(length+1))*base,ema_exit_length=length)
                    sig['ema_exit_enabled']=c.get('ema_exit_enabled',True)
                    reason='EMA'+str(c.get('ema_exit_length',10))+'_INTRABAR_BREACH'
                    if ema_adverse(sig,owned['direction']):
                        owned['exit_indicator_snapshot']=self.indicator_snapshot(sig,reason)
                        self.state['last_exit_bar'] = sig['timestamp']
                        if p: p.update(exit_requested=True,exit_reason=reason,exit_event_at=sig['market_event_at'])
                        else:
                            self.state['pending_entry_exit_reason'] = reason
                            self.state['pending_entry_exit_resume'] = self.state.get('accepting_entries',False) and not self.state.get('squareoff_requested')
                            self.state['accepting_entries'] = False
                        self.save()
                except (ValueError,RuntimeError) as error:
                    self.state['intrabar_exit_error'] = str(error)
            previous=self.state.get('last_processed_bar')
            try:
                result=super().step()
                if not self.state.get('position') and not self.state.get('pending') and c and c.get('sideways_enabled') and (self.state.get('sideways_lock') or {}).get('active'):
                    self.state['status']='SIDEWAYS_LOCKED'
                    self.save()
                return result
            except ValueError as error:
                sig=self.state.get('last_signal') or {}
                key=self.signal_key(sig) if sig.get('cross_direction') else None
                interval=TIMEFRAMES[c['timeframe']] if c else 0
                event_at=sig.get('timestamp',0)+interval
                # The first subscription has no quote synchronously. Retry only this
                # still-fresh signal before any persisted order intent or dedup key.
                if ('stream has no tick for ' in str(error) and sig.get('cross_direction') and not sig.get('provisional')
                    and not self.state.get('pending') and not self.state.get('position') and key not in self.state.get('seen',[])
                    and self.state.get('eligible_since',self.clock())<event_at<=self.clock() and self.clock()-event_at<=interval):
                    self.state['last_processed_bar']=previous
                    for event in self.state.get('execution_signals',[]):
                        if event['key']==key and event.get('run_id')==self.state.get('run_id'):
                            event.update(status='WAITING FOR OPTION QUOTE',reason=str(error))
                    self.state.update(status='WAITING_FOR_OPTION_QUOTE',message=str(error)+' Fresh signal will retry until the next completed candle.')
                    self.save()
                    return
                for event in self.state.get('execution_signals',[]):
                    if event.get('key')==key and event.get('run_id')==self.state.get('run_id'):
                        event.update(status='BLOCKED',reason=str(error))
                self.save()
                raise

    def record_order(self,pending,status,filled=0,price=None):
        old=next((r for r in self.state.get('order_history',[]) if r['tag']==pending['tag']),{})
        observations=deepcopy(old.get('spot_fill_observations',[]))
        reconciliations=deepcopy(old.get('reconciliation_events',[]))
        if not reconciliations or (old.get('status'),old.get('filled'),old.get('average_price'),old.get('order_id'))!=(status,filled,price,pending.get('id')):
            reconciliations.append(dict(at=self.clock(),status=status,filled=filled,remaining=pending['order']['qty']-filled,average_price=price,broker_id=pending.get('id')))
        delta=filled-(old.get('filled',0) or 0)
        if delta>0:
            observation=dict(quantity=delta,price=None,observed_at=self.clock(),exchange_at=None,source='Underlying observation unavailable at fill confirmation')
            try:
                spot,stamp=self.adapter.live_price(self.state['config'],self.clock())
                observation.update(price=spot,exchange_at=stamp,source='Fresh underlying websocket at local option-fill confirmation')
            except (AttributeError,ValueError,RuntimeError):pass
            observations.append(observation)
        super().record_order(pending,status,filled,price)
        row=next(r for r in self.state['order_history'] if r['tag']==pending['tag'])
        position=pending['position']
        row.update({k:position.get(k) for k in ('option_type','strike','expiry_epoch','expiry_protection_at','run_id','entry_event_at','entry_mode','underlying_symbol')})
        row['spot_fill_observations']=observations
        row['reconciliation_events']=reconciliations
        snapshot_key='entry_indicator_snapshot' if self.is_entry_order(pending['order'],pending['position']) else 'exit_indicator_snapshot'
        row['indicator_snapshot']=deepcopy(old.get('indicator_snapshot') or position.get(snapshot_key))
        row['option_quote_observation']=deepcopy(old.get('option_quote_observation'))
        if row['option_quote_observation'] is None:
            try:row['option_quote_observation']={'observed_at':self.clock(),'quote':deepcopy(self.adapter.quote(row['symbol'])),'basis':'Socket quote observed at local intent/reconciliation; not a fill.'}
            except (AttributeError,ValueError,RuntimeError):pass
        if filled and self.is_entry_order(pending['order'],pending['position']) and not position.get('exposure_range'):
            position['exposure_range']=sideways.observe(None,old.get('first_fill_confirmed_at',self.clock()),None,None,self.clock())
            if self.state.get('position'):self.state['position']['exposure_range']=deepcopy(position['exposure_range'])
        row['exposure_range']=deepcopy((self.state.get('position') or position).get('exposure_range'))
        if filled:
            row['first_fill_confirmed_at']=old.get('first_fill_confirmed_at',self.clock())
            row['filled_at']=self.clock() if delta>0 else old.get('filled_at',self.clock())
        if self.state['config']['mode']=='PAPER':
            row['paper_order_id']='PAPER-ORDER-'+pending['tag']

    def complete_pending(self, filled, price):
        self.drain_position_ticks()
        # Disable the shared stepped/partial-target subsystem. Renko trailing
        # exits the entire confirmed owned remainder through existing execution.
        if self.is_entry_order(self.state['pending']['order'],self.state['pending']['position']):
            self.state['pending']['position']['trailing_config']={'trailing_enabled':False}
        exit_filled=not self.is_entry_order(self.state['pending']['order'],self.state['pending']['position']) and filled>0
        prior=deepcopy(self.state.get('position'))
        super().complete_pending(filled,price)
        if exit_filled and prior and not self.state.get('position'):
            exposure=prior.get('exposure_range')
            trade=next((t for t in trade_history(self.state.get('order_history',[])) if t['lifecycle_id']==prior['lifecycle_id']),None)
            if trade:
                lock=sideways.freeze(exposure,self.clock(),trade['costs'].get('realized_net'),TIMEFRAMES[self.state['config']['timeframe']],self.state['config'],trade['trade_id'],self.state['config']['underlying'])
                for row in self.state.get('order_history',[]):
                    if row.get('lifecycle_id')==prior['lifecycle_id']:
                        row['exposure_range']=deepcopy(exposure)
                        row['exposure_host_candles']=sideways.candle_count(exposure['entry_at'],self.clock(),TIMEFRAMES[self.state['config']['timeframe']]) if exposure else None
                        row['sideways_lock_trigger']=deepcopy(lock)
                if lock:
                    self.state['sideways_lock']=lock
                    self.state.setdefault('sideways_events',[]).append(deepcopy(lock))
                self.save()
        if exit_filled and not self.state.get('position'):
            self.state['rearm_after_exit']=True
            self.save()
        reason = self.state.pop('pending_entry_exit_reason',None)
        resume = self.state.pop('pending_entry_exit_resume',False)
        if reason:
            if self.state.get('position'): self.state['position'].update(exit_requested=True,exit_reason=reason)
            if resume and self.state.get('running') and not self.state.get('squareoff_requested') and not after_cutoff(self.clock(),self.state.get('config')): self.state['accepting_entries'] = True
            self.save()


    def submit(self, order, position, reason):
        self.drain_position_ticks()
        proximity=None
        if self.is_entry_order(order,position):
            c=self.state['config']
            if not self.sideways_entry_gate():raise ValueError('Sideways position range lock blocks new entries.')
            if any(c.get(k) is not None for k in ('spot_target','spot_stop')):
                spot,stamp=self.adapter.live_price(c,self.clock())
                if not 0<=self.clock()-stamp<=15:raise ValueError('Fresh underlying tick required to validate hard boundaries.')
                validate_spot_levels(spot,position['direction'],c)
            self.deadline()
            last = self.state['last_signal']
            if after_cutoff(self.clock(),self.state.get('config')):
                raise ValueError('Selected segment entry cutoff has passed.')
            if last.get('provisional') and hasattr(self.adapter,'forming'):
                c = self.state['config']
                candidate = provisional(self.state['renko_engine'], self.adapter.forming(c,self.adapter.candles(c),self.clock()),c,self.adapter.host_tick_size(c['underlying']),self.clock())
                if candidate['entry_direction'] != last['cross_direction'] or candidate['timestamp'] != last['timestamp']:
                    raise ValueError('Intrabar setup changed during preflight; no order.')
        if self.is_entry_order(order,position) and hasattr(self.adapter, 'forming'):
            # The entry setup and the configured exit must agree at submission.
            # This also covers confirmed entries and custom exit EMA lengths.
            c = self.state['config']
            price, stamp = self.adapter.live_price(c, self.clock())
            observation = ema_exit_observation(self.state['renko_engine'], price, stamp, c, self.clock())
            last=self.state['last_signal']
            if last.get('retest_signal') and not last.get('provisional'):
                aligned=observation['close']>observation['ema10']>observation['ema30'] if position['direction']=='BULLISH' else observation['close']<observation['ema10']<observation['ema30']
                if not last.get('signal_allowed') or not aligned:
                    raise ValueError('Confirmed retest direction/alignment changed at fresh-price preflight; no order.')
            length = c.get('ema_exit_length', 10)
            if length != 10:
                base = self.exit_ema(self.adapter.candles(c), c)
                alpha = 2 / (length + 1)
                observation['ema_exit'] = alpha * price + (1 - alpha) * base
            observation['ema_exit_enabled'] = c.get('ema_exit_enabled', True)
            if ema_adverse(observation, position['direction']):
                raise ValueError('Fresh underlying price already breaches configured exit EMA; no entry.')
            proximity=ema_proximity.check(c,price,observation['ema10'],self.state['renko_engine']['last'].get('host_atr'))
            if proximity:proximity.update(exchange_at=stamp,observed_at=self.clock())
        elif self.is_entry_order(order,position) and self.state['config'].get('ema_proximity_enabled'):
            raise ValueError('Fresh underlying observation required for EMA proximity preflight.')
        if self.is_entry_order(order,position):
            if self.state['last_signal'].get('retest_signal'):reason='EMA10_RETEST_BOUNCE'
            self.state['rearm_after_exit']=False
            metadata=getattr(self.adapter,'resolved_contracts',{}).get(order['symbol'],{})
            position={**position,**{k:metadata.get(k) for k in ('option_type','strike','expiry_epoch','expiry_protection_at')},'run_id':self.state.get('run_id'),'underlying_symbol':self.state['config']['underlying']}
            position['entry_indicator_snapshot']=self.indicator_snapshot(self.state['last_signal'],reason)
            if proximity:position['entry_indicator_snapshot']['ema_proximity_observation']=proximity
            position.update(entry_mode='CONFIRMED',entry_event_at=self.state['last_signal']['timestamp']+TIMEFRAMES[self.state['config']['timeframe']])
        elif not position.get('exit_indicator_snapshot'):
            position={**position,'exit_indicator_snapshot':self.indicator_snapshot(self.state.get('last_signal'),reason)}
        if self.is_entry_order(order,position) and self.state['last_signal'].get('provisional'):
            position={**position,'entry_mode':'INTRABAR','entry_event_at':self.state['last_signal']['market_event_at']}
        return super().submit(order,position,reason)

    def record_entry_assessment(self, sig, eligible, code, reason):
        c=self.state['config'];now=self.clock()
        fields=('timestamp','close','direction','ema10','ema30','ema_widening','entry_qualified',
                'entry_direction','entry_diagnostic','cross_direction','signal_allowed','adx',
                'rsi14','rsi14_slope','rsi_slope_pass','retest_signal','retest_ready',
                'retest_touched','retest_touch_evidence','retest_patterns','retest_bounce',
                'retest_rsi_blocked','provisional','market_event_at')
        record=dict(run_id=self.state.get('run_id'),underlying=c['underlying'],timeframe=c['timeframe'],
                    timestamp=sig['timestamp'],event_at=sig.get('market_event_at') if sig.get('provisional') else sig['timestamp']+TIMEFRAMES[c['timeframe']],
                    observed_at=now,eligible=bool(eligible),code=code,reason=reason,
                    history_revised_at=self.state.get('history_revised_at'),
                    signal={k:deepcopy(sig.get(k)) for k in fields if k in sig})
        self.state['latest_entry_assessment']=record
        records=self.state.setdefault('entry_assessments',[])
        identity=(record['run_id'],record['timestamp'],bool(sig.get('provisional')))
        old=next((r for r in records if (r['run_id'],r['timestamp'],bool(r['signal'].get('provisional')))==identity),None)
        if old:old.update(record)
        else:records.append(record)
        self.state['entry_assessments']=records[-120:]

    def fresh_cross(self, sig):
        p=self.state.get('position')
        if p:
            # Protective exits do not use an entry arming/reconnect watermark.
            # Reconsider a revised fresh threshold, but never resubmit a saved
            # exit intent; pending/exit_requested reconciliation owns that path.
            now=self.clock();seconds=TIMEFRAMES[self.state['config']['timeframe']]
            closed_at=sig['timestamp']+seconds
            token=hashlib.sha256(json.dumps([p.get('lifecycle_id',p.get('opened_at',p['symbol'])),sig['timestamp'],sig['close'],sig.get('ema_exit',sig.get('ema10')),sig.get('supertrend_cross_direction')]).encode()).hexdigest()
            prior=self.state.get('latest_exit_assessment') or {}
            if token==prior.get('token'):return False
            valid=0<=now-closed_at<=seconds
            self.state['latest_exit_assessment']=dict(token=token,timestamp=sig['timestamp'],observed_at=now,event_at=closed_at,
                eligible=valid,close=sig['close'],ema_exit=sig.get('ema_exit',sig.get('ema10')),
                ema_exit_length=self.state['config'].get('ema_exit_length',10),
                reason='Fresh completed protective-exit assessment.' if valid else 'Previously assessed or stale protective-exit candle.')
            self.save()
            cross=('BEARISH' if p['direction']=='BULLISH' else 'BULLISH') if ema_adverse(sig,p['direction']) else sig.get('supertrend_cross_direction')
            return valid and bool(cross)
        now=self.clock();c=self.state['config'];seconds=TIMEFRAMES[c['timeframe']]
        provisional=bool(sig.get('provisional'))
        event_at=sig.get('market_event_at',0) if provisional else sig['timestamp']+seconds
        prior=self.state.get('last_processed_bar')
        if not provisional and prior is not None and sig['timestamp']<=prior:
            # Polls and corrected historical output must not overwrite a real
            # decision or cause a second entry for this completed candle.
            return False
        gate=self.sideways_entry_gate()
        if not gate:code,reason='SIDEWAYS_LOCK','Recorded loss-range gate blocks entry.'
        elif event_at<=self.state.get('eligible_since',self.state.get('started_at',now)):
            code,reason='BEFORE_ELIGIBILITY','Candle/event predates the actual arming, reconnect or lock-release boundary.'
        elif not 0<=now-event_at<=(15 if provisional else seconds):
            code,reason='STALE_EVENT','Candle/event is outside the configured freshness window.'
        elif after_cutoff(now,c):code,reason='ENTRY_CUTOFF','Configured entry cutoff reached.'
        elif sig['timestamp']<=self.state.get('last_exit_bar',0):
            code,reason='EXIT_CANDLE','Entry is blocked on the same or an earlier exit candle.'
        elif not sig.get('cross_direction'):
            code=sig.get('entry_diagnostic') if not sig.get('entry_qualified') else 'NO_ENTRY_EVENT'
            reason='Setup passes; waiting for a new strategy entry event.' if code=='NO_ENTRY_EVENT' else 'Configured strategy gate: '+str(code)
        elif self.signal_key(sig) in self.state.get('seen',[]):
            code,reason='ALREADY_SUBMITTED','A durable order intent already consumed this signal.'
        else:code,reason='ELIGIBLE','Fresh post-arming strategy entry event; execution preflight still required.'
        eligible=code=='ELIGIBLE'
        self.record_entry_assessment(sig,eligible,code,reason)
        if not provisional:self.state['last_processed_bar']=sig['timestamp']
        self.remember_execution_signal(sig,eligible,reason)
        self.save()
        return eligible

    def remember_execution_signal(self,sig,eligible,reason=None):
        if not sig.get('cross_direction'):return
        key=self.signal_key(sig)
        rows=self.state.setdefault('execution_signals',[])
        if any(row['key']==key and row.get('run_id')==self.state.get('run_id') for row in rows):return
        c=self.state['config'];now=self.clock()
        event_at=sig.get('market_event_at') if sig.get('provisional') else sig['timestamp']+TIMEFRAMES[c['timeframe']]
        rows.append(dict(key=key,run_id=self.state.get('run_id'),underlying=c['underlying'],mode=c['mode'],timestamp=sig['timestamp'],event_at=event_at,
            direction=sig['cross_direction'],eligible=bool(eligible),provisional=bool(sig.get('provisional')),observed_at=now,
            status='ELIGIBLE' if eligible else 'NOT ELIGIBLE',reason=reason or ('Fresh post-arming entry signal; execution preflight still required.' if eligible else 'Already consumed, predates arming/reconnection, or is no longer fresh.')))
        self.state['execution_signals']=rows[-500:]
        self.save()

    def exit_reason_for(self, sig, position):
        reason='EMA'+str(self.state['config'].get('ema_exit_length',10))+'_CONFIRMED_BREACH' if ema_adverse(sig,position['direction']) else self.exit_reason if self.exit_signal(sig,position['direction']) else None
        assessment=self.state.get('latest_exit_assessment') or {}
        if reason and assessment.get('eligible') and assessment.get('timestamp')==sig['timestamp'] and self.exit_is_later(sig,position):
            position['exit_indicator_snapshot']=self.indicator_snapshot(sig,reason)
        return reason

    def exit_is_later(self, sig, position):
        return sig['timestamp'] >= position['entry_signal_timestamp'] if position.get('entry_mode') == 'INTRABAR' else super().exit_is_later(sig,position)

    def exit_signal(self, sig, direction):
        return not sig.get('is_forming') and (ema_adverse(sig,direction) or sig.get('supertrend_cross_direction') == ('BEARISH' if direction == 'BULLISH' else 'BULLISH'))

    def exit_ema(self,rows,c):
        rows=completed(rows)
        anchor=(self.state.get('renko_engine') or {}).get('anchor')
        if not rows or anchor is not None and rows[0]['timestamp']!=anchor:
            raise ValueError('Configured EMA exit requires full original host history; no reseed.')
        return confirmed_values(rows,c.get('ema_exit_length',10))[-1]['ema_exit']

    def current_analysis(self, rows, c, tick):
        """Recover a revised history atomically, never replay an entry/order.

        Only a complete chronological history beginning at the original anchor
        is eligible. Retain execution ownership, journal, quota and locks. The
        Historical replay cannot consume a new entry assessment or move the
        actual arming/reconnection boundary. Previously assessed bars remain
        consumed; the newest fresh candle goes through the normal entry gates.
        Missing history, malformed OHLC and identity failures still block.
        """
        saved = self.state.get('renko_engine')
        try:
            return analysis(rows, c, tick, saved)
        except HistoryRevision:
            confirmed = completed(rows)
            if not saved or not confirmed or confirmed[0]['timestamp'] != saved['anchor']:
                raise ValueError('Revised history recovery requires the full original anchor; entries remain blocked.')
            if not any(r['timestamp'] == saved['last']['timestamp'] for r in confirmed):
                raise ValueError('Revised history recovery requires the previously processed last candle.')
            prior_rows = [r for r in confirmed if r['timestamp'] <= saved['last']['timestamp']]
            stamps = {str(r['timestamp']) for r in prior_rows}
            if len(prior_rows) != saved['state']['count'] or not set(saved.get('price_fingerprints', {})).issubset(stamps):
                raise ValueError('Revised history recovery requires complete original coverage; entries remain blocked.')
            rebuilt = analysis(confirmed, c, tick)
            previous = {r['timestamp']: r for r in saved.get('rows', [])}
            changes = []
            for row in confirmed:
                stamp = str(row['timestamp'])
                prior_hash = saved.get('price_fingerprints', {}).get(stamp)
                old = previous.get(row['timestamp'])
                changed = prior_hash != price_fingerprint(row) if prior_hash else old and price_fingerprint(old) != price_fingerprint(row)
                if changed:
                    changes.append(dict(timestamp=row['timestamp'],
                        before={k:old.get(k) for k in ('open','high','low','close')} if old else None,
                        after={k:row[k] for k in ('open','high','low','close')}))
            now = self.clock()
            self.state['renko_engine'] = rebuilt
            # Indicator progress and execution consumption are independent.
            # Do not turn a routine OHLC amendment into a new arming boundary.
            self.state['history_revised_at'] = now
            record = dict(at=now, anchor=saved['anchor'], completed_bars=rebuilt['state']['count'],
                          changes=changes, old_last=deepcopy(saved['last']), new_last=deepcopy(rebuilt['last']),
                          policy='SAME_ANCHOR_REPLAY__UNASSESSED_FRESH_CANDLES_ONLY')
            self.state['history_recoveries'] = (self.state.get('history_recoveries', []) + [record])[-20:]
            self.event('HISTORY_RECOVERED', 'Revised completed prices rebuilt from the original history anchor. Previously assessed candles remain consumed; new fresh candles retain the arming/reconnection boundary.')
            return rebuilt

    def signal(self):
        c = self.state['config']
        tick = self.adapter.host_tick_size(c['underlying'])
        rows = self.adapter.candles(c)
        result = self.current_analysis(rows, c, tick)
        self.state['renko_engine'] = result
        sig = {**result['last'], 'supertrend_cross_direction': result['last']['cross_direction'], 'cross_direction': result['last']['entry_direction']}
        if not self.state.get('position') and self.state.get('rearm_after_exit') and result['last']['entry_qualified'] and result['last']['timestamp']>self.state.get('last_exit_bar',0):
            sig['cross_direction']=result['last']['direction']
        self.deadline()
        if c.get('intrabar_entries') and not sig.get('retest_signal') and not self.state.get('position') and self.state.get('accepting_entries'):
            sig = provisional(result,self.adapter.forming(c,rows,self.clock()),c,tick,self.clock())
            sig = {**sig, 'supertrend_cross_direction':None, 'cross_direction':sig['entry_direction']}
        sig.update(ema_exit=self.exit_ema(rows,c) if c.get('ema_exit_length',10)!=10 else sig['ema10'],ema_exit_length=c.get('ema_exit_length',10),ema_exit_enabled=c.get('ema_exit_enabled',True))
        if not c.get('ema_exit_enabled',True):sig['ema_exit_enabled']=False
        self.state['last_signal'] = sig
        self.save()
        return sig
