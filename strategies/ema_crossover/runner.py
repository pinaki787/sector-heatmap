"""Independent opt-in runner. Durable intent precedes every broker mutation."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import fcntl
import hashlib
import json
import math
import os
import secrets
import threading
import time
from .signals import series, exit_on_close, rsi_sma_series, rsi_exit_on_close
from .valuation import amount, multiplier
from .trailing import settings as trailing_settings, initial as trailing_initial, advance as trailing_advance, allocation as trailing_allocation, target_quantity
from .history import position_history, verified_legacy_rows

IST = ZoneInfo('Asia/Kolkata')
TIMEFRAMES = {'1 minute': 60, '2 minutes': 120, '3 minutes': 180, '5 minutes': 300, '10 minutes': 600, '15 minutes': 900, '30 minutes': 1800, '1 hour': 3600}
TERMINAL = {1, 2, 5, 7}


def configuration(payload):
    if payload.get('strategy') != 'RSI_BASED_EMA_V1':
        raise ValueError('Reload the dashboard and review the current RSI based EMA rules before activation.')
    def whole(key, default=None):
        raw = payload.get(key, default)
        if isinstance(raw, bool) or str(raw) != str(int(raw)):
            raise ValueError(f'{key} must be a whole number.')
        return int(raw)
    c = dict(underlying=str(payload.get('underlying', '')).strip().upper(),
             timeframe=payload.get('timeframe', '5 minutes'), rsi_length=whole('rsi_length',14), ma_length=whole('ma_length',payload.get('sma_length',14)), ma_type=str(payload.get('ma_type','SMA')).upper(), max_trades=whole('max_trades', 2), lots=whole('lots'), mode=str(payload.get('mode', 'PAPER')).upper(),
             max_premium=None if payload.get('max_premium') in (None, '') else float(payload['max_premium']), daily_budget=None if payload.get('daily_budget') in (None, '') else float(payload['daily_budget']),
             label='RSI based '+str(payload.get('ma_type','SMA')).upper(), strategy='RSI_BASED_EMA_V1')
    for key in ('spot_target', 'spot_stop'):
        raw = payload.get(key)
        c[key] = None if raw in (None, '') else float(raw)
        if c[key] is not None and (isinstance(raw, bool) or not math.isfinite(c[key]) or c[key] <= 0):
            raise ValueError('Spot target and stop-loss must be positive prices or blank.')
    rsi_sma_series([], c['rsi_length'], c['ma_length'], c['ma_type'])
    if any(c.get(k) is not None for k in ('spot_target','spot_stop')):
        raise ValueError('RSI strategy exits only on the opposite completed RSI/MA crossover; clear legacy spot exits.')
    if not 1 <= c['max_trades'] <= 1000:
        raise ValueError('Maximum trades must be between 1 and 1000.')
    if c['mode'] not in {'PAPER', 'LIVE'} or c['timeframe'] not in TIMEFRAMES or not 1 <= c['lots'] <= 100:
        raise ValueError('Choose Paper/Live, a supported timeframe, and 1–100 whole lots.')
    if not c['underlying'].startswith(('NSE:', 'BSE:', 'MCX:')):
        raise ValueError('Select a FYERS master underlying.')
    if c['daily_budget'] is not None and (not math.isfinite(c['daily_budget']) or c['daily_budget'] <= 0):
        raise ValueError('Enter a positive daily loss budget.')
    if c['max_premium'] is not None and (not math.isfinite(c['max_premium']) or c['max_premium'] <= 0 or (c['daily_budget'] is not None and c['max_premium'] > c['daily_budget'])):
        raise ValueError('Optional premium cap must be positive and no greater than the daily budget.')
    c.update(trailing_settings(payload))
    return c


def validate_spot_levels(spot, direction, config):
    bullish = direction == 'BULLISH'
    target, stop = config.get('spot_target'), config.get('spot_stop')
    if target is not None and not (target > spot if bullish else target < spot):
        raise ValueError('Spot target must be above the entry close for a Call and below it for a Put.')
    if stop is not None and not (stop < spot if bullish else stop > spot):
        raise ValueError('Spot stop-loss must be below the entry close for a Call and above it for a Put.')


def spot_exit(candle, direction, config):
    if candle.get('is_forming'):
        return None
    target, stop = config.get('spot_target'), config.get('spot_stop')
    if target is None and stop is None:
        return 'EMA_CLOSE_EXIT' if exit_on_close(candle, direction) else None
    close, bullish = candle['close'], direction == 'BULLISH'
    if stop is not None and (close <= stop if bullish else close >= stop):
        return 'SPOT_STOP_EXIT'
    if target is not None and (close >= target if bullish else close <= target):
        return 'SPOT_TARGET_EXIT'
    return None


class Runner:
    def __init__(self, adapter, state_path, clock=time.time):
        self.adapter, self.path, self.clock = adapter, Path(state_path), clock
        self.lock, self.wake, self.thread, self.file_lock = threading.RLock(), threading.Event(), None, None
        self.preview_value = None
        self.state = dict(status='STOPPED', running=False, accepting_entries=False, config=None,
                          position=None, pending=None, last_signal=None, seen=[], events=[], losses={}, updated_at=None)
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text())
                if saved.get('schema') != 1 or not isinstance(saved.get('seen'), list):
                    raise ValueError('Unsupported runner state')
                self.state.update(saved)
                self.state.update(running=False, accepting_entries=False,
                                  status='RECOVERY_REQUIRED' if saved.get('pending') or saved.get('position') else 'STOPPED')
                self.state['message'] = 'Server restarted. Select settings and click Start Runner when you want to arm trading.'
            except Exception:
                self.state.update(status='STATE_CORRUPT', error='Saved EMA Cloud state is unreadable; resolve it before activation.')

    def save(self):
        self.state['schema'] = 1
        self.state['updated_at'] = self.clock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        with open(tmp, 'w') as f:
            os.chmod(tmp, 0o600)
            json.dump(self.state, f, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def event(self, status, message):
        self.state.update(status=status, message=message)
        self.state['events'] = (self.state['events'] + [dict(at=self.clock(), status=status, message=message)])[-100:]
        self.save()

    def snapshot(self):
        with self.lock:
            pnl = dict(unrealized=None, realized=self.state.get('realized_pnl', 0), basis='Executable bid; before fees', available=False)
            if self.state['position']:
                try:
                    pos = self.state['position']
                    bid = self.adapter.quote(pos['symbol'])['bid']
                    pnl.update(unrealized=amount(pos, pos['quantity'], bid-pos['entry_price']), available=True, updated_at=self.clock())
                except Exception:
                    pass
            else:
                pnl.update(unrealized=0, available=True)
            evidence=self.path.parent.parent/'output'
            def audit(name,default):
                try:return json.loads((evidence/name).read_text())
                except (OSError,ValueError):return default
            history=verified_legacy_rows(self.state.get('order_history',[]),self.state.get('events',[]),self.state.get('position'),self.state.get('config') or {},audit('position-history-valuation-evidence.json',{}),audit('position-history-ownership-evidence.json',[]))
            return {**deepcopy(self.state), 'pnl': pnl, 'position_history':position_history(history), 'runtime_revision': 'rsi-crossover-partial-trailing-v5', 'stream': self.adapter.stream_status() if hasattr(self.adapter, 'stream_status') else None, 'strategy': 'RSI_BASED_EMA_V1', 'scan_interval_seconds': 1, 'signal_policy':'COMPLETED_RSI_CROSSOVER_ONLY', 'live_available': self.adapter.live_enabled()}

    def preview(self, payload):
        config = configuration(payload)
        with self.lock:
            if self.state['status'] == 'STATE_CORRUPT':
                raise ValueError(self.state['error'])
            if self.state['running']:
                raise ValueError('Runner is already active. Stop new entries first and wait until flat.')
            if (self.state['position'] or self.state['pending']) and config != self.state['config']:
                raise ValueError('Recovery requires the original configuration; pending orders and positions are preserved.')
            if config['mode'] == 'LIVE' and not self.adapter.live_enabled():
                raise ValueError('The existing FYERS live runtime gate is disabled.')
            context = self.adapter.validate_config(config)
            if (self.state['position'] or self.state['pending']) and context.get('account_identity') != self.state.get('account_identity'):
                raise ValueError('Saved exposure belongs to a different FYERS account.')
            digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:10].upper()
            phrase = f"START {config['mode']} RSI BASED EMA {digest}"
            self.preview_value = dict(id=secrets.token_hex(16), config=config, confirmation=phrase,
                                      expires_at=self.clock()+120, context=context, trailing_allocation=trailing_allocation(config['lots']) if config.get('trailing_enabled') else None)
            return deepcopy(self.preview_value)

    def start(self, payload, background=True):
        with self.lock:
            p = self.preview_value
            if not p or payload.get('preview_id') != p['id'] or payload.get('confirmation') != p['confirmation'] or self.clock() > p['expires_at']:
                raise ValueError('Review a fresh activation preview and type its exact confirmation phrase.')
            if self.state['running'] or (self.thread and self.thread.is_alive()):
                raise ValueError('Runner is already active or finishing shutdown.')
            config = p['config']
            if config['mode'] == 'LIVE' and not self.adapter.live_enabled():
                raise ValueError('FYERS live runtime gate is disabled.')
            context = self.adapter.validate_config(config)
            if context.get('account_identity') != p['context'].get('account_identity'):
                raise ValueError('FYERS account changed since preview; review again.')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(self.path.with_suffix('.lock'), 'a')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                raise ValueError('Another process owns the EMA Cloud runner.')
            self.file_lock = handle
            # Re-read after taking process ownership. Never overwrite another process's order intent.
            if self.path.exists():
                saved = json.loads(self.path.read_text())
                if saved.get('updated_at') != self.state.get('updated_at'):
                    self.release()
                    raise ValueError('Runner state changed in another process. Reload the server before activation.')
            try:
                self.adapter.start()
                self.preview_value = None
                if not self.state['position'] and not self.state['pending']:
                    self.state['trades_used'] = 0
                    self.state['realized_pnl'] = 0
                    self.state['squareoff_requested'] = False
                self.state.update(config=config, account_identity=context.get('account_identity'), running=True, accepting_entries=True, started_at=self.clock(),eligible_since=self.clock(),last_processed_bar=None,stream_was_connected=None,stream_generation=None)
                self.event('WATCHING', config['label']+' armed. Waiting for a new completed RSI crossover after arming; old crosses and forming candles are ignored.')
                if background:
                    self.wake.clear()
                    self.thread = threading.Thread(target=self.loop, name='ema-crossover-runner', daemon=True)
                    self.thread.start()
            except Exception:
                self.state.update(running=False, accepting_entries=False)
                self.release()
                raise
            return self.snapshot()

    def release(self):
        if self.file_lock:
            fcntl.flock(self.file_lock, fcntl.LOCK_UN)
            self.file_lock.close()
            self.file_lock = None

    def stop(self):
        with self.lock:
            if self.state['status'] == 'STATE_CORRUPT':
                raise ValueError(self.state['error'])
            self.state['accepting_entries'] = False
            self.state['squareoff_requested'] = True
            if self.state['position']:
                self.state['position']['exit_requested'] = True
                self.state['position']['exit_reason'] = 'MANUAL_SQUARE_OFF'
            if self.state['pending'] or self.state['position']:
                self.event('DRAINING', 'Stop requested: cancel pending entry remainder and square off runner-owned filled quantity. Waiting for broker confirmation.')
            else:
                self.state['running'] = False
                self.event('STOPPED', 'Stopped while flat.')
                self.adapter.stop()
                self.release()
            self.wake.set()
            return self.snapshot()

    def loop(self):
        while self.state['running']:
            scan_started = time.monotonic()
            try:
                self.step()
            except Exception as error:
                with self.lock:
                    # Keep ownership, pending intent, and position on all failures.
                    self.state['eligible_since'] = self.clock()
                    self.event('BLOCKED', str(error))
            self.wake.wait(max(0, 1 - (time.monotonic() - scan_started)))
            self.wake.clear()
        self.adapter.stop()
        self.release()

    def signal(self):
        c = self.state['config']
        data = rsi_sma_series(self.adapter.candles(c),c['rsi_length'],c['ma_length'],c['ma_type'])
        if len(data) <= c['rsi_length']+(c['ma_length']-1 if c['ma_type']=='SMA' else 0):
            raise ValueError('Insufficient completed candles for RSI/SMA warm-up.')
        last = data[-1]
        self.state['last_signal'] = {k:last[k] for k in ('timestamp', 'close', 'rsi', 'rsi_ma', 'rsi_sma', 'ma_type', 'direction', 'cross_direction')}
        return last

    def fresh_cross(self, sig):
        interval=TIMEFRAMES[self.state['config']['timeframe']]
        closed_at=sig['timestamp']+interval
        previous=self.state.get('last_processed_bar')
        if previous is not None and sig['timestamp']<=previous:return False
        self.state['last_processed_bar']=sig['timestamp']
        self.save()
        return bool(sig.get('cross_direction')) and self.state.get('eligible_since',self.state.get('started_at',self.clock())) < closed_at <= self.clock() and self.clock()-closed_at<=interval

    def record_order(self, pending, status, filled=0, price=None):
        order = pending['order']
        row = dict(tag=pending['tag'], order_id=pending.get('id'), symbol=order['symbol'],
                   side='BUY' if order['side'] == 1 else 'SELL', requested=order['qty'],
                   filled=filled, remaining=order['qty']-filled, average_price=price,
                   status=status, submitted_at=pending['submitted_at'], updated_at=self.clock(),
                   lifecycle_id=pending['position'].get('lifecycle_id'), strategy=pending['position'].get('strategy'), lot_size=pending['position'].get('lot_size'), quantity_multiplier=pending['position'].get('quantity_multiplier'), filled_at=self.clock() if filled else None, mode=self.state['config']['mode'], requested_type='MARKET', product=order['productType'], reason=pending['reason'])
        rows=self.state.setdefault('order_history', [])
        index=next((i for i,item in enumerate(rows) if item['tag']==pending['tag']),None)
        if index is None: rows.append(row)
        else: rows[index]=row
        self.state['order_history']=rows

    def submit(self, order, position, reason):
        self.adapter.validate_order(order)
        if order['side'] == 1:
            c = self.state['config']
            last = self.state['last_signal']
            if not self.state['accepting_entries'] or self.clock()-last['timestamp']-TIMEFRAMES[c['timeframe']] > TIMEFRAMES[c['timeframe']]:
                raise ValueError('Entry authorization or signal expired during preflight.')
        execution_quote = self.adapter.quote(order['symbol'])  # Recheck socket freshness immediately before persisting intent.
        tag = 'EC' + secrets.token_hex(10)
        if order['side']==1:
            position={**position,'lifecycle_id':tag,'strategy':self.state['config']['label'],'trailing_config':{k:self.state['config'].get(k) for k in ('trailing_enabled','trailing_mode','trailing_step')}}
        order = {**order, 'orderTag': tag}
        if order['side'] == 1:
            if self.state.get('trades_used', 0) >= self.state['config']['max_trades']:
                raise ValueError('Maximum entry trades reached.')
            self.state['trades_used'] = self.state.get('trades_used', 0) + 1
        self.state['pending'] = dict(order=order, tag=tag, id=None, position=position, reason=reason,
                                     submitted_at=self.clock(), cancel_requested=False)
        self.record_order(self.state['pending'], 'SUBMITTING')
        self.event('SUBMITTING', f"Submitting {reason}: {order['symbol']} qty {order['qty']} as MARKET (FYERS MPP).")
        if self.state['config']['mode'] == 'PAPER':
            self.complete_pending(order['qty'], execution_quote['ask' if order['side'] == 1 else 'bid'])
            return
        if not self.adapter.live_enabled():
            # Intent is retained on uncertainty, but a disabled gate is known to have sent nothing.
            self.state['pending'] = None
            self.event('BLOCKED', 'FYERS live runtime gate disabled; no order sent.')
            return
        try:
            result = self.adapter.place(order)
        except Exception:
            self.record_order(self.state['pending'], 'UNKNOWN')
            self.event('ORDER_STATUS_UNKNOWN', 'Submission response unavailable. Reconcile saved order tag; never blindly retry.')
            return
        if isinstance(result, dict) and result.get('s') == 'ok' and result.get('id'):
            self.state['pending']['id'] = str(result['id'])
            self.record_order(self.state['pending'], 'ACCEPTED')
            self.event('ORDER_PENDING', 'FYERS accepted the order. Waiting for confirmed fills.')
        elif isinstance(result, dict) and result.get('s') == 'error' and result.get('code') != 201:
            self.record_order(self.state['pending'], 'REJECTED')
            self.state['pending'] = None
            self.state.update(accepting_entries=False, running=False)
            self.event('ORDER_REJECTED', str(result.get('message', 'FYERS rejected order')))
        else:
            self.record_order(self.state['pending'], 'UNKNOWN')
            self.event('ORDER_STATUS_UNKNOWN', 'No definitive FYERS acknowledgement. Saved intent remains blocked for reconciliation.')

    def complete_pending(self, filled, price):
        pending = self.state['pending']
        if filled < 0 or filled > pending['order']['qty'] or (filled and (not math.isfinite(price) or price <= 0)):
            raise ValueError('Invalid confirmed fill quantity/price.')
        if pending['order']['side'] == 1 and filled:
            self.state['position'] = {**pending['position'], 'quantity': filled, 'entry_price': price,
                                      'opened_at': self.clock(), 'entry_order_id': pending['id']}
            self.state['position']['trailing']=trailing_initial(price,pending['position'].get('tick_size'),pending['position'].get('trailing_config',{}),filled,pending['position'].get('lot_size'))
        elif pending['order']['side'] == -1 and filled:
            p = self.state['position']
            pnl = amount(p, filled, price-p['entry_price'])
            p['quantity'] -= filled
            if pending['reason'] in ('STEP_TARGET_1','STEP_TARGET_2') and p.get('trailing'):
                stage=pending['reason'][-1]
                totals=p['trailing'].setdefault('target_filled',{})
                totals[stage]=totals.get(stage,0)+filled
            day = datetime.fromtimestamp(self.clock(), IST).date().isoformat()
            self.state['realized_pnl'] = self.state.get('realized_pnl', 0) + pnl
            self.state['losses'][day] = self.state['losses'].get(day, 0) + max(0, -pnl)
            if not p['quantity']:
                self.state['position'] = None
        previous=next((r for r in self.state.get('order_history',[]) if r['tag']==pending['tag']),{})
        status=previous.get('status') if previous.get('status') in ('CANCELLED','REJECTED','EXPIRED') else ('FILLED' if filled==pending['order']['qty'] else 'PARTIAL / CLOSED' if filled else 'CLOSED')
        self.record_order(pending,status,filled,price if filled else None)
        self.state['pending'] = None
        self.event('POSITION_OPEN' if self.state['position'] else 'FLAT', f"{pending['reason']}: confirmed {filled} filled at {price}; quantities reconciled.")

    def reconcile(self):
        p = self.state['pending']
        rows = self.adapter.orders()
        matches = [r for r in rows if (p['id'] and str(r.get('id')) == p['id']) or str(r.get('orderTag','')).split(':')[-1] == p['tag']]
        if len(matches) != 1:
            raise ValueError('Pending order not uniquely reconciled by ID/tag. No replacement order will be sent.')
        row = matches[0]
        if row.get('symbol') != p['order']['symbol'] or int(row.get('side',0)) != p['order']['side'] or row.get('productType') != p['order']['productType'] or int(row.get('qty',-1)) != p['order']['qty']:
            raise ValueError('FYERS order identity/quantity does not match saved intent.')
        p['id'] = str(row['id'])
        status, filled = int(row['status']), int(row.get('filledQty', 0))
        self.record_order(p, {1:'CANCELLED',2:'FILLED',4:'TRANSIT',5:'REJECTED',6:'PENDING',7:'EXPIRED'}.get(status,str(status)), filled, float(row.get('tradedPrice') or 0) if filled else None)
        self.save()
        if status in TERMINAL:
            if status == 2 and filled != p['order']['qty']:
                raise ValueError('Filled status has inconsistent quantity.')
            expected = filled if p['order']['side'] == 1 else self.state['position']['quantity'] - filled
            self.adapter.reconcile_position(p['order']['symbol'], expected)
            price = float(row.get('tradedPrice') or 0)
            self.complete_pending(filled, price)
            return
        # Cancel stale orders, paused entry orders, or entry orders at square-off. Await terminal status.
        cancel = self.clock()-p['submitted_at'] > 30 or (p['order']['side'] == 1 and (not self.state['accepting_entries']))
        if cancel and not p['cancel_requested']:
            self.adapter.validate_order(p['order'])
            p['cancel_requested'] = True
            self.event('CANCEL_PENDING', 'Requesting cancellation of unfilled remainder; confirmed fills remain owned.')
            if not self.adapter.live_enabled():
                p['cancel_requested'] = False
                raise ValueError('Live gate disabled; cannot cancel pending order.')
            self.adapter.cancel(p['id'])
        else:
            self.state['status'] = 'CANCEL_PENDING' if p['cancel_requested'] else 'ORDER_PENDING'
            self.save()

    def step(self):
        with self.lock:
            if not self.state['running']:
                return
            c = self.state['config']
            if self.state['pending']:
                self.reconcile()
                return
            p = self.state['position']
            if hasattr(self.adapter,'stream_status') and not self.state.get('squareoff_requested') and not (p and p.get('exit_requested')):
                stream=self.adapter.stream_status() or {}
                connected=bool(stream.get('connected'))
                generation=stream.get('generation')
                if not connected or self.state.get('stream_was_connected') is False or (generation is not None and self.state.get('stream_generation') is not None and generation!=self.state['stream_generation']):
                    self.state['eligible_since']=self.clock()
                self.state['stream_was_connected']=connected
                self.state['stream_generation']=generation
                if not connected:
                    self.state.update(status='WAITING_FOR_STREAM',message='Waiting for stream; old crossovers will not be replayed.')
                    self.save()
                    return
            if p:
                if self.state.get('squareoff_requested'):
                    p.update(exit_requested=True, exit_reason='MANUAL_SQUARE_OFF')
                    self.save()
                if c['mode'] == 'LIVE':
                    self.adapter.reconcile_position(p['symbol'], p['quantity'])
                if not p.get('exit_requested') and p.get('trailing'):
                    try:
                        trail,hit=trailing_advance(p['trailing'],self.adapter.quote(p['symbol']),self.clock())
                        p['trailing']=trail
                        p.pop('trailing_error',None)
                    except ValueError as error:
                        p['trailing_error']=str(error)
                        hit=False
                    if hit:
                        p.update(exit_requested=True,exit_reason='STEP_TRAILING_EXIT')
                        anchor=(self.state.get('last_signal') or {}).get('timestamp',p['entry_signal_timestamp'])
                        interval=TIMEFRAMES[c['timeframe']]
                        self.state['last_exit_bar']=anchor+int((self.clock()-anchor)//interval)*interval
                    self.save()
                if not p.get('exit_requested'):
                    sig = self.signal()
                    fresh = self.fresh_cross(sig)
                    # Never exit on the same completed bar that authorized entry.
                    later = sig['timestamp'] > p['entry_signal_timestamp']
                    reason = 'RSI_CLOSE_EXIT' if rsi_exit_on_close(sig,p['direction']) else None
                    if fresh and later and reason:
                        p['exit_requested'] = True
                        p['exit_reason'] = reason
                        p['exit_signal_timestamp'] = sig['timestamp']
                        # Do not open another position on this exit candle.
                        self.state['last_exit_bar'] = sig['timestamp']
                        self.save()
                target=target_quantity(p.get('trailing'),p['quantity']) if not p.get('exit_requested') else None
                if target:
                    stage,qty=target
                    quote=self.adapter.quote(p['symbol'])
                    trailing_advance(p['trailing'],quote,self.clock())
                    order=self.adapter.order(p['symbol'],qty,-1,quote)
                    self.submit(order,p,'STEP_TARGET_'+str(stage))
                    return
                if p.get('exit_requested'):
                    quote = self.adapter.quote(p['symbol'])
                    if p.get('exit_reason')=='STEP_TRAILING_EXIT':trailing_advance(p['trailing'],quote,self.clock())
                    order = self.adapter.order(p['symbol'], p['quantity'], -1, quote)
                    self.submit(order, p, p.get('exit_reason', 'RSI_CLOSE_EXIT'))
                else:
                    self.state['status'] = 'POSITION_OPEN'
                    self.state['message'] = 'Holding until a fresh opposite completed RSI crossover. Equality and continued relationships hold.'
                    self.save()
                return
            if not self.state['accepting_entries']:
                self.stop()
                return
            if self.state.get('trades_used', 0) >= c['max_trades']:
                self.state['accepting_entries'] = False
                self.event('TRADE_LIMIT_REACHED', 'Maximum entry trades reached. Existing exits remain managed; review and start again to authorize a new run.')
                self.stop()
                return
            now = datetime.fromtimestamp(self.clock(), IST)
            end = 23*60+30 if c['underlying'].startswith('MCX:') else 15*60+30
            if now.weekday() >= 5 or not 9*60+15 <= now.hour*60+now.minute < end:
                self.state['status'] = 'OUTSIDE_SESSION'
                return
            sig = self.signal()
            interval = TIMEFRAMES[c['timeframe']]
            closed_at = sig['timestamp']+interval
            # Consume each completed bar once; only new post-arming crossovers authorize entry.
            if not self.fresh_cross(sig) or sig['timestamp'] <= self.state.get('last_exit_bar', 0):
                self.state['status'] = 'WATCHING_NO_ENTRY'
                self.save()
                return
            key = f"RSI:{c['underlying']}:{c['timeframe']}:{c['rsi_length']}:{c['ma_type']}:{c['ma_length']}:{sig['timestamp']}"
            if key in self.state['seen']:
                return
            validate_spot_levels(sig['close'], sig['cross_direction'], c)
            contract = self.adapter.resolve(c, sig['cross_direction'])
            tick=contract.get('verified_tick_size',contract.get('tick_size'))
            if c.get('trailing_enabled'):trailing_initial(1,tick,c)
            quote = self.adapter.quote(contract['symbol'])
            qty = c['lots']*contract['lot_size']
            order = self.adapter.order(contract['symbol'], qty, 1, quote)
            premium = amount(contract, qty, quote['ask'])
            day = now.date().isoformat()
            if (c['max_premium'] is not None and premium > c['max_premium']) or (c['daily_budget'] is not None and premium+self.state['losses'].get(day,0) > c['daily_budget']):
                raise ValueError('Full option premium exceeds per-entry cap or remaining daily loss budget.')
            self.adapter.preflight(order, c)
            self.state['seen'] = (self.state['seen']+[key])[-5000:]
            self.save()
            position = dict(symbol=contract['symbol'], direction=sig['cross_direction'], lot_size=contract['lot_size'], quantity=qty,
                            quantity_multiplier=multiplier(contract),tick_size=tick,
                            entry_price=None, opened_at=None, entry_signal_timestamp=sig['timestamp'])
            self.submit(order, position, 'RSI_CLOSE_ENTRY')
