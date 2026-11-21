"""Profile a recorded price-Renko producer in an isolated output folder.

Reuses frozen state and synthetic next prices; no broker adapter, runner thread,
credentials, order methods, or production state writes are available.
"""
import argparse
import cProfile
import io
import json
from pathlib import Path
import pstats
from queue import Queue
from threading import Event
from time import perf_counter
from types import SimpleNamespace

from strategies.renko_supertrend.price_basis import produce


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state')
    parser.add_argument('output')
    parser.add_argument('--ticks', type=int, default=12)
    parser.add_argument('--no-profile', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.ticks <= 100:
        parser.error('--ticks must be between 1 and 100')
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('output must be a new or empty isolated directory')
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = json.loads(Path(args.state).read_text())
    engine = state['renko_engine']
    live = engine['state']['price_renko']
    # Rehydrate only the frozen reference captured with this exact engine.
    # Never fetch or manufacture a session reference for an offline profile.
    from strategies.renko_supertrend import session_auto
    if session_auto.selected(state['config']):
        reference = engine['state'].get('session_auto')
        if not reference:
            parser.error('recording lacks frozen Session Auto reference')
        state['config']['_session_auto_references'] = {
            str(int(reference['session_start'])): reference}
    runner = SimpleNamespace(
        state={'config': state['config'], 'run_id': state['run_id'],
               'renko_engine': engine},
        path=output / 'isolated-state.json',
        _price_stream_session=live['stream_session'],
        stop_requested=Event(), wake=Event(), confirmed_price_events=Queue())
    box = engine['state']['brick_box']
    direction = live['direction'] or 1
    start, sequence, level = live['last_exchange_at'], live['last_sequence'], live['level']
    samples = []
    profiler = cProfile.Profile()
    if not args.no_profile:
        profiler.enable()
    for index in range(1, args.ticks+1):
        stamp = start+index
        tick = dict(ltp=(level+direction*index)*box, exch_feed_time=stamp,
                    observation_sequence=sequence+index)
        before = perf_counter()
        rows = produce(runner, tick, stamp+.1, live['generation'])
        samples.append({'index': index, 'seconds': perf_counter()-before,
                        'bricks': len(rows)})
    if not args.no_profile:
        profiler.disable()
    if not args.no_profile:
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(30)
        (output/'profile.txt').write_text(stream.getvalue())
    result = {'kind': 'OFFLINE_SYNTHETIC_CONTINUATION_OF_RECORDED_STATE',
              'broker_calls': 0, 'orders': 0, 'profile_enabled': not args.no_profile, 'ticks': samples,
              'total_seconds': sum(s['seconds'] for s in samples),
              'queued_bricks': runner.confirmed_price_events.qsize()}
    (output/'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
