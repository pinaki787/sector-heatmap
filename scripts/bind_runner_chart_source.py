from pathlib import Path
p=Path('sector_heatmap/web.py');s=p.read_text();begin=s.index('            if path == "/api/renko-supertrend/chart":');end=s.index('            if path == "/api/ema-band/runner":',begin);part=s[begin:end]
old="                    from strategies.renko_supertrend import mtf_rsi\n"
assert part.count(old)==1;part=part.replace(old,old+"                    requested_run = (query.get('confirmed_run_id') or [''])[0]\n")
part=part.replace("if config.get('chart_entry_guards') and mtf_rsi.enabled(config):","if not requested_run and config.get('chart_entry_guards') and mtf_rsi.enabled(config):")
part=part.replace("if config.get('chart_entry_guards') and config.get('higher_timeframe_enabled'):","if not requested_run and config.get('chart_entry_guards') and config.get('higher_timeframe_enabled'):")
part=part.replace("if config.get('chart_zone_target_enabled'):","if not requested_run and config.get('chart_zone_target_enabled'):")
start=part.index("                    analyzed,rows,forming_rows,history = ")
finish=part.index("                    history_error=history['history_error']",start)
replacement="""                    confirmed_source = None
                    if requested_run:
                        from strategies.renko_supertrend.confirmed_feed import bind_confirmed
                        from strategies.renko_supertrend.runner import TIMEFRAMES
                        confirmed_source = bind_confirmed(renko_supertrend, requested_run, symbol, timeframe)
                        rows = confirmed_source.pop('rows')
                        if not rows:
                            raise ValueError('Confirmed runner history unavailable; previous chart retained.')
                        analyzed = confirmed_source.pop('_engine')
                        config = confirmed_source.pop('_config')
                        # No history API/replay sits in the confirmed chart path.
                        # Full-range independent research remains the Draft view.
                        history = dict(display_oldest=rows[0]['timestamp'],display_latest=rows[-1]['timestamp'],
                            display_count=len(rows),initialization_bars=max(0,confirmed_source['count']-len(rows)),
                            source='Shared confirmed runner indicator snapshot · retained window',
                            analysis_revision=confirmed_source['revision'],history_error=None,
                            requested_from=(query.get('history_from') or ['runner anchor'])[0],
                            requested_to=(query.get('history_to') or ['recorded candle'])[0],
                            anchor_policy='Confirmed recurrence and OHLC published by the runner owner.',
                            intrabar_history='Provisional live previews never change confirmed state.',
                            data_quality={'analysis_available':True})
                        forming_rows=[]
                        try:
                            # Nonblocking shared read also starts a missing cache
                            # warmup in the background; failure cannot hide the
                            # already available confirmed indicator snapshot.
                            shared_rows=renko_chart_broker.candles({'underlying':symbol,'timeframe':timeframe})
                            forming_rows=[r for r in shared_rows if r.get('is_forming') and r['timestamp']+TIMEFRAMES[timeframe]>time.time()]
                        except (ValueError,RuntimeError):pass
                    else:
                        analyzed,rows,forming_rows,history = renko_chart_history.load(ema_readonly_client(),symbol,timeframe,
                            str((query.get('history_preset') or ['45'])[0]),str((query.get('history_from') or [''])[0]),str((query.get('history_to') or [''])[0]),
                            {**config,'underlying':symbol,'timeframe':timeframe},tick)
"""
part=part[:start]+replacement+part[finish:];p.write_text(s[:begin]+part+s[end:])
p=Path('renko-supertrend.js');s=p.read_text()
old="chart_entry_guards:false"
# The auxiliary higher-timeframe chart is explicit research, not the host runner.
s=s.replace(old,"chart_entry_guards:false,confirmed_run_id:''")
p.write_text(s)
print('Confirmed chart path bypasses history API and independent indicator replay.')
