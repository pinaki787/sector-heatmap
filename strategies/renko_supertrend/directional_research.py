"""Isolated completed-OHLC recovery-lock experiment. Never imported by runner."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .signals import Engine

IST = ZoneInfo('Asia/Kolkata')


class RecoveryLocks:
    """Strict completed-close proxy for fresh tick recovery, no wick ordering."""
    def __init__(self, policy):
        if policy not in ('none', 'either', 'directional'):
            raise ValueError('Unknown recovery policy')
        self.policy = policy
        self.locks = {}

    def loss(self, direction, high, low, at):
        if self.policy == 'none':
            return
        key = 'shared' if self.policy == 'either' else direction
        self.locks[key] = dict(direction=direction, high=high, low=low, at=at)

    def observe(self, close, at):
        released = []
        for key, lock in list(self.locks.items()):
            if at <= lock['at']:
                continue
            passed = (close > lock['high'] or close < lock['low']) if self.policy == 'either' else (
                close > lock['high'] if lock['direction'] == 'BULLISH' else close < lock['low'])
            if passed:
                released.extend(['BULLISH', 'BEARISH'] if key == 'shared' else [key])
                del self.locks[key]
        return released

    def allows(self, direction):
        return 'shared' not in self.locks and direction not in self.locks


def simulate(rows, policy, bps, seconds=60, max_candles=3):
    """All decisions at completed closes; ordinary fills at next contiguous open.

    Same EMA/sign/gap/ADX qualification as Engine. Exit consumes decision candle.
    After an exit or lock release, a still-qualified later bar may re-arm.
    Timed exit uses cutoff bar open; its subsequent wick is excluded from range.
    Locks persist across sessions; only observed strict recovery releases them.
    No per-run quota is invented for this research simulation.
    """
    if bps < 0 or seconds <= 0:
        raise ValueError('Invalid cost/timeframe')
    locks = RecoveryLocks(policy)
    position = None
    trades = []
    previous_setup = None
    pending = None
    skipped = []
    releases = []
    triggers = 0

    def exit_position(price, at, reason):
        nonlocal position, previous_setup, triggers
        sign = 1 if position['direction'] == 'BULLISH' else -1
        gross = sign * (price - position['price'])
        costs = (price + position['price']) * bps / 10000
        buckets = int(at // seconds - position['entry_time'] // seconds + 1)
        trade = dict(position, exit_time=at, exit_price=price, exit_reason=reason,
                     gross_points=gross, net_points=gross-costs, modeled_cost_points=costs,
                     host_candles=buckets)
        trades.append(trade)
        if gross-costs < 0 and buckets <= max_candles:
            locks.loss(position['direction'], position['high'], position['low'], at)
            triggers += policy != 'none'
        position = None
        previous_setup = None

    for row in rows:
        at = row['timestamp']
        clock = datetime.fromtimestamp(at, IST)
        cutoff = clock.replace(hour=15, minute=15, second=0, microsecond=0).timestamp()
        if pending:
            kind, expected, direction = pending
            pending = None
            if kind == 'exit':
                # An unexpected data gap uses the next observed open and is audited.
                exit_position(row['open'], at, 'EMA_OR_REVERSAL' if at == expected else 'DATA_GAP_EXIT')
            elif at == expected and at < cutoff:
                position = dict(direction=direction, price=row['open'], entry_time=at,
                                high=row['open'], low=row['open'],
                                entry_after_net_loss=bool(trades and trades[-1]['net_points'] < 0))
            else:
                skipped.append(dict(at=at, direction=direction, reason='NONCONTIGUOUS_OR_CUTOFF'))
        if position and (at + seconds >= cutoff or datetime.fromtimestamp(position['entry_time'], IST).date() < clock.date()):
            # Same legacy proxy convention: cutoff bar open, not its future close.
            exit_position(row['open'], at, 'TIMED_SQUARE_OFF_1515')
            previous_setup = None
            continue
        if position:
            position['high'] = max(position['high'], row['high'])
            position['low'] = min(position['low'], row['low'])
        unlocked = locks.observe(row['close'], at + seconds)
        releases.extend(dict(at=at+seconds, direction=d) for d in unlocked)
        setup = row['direction'] if row['entry_qualified'] else None
        onset = setup and (setup != previous_setup or setup in unlocked)
        previous_setup = setup
        if position:
            adverse = row['close'] < row['ema10'] if position['direction'] == 'BULLISH' else row['close'] > row['ema10']
            opposite = 'BEARISH' if position['direction'] == 'BULLISH' else 'BULLISH'
            if adverse or row.get('cross_direction') == opposite:
                pending = ('exit', at+seconds, None)
                previous_setup = None
            continue
        if onset and at+seconds < cutoff:
            if locks.allows(setup):
                pending = ('entry', at+seconds, setup)
            else:
                skipped.append(dict(at=at+seconds, direction=setup, reason='RECOVERY_LOCK'))
    return dict(trades=trades, skipped=skipped, releases=releases, lock_triggers=triggers,
                open_position=position, pending=pending, remaining_locks=locks.locks)


def summarize(result, days):
    selected = set(days)
    trades = [t for t in result['trades'] if datetime.fromtimestamp(t['entry_time'], IST).date().isoformat() in selected
              and datetime.fromtimestamp(t['exit_time'], IST).date().isoformat() in selected]
    equity = peak = drawdown = 0
    for trade in trades:
        equity += trade['net_points']
        peak = max(peak, equity)
        drawdown = max(drawdown, peak-equity)
    count = len(trades)
    in_split = lambda x: datetime.fromtimestamp(x['at'], IST).date().isoformat() in selected
    return dict(closed_trades=count, gross_points=sum(t['gross_points'] for t in trades),
                net_points=equity, expectancy_points=equity/count if count else None,
                max_drawdown_points=drawdown, win_rate=sum(t['net_points'] > 0 for t in trades)/count if count else None,
                skipped_entries=sum(in_split(x) and x['reason'] == 'RECOVERY_LOCK' for x in result['skipped']),
                released_directions=sum(in_split(x) for x in result['releases']),
                reentries_after_net_loss=sum(t['entry_after_net_loss'] for t in trades))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=60)
    args = parser.parse_args()
    if args.seconds not in (60, 300):
        parser.error('This experiment supports verified one/five minute datasets only.')
    cache = json.loads(args.cache.read_text())
    if not cache.get('complete') or cache.get('error'):
        raise ValueError('Require a complete cache without saved errors.')
    config = json.loads(args.config.read_text())
    if 'config' in config:
        config = config['config']
    config = {**config, 'timeframe': '1 minute' if args.seconds == 60 else '5 minutes', 'intrabar_entries': False}
    engine = Engine(config, .05)
    rows = [engine.update(dict(zip(('timestamp', 'open', 'high', 'low', 'close', 'volume'), c))) for c in cache['rows']]
    days = sorted({datetime.fromtimestamp(r['timestamp'], IST).date().isoformat() for r in rows})
    complete = [d for d in days if d < '2026-10-06']
    heldout, development = complete[-5:], complete[5:-5]
    if not development or len(heldout) != 5:
        raise ValueError('Insufficient sessions after warmup and historical holdout.')
    evaluation_rows = [r for r in rows if datetime.fromtimestamp(r['timestamp'], IST).date().isoformat() >= development[0]]
    report = dict(scope='Completed OHLC underlying proxy; not actual tick/option fills or profitability proof.',
                  config=config, source=str(args.cache.resolve()), source_sha256=hashlib.sha256(args.cache.read_bytes()).hexdigest(),
                  code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), bars=len(rows),
                  first_timestamp=rows[0]['timestamp'], last_timestamp=rows[-1]['timestamp'],
                  warmup_sessions=5, development_sessions=development, heldout_sessions=heldout,
                  heldout_caveat='Pre-existing historical holdout previously used for other hypotheses; not fresh untouched validation.',
                  cutoff='15:15 IST', max_loss_host_buckets=3, results={}, executions={})
    for policy in ('none', 'either', 'directional'):
        report['results'][policy] = {}
        for bps in (0, 1, 2, 5):
            result = simulate(evaluation_rows, policy, bps, args.seconds)
            report['results'][policy][str(bps)] = {split: summarize(result, selected) for split, selected in
                [('development', development), ('heldout', heldout)]}
            report['executions'][policy+':'+str(bps)] = result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report['results'], indent=2))


if __name__ == '__main__':
    main()
