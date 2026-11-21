import os,sys,json,time,fcntl,runpy,subprocess
from pathlib import Path
ROOT=Path('/home/trading/sector-heatmap');AID='bf46fc364b610a0dfd338419e133cb41';BASE=ROOT/'.private/dashboard-login/accounts'/AID;SOURCE=BASE/'source'
audit=sorted(ROOT.glob('.private/fyers-reconciliation-reload-*'))[-1]
owner=json.loads((BASE/'dashboard-owner.lock').read_text())['pid']
env=dict(item.split('=',1) for item in Path(f'/proc/{owner}/environ').read_text().split('\0') if '=' in item)
for key in ['SECTOR_PULSE_WORKSPACE_REGISTRY','SECTOR_PULSE_WORKSPACE_ID','SECTOR_PULSE_WORKSPACE_BROKER','FYERS_TOKEN_FILE','XDG_CONFIG_HOME']:
 if key in env:os.environ[key]=env[key]
os.chdir(SOURCE);sys.path.insert(0,str(SOURCE))
from sector_heatmap.fyers_execution import _current_client
from sector_heatmap.workspaces import private_write
from sector_heatmap.service_restart import stopped_state_paths
from sector_heatmap.runner_job_history import record
state=SOURCE/'.private/renko-instances/4a8a4fa8e499c1b20def/state.json'
prepare=runpy.run_path(str(ROOT/'scripts/reconcile_confirmed_crude.py'))['prepare']
with open(state.with_suffix('.lock'),'a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 before,after,proof=prepare(state,ROOT/'.private/crude-close-evidence-20261022.json',_current_client())
 private_write(state,json.dumps(after,allow_nan=False));record(state,after)
 private_write(audit/'final-state.json',json.dumps(after,allow_nan=False))
# Repair only the stopped, flat NIFTY calculation at its original last candle.
from strategies.renko_supertrend.runner import Runner
from copy import deepcopy
nifty=SOURCE/'.private/renko-instances/9abcfe9c2d417c1e7efe/state.json'
class CalculationRepair(Runner):
 def save(self):pass
 def event(self,*args):pass
class NoTrading:
 def stop(self):pass
with open(nifty.with_suffix('.lock'),'a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 original=json.loads(nifty.read_text())
 if any(original.get(k) for k in ['running','position','pending','accepting_entries']):raise ValueError('NIFTY is not stopped and flat')
 saved=original['renko_engine'];cache=nifty.parent/'chart-history/514985e7615160f02421de94c01353a4824b9763c096ff2dcc3c1d36b3a35e4e.json'
 raw=json.loads(cache.read_text())['rows']
 rows=[dict(timestamp=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4]),volume=r[5] if len(r)>5 else None) for r in raw if r[0]<=saved['last']['timestamp']]
 calc=CalculationRepair(NoTrading(),nifty)
 rebuilt=calc.current_analysis(rows,original['config'],saved['identity']['tick_size'])
 signal_at=original['last_signal']['timestamp']
 signal=next(r for r in rebuilt['rows'] if r['timestamp']==signal_at)
 final=deepcopy(original);final['renko_engine']=rebuilt;final['last_signal']=signal
 final['history_recoveries']=calc.state.get('history_recoveries',[])
 final['history_revised_at']=time.time()
 final['stopped_calculation_repaired_at']=time.time()
 final['message']='Stopped while flat. Same-anchor completed history repaired; no runner rearmed.'
 private_write(audit/'nifty-original-state.json',json.dumps(original))
 private_write(nifty,json.dumps(final,allow_nan=False));record(nifty,final)
 print('Stopped NIFTY calculation repaired; Supertrend',signal['supertrend'],flush=True)
stopped_state_paths(SOURCE)
private_write(audit/'ready','Confirmed historical close; all runners stopped; calculation repaired')
# If the waiting replacement expired, launch this account with its existing environment.
alive=False
try:alive=Path(f'/proc/{owner}/stat').read_text().split(') ',1)[1][0]!='Z'
except FileNotFoundError:pass
if not alive:
 with open(BASE/'dashboard.log','a') as log:
  proc=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-B','heatmap_server.py'],cwd=SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 owner=proc.pid
report={'status':'WAITING','new_pid':owner,'broker_orders_submitted':0,'confirmed_exit_order_id':proof['order_id'],'exit_price':proof['price'],'audit_directory':str(audit)}
private_write(audit/'result.json',json.dumps(report));print(json.dumps(report),flush=True)
