from pathlib import Path
import shutil,time
root=Path('/home/trading/sector-heatmap')
backup=root/'.private'/('confirmed-feed-backup-'+str(int(time.time())))
def edit(name,changes):
 p=root/name;s=p.read_text();target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
 for old,new in changes:
  assert s.count(old)==1,(name,old[:100],s.count(old))
  s=s.replace(old,new,1)
 p.write_text(s)

edit('strategies/renko_supertrend/runner.py',[
("    def stop(self):\n        # SDK close", """    def start(self):
        if getattr(self.fetch_candles, '_renko_shared_pipeline', False):
            from .confirmed_feed import quote_hub_for
            self._shared_quote_hub = quote_hub_for(self)
            self._shared_quote_hub.join(self)
            return
        return super().start()

    def tick(self, symbol):
        if getattr(self, '_shared_quote_hub', None):
            return self._shared_quote_hub.tick(self, symbol)
        return super().tick(symbol)

    def subscribe_all(self):
        if getattr(self, '_shared_quote_hub', None):
            hub = self._shared_quote_hub
            with hub.transport.lock:
                hub.transport.symbols.update(self.symbols)
            return hub.transport.subscribe_all()
        return super().subscribe_all()

    def stop(self):
        if getattr(self, '_shared_quote_hub', None):
            self._shared_quote_hub.leave(self)
            self._shared_quote_hub = None
            with self.lock:
                self.socket = None
                self.connected = False
                self.symbols.clear()
                self.ticks.clear()
            return
        # SDK close"""),
("        rows = self.fetch_candles(_current_client(), *key, include_forming=True)", """        if getattr(self.fetch_candles, '_renko_shared_pipeline', False):
            from .confirmed_feed import feed_for
            pool = feed_for(self.fetch_candles)
            rows = pool.read(key, TIMEFRAMES[c['timeframe']],
                             lambda:self.fetch_candles(_current_client(), *key, include_forming=True, force_refresh=True))
        else:
            rows = self.fetch_candles(_current_client(), *key, include_forming=True)"""),
("        if state:\n            result['initialization_anchor']", """        from .confirmed_feed import confirmed_export
        if state:
            result['confirmed_indicators'] = confirmed_export({**result,'renko_engine':state})
        if state:
            result['initialization_anchor']""")
])
edit('sector_heatmap/chart_feed_recovery.py',[
("        self._recover_chart(symbol, time.time())\n        return super().tick(symbol)", """        if not getattr(self, '_shared_quote_hub', None):
            self._recover_chart(symbol, time.time())
        return super().tick(symbol)""")
])
edit('sector_heatmap/web.py',[
("    def ema_band_candles(client, symbol, timeframe, include_forming=False):","    def ema_band_candles(client, symbol, timeframe, include_forming=False, force_refresh=False):"),
("            if cached and cached.get('refresh_bar') ==", "            if not force_refresh and cached and cached.get('refresh_bar') =="),
("    def ema_band_completed_candles(client, symbol, timeframe):", """    ema_band_candles._renko_shared_pipeline = True

    def ema_band_completed_candles(client, symbol, timeframe):"""),
("                    history_error=history['history_error']\n                    data_quality=history['data_quality']", """                    confirmed_source = None
                    requested_run = (query.get('confirmed_run_id') or [''])[0]
                    if requested_run:
                        from strategies.renko_supertrend.confirmed_feed import bind_confirmed
                        confirmed_source = bind_confirmed(renko_supertrend, requested_run, symbol, timeframe)
                        # Primary runner-bound indicators are published by the execution
                        # owner. Historical research cannot replace this recurrence.
                        rows = confirmed_source.pop('rows')
                        if not rows:
                            raise ValueError('Confirmed runner history unavailable; previous chart retained.')
                        analyzed = {**analyzed,'anchor':confirmed_source['anchor'],'last':rows[-1]}
                        history = {**history,'display_oldest':rows[0]['timestamp'],'display_latest':rows[-1]['timestamp'],
                                   'display_count':len(rows),'source':'Shared confirmed runner indicator snapshot',
                                   'analysis_revision':confirmed_source['revision']}
                    history_error=history['history_error']
                    data_quality=history['data_quality']"""),
("'initialization_anchor': analyzed['anchor'],", "'confirmed_source':confirmed_source, 'initialization_anchor': analyzed['anchor'],"),
("                        frame['bar_seconds'] = seconds", """                        frame['bar_seconds'] = seconds
                        requested_run = (query.get('confirmed_run_id') or [''])[0]
                        if requested_run and frame.get('runner',{}):
                            confirmed = frame['runner'].get('confirmed_indicators')
                            frame['confirmed_indicators'] = confirmed if confirmed and confirmed['run_id']==requested_run else None""")
])
print(backup)
