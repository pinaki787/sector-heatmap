from pathlib import Path
def edit(name,old,new):
 p=Path(name);s=p.read_text();assert s.count(old)==1,(name,old[:90],s.count(old));p.write_text(s.replace(old,new,1))
edit('strategies/renko_supertrend/confirmed_feed.py',"""    def read(self, key, seconds, loader):""","""    def read(self, key, seconds, loader, with_revision=False):""")
edit('strategies/renko_supertrend/confirmed_feed.py',"""            error = entry.get('error')
        if rows is None:""","""            error = entry.get('error')
            revision = entry.get('revision')
        if rows is None:""")
edit('strategies/renko_supertrend/confirmed_feed.py',"""        return rows

    def _refresh""","""        return (rows,revision) if with_revision else rows

    def _refresh""")
edit('strategies/renko_supertrend/confirmed_feed.py',"""error=None, next_at=now+retry""","""error=None, waiting_for_close=late, next_at=now+retry""")
edit('strategies/renko_supertrend/confirmed_feed.py',"""'latest_completed','error','next_at')""","""'latest_completed','error','next_at','waiting_for_close')""")
edit('strategies/renko_supertrend/confirmed_feed.py',"""            if owner.on_tick:
                owner.on_tick(dict(raw))""","""            if owner.on_tick:
                try:
                    owner.on_tick(dict(raw))
                except Exception:
                    # An individual consumer failure cannot stop other charts
                    # or execution consumers from receiving market data.
                    pass""")
edit('strategies/renko_supertrend/runner.py',"""            rows = pool.read(key, TIMEFRAMES[c['timeframe']],
                             lambda:self.fetch_candles(_current_client(), *key, include_forming=True, force_refresh=True))""","""            rows, revision = pool.read(key, TIMEFRAMES[c['timeframe']],
                             lambda:self.fetch_candles(_current_client(), *key, include_forming=True, force_refresh=True),
                             with_revision=True)
            if not hasattr(self,'history_revisions'):self.history_revisions={}
            self.history_revisions[key] = revision""")
edit('strategies/renko_supertrend/runner.py',"""    def live_price(self, c, now):""","""    def candle_revision(self, c):
        return getattr(self,'history_revisions',{}).get((c['underlying'],c['timeframe']))

    def live_price(self, c, now):""")
edit('strategies/renko_supertrend/runner.py',"""        result = self.current_analysis(rows, c, tick)
        self.state['renko_engine'] = result""","""        revision = self.adapter.candle_revision(c) if hasattr(self.adapter,'candle_revision') else None
        source_key = (self.state.get('run_id'),json.dumps(c,sort_keys=True),tick,revision)
        if revision is not None and source_key == getattr(self,'_confirmed_source_key',None) and self.state.get('renko_engine'):
            result = self.state['renko_engine']
        else:
            result = self.current_analysis(rows, c, tick)
            self._confirmed_source_key = source_key if revision is not None else None
        self.state['renko_engine'] = result""")
edit('renko-supertrend.js',"""const candles=data.candles?.error?'retrieval recovering':data.candles?.busy?""","""const candles=data.candles?.error?'retrieval recovering':data.candles?.waiting_for_close?'awaiting completed broker candle':data.candles?.busy?""")
print('Confirmed engine advances once per shared history revision.')
