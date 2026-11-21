"""Operator-approved orphan reconciliation. Broker access is GET-only."""
from pathlib import Path
import argparse,json,sqlite3,subprocess,sys,os,time,fcntl
ROOT=Path('/home/trading/sector-heatmap');sys.path.insert(0,str(ROOT))
p=argparse.ArgumentParser();p.add_argument('--account',required=True);p.add_argument('--instance',required=True);p.add_argument('--tag',required=True);p.add_argument('--worker',action='store_true');p.add_argument('--offline',action='store_true');args=p.parse_args()
registry=ROOT/'.private/dashboard-login/registry.sqlite3'
if not args.worker:
 from sector_heatmap.workspaces import isolated_environment
 db=sqlite3.connect('file:'+str(registry)+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 account=dict(db.execute('select * from accounts where id=?',(args.account,)).fetchone());assert account['broker']=='DELTA_INDIA'
 folder=ROOT/'.private/dashboard-login/accounts'/args.account;env=isolated_environment(account,folder,registry,8080);env['PYTHONPATH']=str(ROOT)
 command=[sys.executable,str(Path(__file__).resolve()),'--worker','--account',args.account,'--instance',args.instance,'--tag',args.tag]+(['--offline'] if args.offline else [])
 sys.exit(subprocess.call(command,cwd=folder/'source',env=env))
from sector_heatmap.delta_india import DeltaIndia
from sector_heatmap.config import load_config
from sector_heatmap.file_lock import lock_file
from sector_heatmap.workspaces import private_write
from strategies.renko_supertrend.delta_broker import Broker
from strategies.renko_supertrend.delta_no_send import prove_absent,record,recover
from strategies.renko_supertrend.delta_runner import DeltaRunner
source=Path.cwd();state=source/'.private/renko-delta-instances'/args.instance/'renko-delta-state.json'
d=json.loads(state.read_text());pending=d.get('pending') or {}
assert pending.get('tag')==args.tag and pending.get('id') is None and d.get('position') is None
assert d.get('squareoff_requested') is True and d.get('accepting_entries') is False
assert pending['order']['orderTag']==args.tag
native=DeltaIndia(source/'.private/delta-india-paper.json',credentials=lambda:json.loads((source.parent/'credentials.json').read_text()))
private=native._private
def read_only(method,*pos,**kw):
 if method!='GET':raise AssertionError('Reconciliation cannot send, cancel or edit an order')
 return private(method,*pos,**kw)
native._private=read_only
broker=Broker(native,source/'.private/renko-delta-history')
proof=prove_absent(broker,pending,d['account_identity'])
if not args.offline:
 record(native,pending['order'],d['account_identity'],basis='OPERATOR_RECONCILED_ORPHAN',evidence={**proof,'authorization':'User explicitly requested reconciliation of retained orphan entry'})
 print(json.dumps(dict(status='PROOF_RECORDED',run_id=d['run_id'],tag=args.tag,proof=proof)))
else:
 # Only a stopped dashboard may have its retained lifecycle reconciled offline.
 owner=source.parent/'dashboard-owner.lock'
 with owner.open('a+') as owner_handle, state.with_suffix('.lock').open('a') as state_handle:
  lock_file(owner_handle.fileno(),blocking=False);lock_file(state_handle.fileno(),blocking=False)
  before=state.read_text();current=json.loads(before)
  assert current.get('pending')==pending and current.get('position') is None
  audit=ROOT/'.private'/('delta-no-send-reconciled-'+str(int(time.time())));audit.mkdir()
  private_write(audit/'before.json',before);private_write(audit/'proof.json',json.dumps(proof))
  runner=DeltaRunner(broker,state)
  assert recover(runner)
  final=json.loads(state.read_text());assert final['pending'] is None and final['position'] is None and final['running'] is False
  private_write(audit/'after.json',state.read_text())
  print(json.dumps(dict(status=final['status'],pending=final['pending'],position=final['position'],running=final['running'],audit=str(audit))))
