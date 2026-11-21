"""Add diagnostic timings to the already-staged price-publication candidates."""
from pathlib import Path
p=Path('.private/chart-order-rollouts/fyers-sensex-execution-alignment-20261119')
helpers="""
def _price_event_identity(row):
    return tuple(row.get(key) for key in ('source_generation','source_sequence','source_event_index','timestamp'))

def _remember_price_publication(runner, rows, timing):
    from collections import OrderedDict
    cache=getattr(runner,'_price_event_timings',None)
    if cache is None:
        cache=OrderedDict();runner._price_event_timings=cache
    for row in rows:
        cache[_price_event_identity(row)]=dict(timing)
    while len(cache)>2000:cache.popitem(last=False)

def _record_price_execution_timing(runner,row,started,elapsed,decision):
    import time
    # Diagnostics only: no event/quote timestamp or execution gate is changed.
    cached=getattr(runner,'_price_event_timings',{}).get(_price_event_identity(row))
    result=dict(run_id=runner.state.get('run_id'),event_at=row.get('market_event_at'),
                source_observed_at=row.get('source_observed_at'),
                source_sequence=row.get('source_sequence'),source_event_index=row.get('source_event_index'),
                decision=decision,execution_step_seconds=elapsed,recorded_at=runner.clock())
    if cached:
        result['publication']=dict(cached)
        result['queue_wait_seconds']=max(0,started-cached['queued_monotonic'])
        result['publication'].pop('queued_monotonic',None)
    observed=row.get('source_observed_at')
    age=runner.clock()-observed if isinstance(observed,(int,float)) and not isinstance(observed,bool) else None
    result['receive_to_record_seconds']=age if age is not None and age>=0 else None
    records=runner.state.setdefault('price_execution_timings',[])
    records.append(result)
    runner.state['price_execution_timings']=records[-120:]
    return result

"""
for filename in ('price_basis.candidate.py','fyers-price_basis.candidate.py'):
 path=p/filename;s=path.read_text()
 assert '_record_price_execution_timing' not in s
 s=s.replace('\ndef produce(runner,tick,received,generation,*,config=None):',helpers+'\ndef produce(runner,tick,received,generation,*,config=None):')
 old='    import json\n    config=deepcopy('
 new='    import json,time\n    publication_started=time.perf_counter()\n    config=deepcopy('
 assert s.count(old)==1;s=s.replace(old,new)
 old="    if runner.state.get('run_id')!=run_id or getattr(runner,'stop_requested',None) and runner.stop_requested.is_set():"
 new="    observed_at=time.perf_counter()\n"+old
 assert s.count(old)==1;s=s.replace(old,new)
 old="        for row in rows:runner.confirmed_price_events.put(deepcopy(row))"
 new="""        queued_at=time.perf_counter()
        _remember_price_publication(runner,rows,dict(
            observe_seconds=observed_at-publication_started,
            durable_history_seconds=queued_at-observed_at,
            queued_monotonic=queued_at))
        for row in rows:runner.confirmed_price_events.put(deepcopy(row))"""
 assert s.count(old)==1;s=s.replace(old,new)
 old="        for row in events:\n"
 new="        for row in events:\n            import time\n            execution_started=time.perf_counter()\n"
 assert s.count(old)==1;s=s.replace(old,new)
 old="            if not 0<=runner.clock()-row['market_event_at']<=15:\n"
 new=old+"                _record_price_execution_timing(runner,row,execution_started,0,'EXPIRED_ENTRY_EVENT')\n"
 assert s.count(old)==1;s=s.replace(old,new)
 old="                runner._candle_step()\n            except Exception as error:"
 new="""                runner._candle_step()
            except Exception as error:"""
 # Record finally so exceptions and successful order work are both observed.
 assert s.count(old)==1
 old="                runner.handle_step_error(error)\n                continue\n            if held"
 new="""                runner.handle_step_error(error)
                continue
            finally:
                _record_price_execution_timing(runner,row,execution_started,
                    time.perf_counter()-execution_started,runner.state.get('status','UNKNOWN'))
            if held"""
 assert s.count(old)==1;s=s.replace(old,new)
 path.write_text(s)
print('timing candidates staged only')
