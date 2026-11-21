"""Offline reconciliation of proven historical fill; deliberately has no order API."""
import json,time
from copy import deepcopy
from pathlib import Path
from strategies.renko_supertrend.runner import Runner
from strategies.ema_crossover.external_close import confirmed_close
from sector_heatmap.fyers_history import account_read
class ReadOnlyEvidence:
 def __init__(self,client,evidence):self.client=client;self.evidence=evidence
 def positions(self):
  d=account_read(self.client,'positions')
  if d.get('s')!='ok' or not isinstance(d.get('netPositions'),list):raise ValueError('Fresh positions unavailable')
  return d['netPositions']
 def orders(self):
  d=account_read(self.client,'orderbook')
  if d.get('s')!='ok' or not isinstance(d.get('orderBook'),list):raise ValueError('Fresh orderbook unavailable')
  # Existing historical facts supplement only IDs absent from today's book.
  current=d['orderBook'];ids={str(r.get('id')) for r in current}
  return current+[r for r in self.evidence['orders'] if r['id'] not in ids]
 def stop(self):pass
class RepairRunner(Runner):
 def save(self):self.state['updated_at']=time.time()
 def snapshot(self):return deepcopy(self.state)
def prepare(state_path,evidence_path,client):
 original=json.loads(Path(state_path).read_text());evidence=json.loads(Path(evidence_path).read_text())
 if evidence['account_id']!='bf46fc364b610a0dfd338419e133cb41' or evidence['contract']!=original['position']['symbol']:raise ValueError('Wrong account or contract')
 adapter=ReadOnlyEvidence(client,evidence)
 verified=confirmed_close(original['position'],[],evidence['orders'])
 runner=RepairRunner(adapter,state_path,clock=lambda:verified['filled_at'])
 runner.state['squareoff_requested']=True
 if not runner.reconcile_external_stop():raise ValueError('Reconciliation not performed')
 final=runner.state
 if final.get('position') or final.get('pending') or final.get('running') or final.get('accepting_entries'):raise ValueError('Reconciliation did not stop flat')
 if final.get('run_id')!=original.get('run_id'):raise ValueError('Run ownership changed')
 final['historical_fill_reconciliation']={'recorded_at':time.time(),'evidence_source':evidence['source'],'exit_order_id':verified['order_id'],'exit_filled_at':verified['filled_at']}
 return original,final,verified
