from pathlib import Path
p=Path('strategies/renko_supertrend/confirmed_feed.py');s=p.read_text()
old="def bind_confirmed(runner, requested_run, symbol, timeframe):\n"
new="""def publish_confirmed(runner):
    state = runner.state
    engine = state.get('renko_engine')
    if not engine or not state.get('run_id'):
        return
    key = (state['run_id'], id(engine), json.dumps(state.get('config'),sort_keys=True))
    if key == getattr(runner,'_published_confirmed_key',None):
        return
    exported = confirmed_export(state, include_rows=True)
    exported['_engine'] = deepcopy({k:engine[k] for k in ('state','last','anchor')})
    exported['_config'] = deepcopy(state.get('config') or {})
    # The immutable publication is replaced atomically, never edited by readers.
    # Holding the prior engine reference prevents object-ID reuse in the key.
    runner._published_confirmed_engine = engine
    runner._confirmed_publication = exported
    runner._published_confirmed_key = key


def bind_confirmed(runner, requested_run, symbol, timeframe):
    publication = getattr(runner,'_confirmed_publication',None)
    if publication is not None:
        if runner.state.get('run_id') != requested_run:
            raise ValueError('Runner identity changed; refresh the selected runner chart.')
        if publication['run_id'] != requested_run:
            raise CandlePending('New run confirmed publication warming up; previous chart retained.')
        if publication['symbol'] != symbol or publication['timeframe'] != timeframe:
            raise ValueError('Runner identity changed; refresh the selected runner chart.')
        # This read does not acquire the execution lock or perform broker IO.
        result = deepcopy(publication)
        if runner.state.get('run_id') != requested_run:
            raise ValueError('Runner identity changed; refresh the selected runner chart.')
        return result
"""
assert s.count(old)==1;p.write_text(s.replace(old,new,1))
p=Path('strategies/renko_supertrend/runner.py');s=p.read_text()
old="        self.adapter.on_tick=wake_on_tick\n"
new=old+"        from .confirmed_feed import publish_confirmed\n        publish_confirmed(self)\n"
assert s.count(old)==1;s=s.replace(old,new,1)
old="        self.state['last_signal'] = sig\n        self.save()"
new="        self.state['last_signal'] = sig\n        from .confirmed_feed import publish_confirmed\n        publish_confirmed(self)\n        self.save()"
assert s.count(old)==1;p.write_text(s.replace(old,new,1))
print('Confirmed chart publication no longer acquires the execution lock.')
