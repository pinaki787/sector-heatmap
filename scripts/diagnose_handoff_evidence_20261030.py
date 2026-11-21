"""Read-only diagnosis of owned Handoff evidence transport; never submits."""
from pathlib import Path
import json,subprocess
from sector_heatmap.workspaces import WorkspaceStore,isolated_environment
root=Path(__file__).resolve().parents[1]
out=root/'output/handoff-source-allocation-20261030';out.mkdir(exist_ok=True)
store=WorkspaceStore(root/'.private/dashboard-login/registry.sqlite3')
with store.db() as db:account=dict(db.execute('SELECT * FROM accounts WHERE id=?',('b0041912d9d6f68d352814cbd24bf6da',)).fetchone())
folder=store.folder(account)
env=isolated_environment(account,folder,store.path,8079)
r=subprocess.run([str(root/'.venv/bin/python'),'-B','-m','sector_heatmap.handoff_broker_read','state'],cwd=folder/'source',env=env,capture_output=True,text=True,timeout=65)
for name,value in [('evidence-stdout.txt',r.stdout),('evidence-stderr.txt',r.stderr)]:
 p=out/name;p.write_text(value);p.chmod(0o600)
summary={'returncode':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr)}
try:
 value=json.loads(r.stdout);summary['valid_json']=True;summary['ok']=value.get('ok');summary['error']=value.get('error')
 if value.get('ok'):summary['verified']={k:value['state'].get(k) for k in ['positions_verified','orders_verified','holdings_verified','available_funds','used_capital','daily_loss']}
except Exception as e:
 summary['valid_json']=False;summary['parse_error_type']=type(e).__name__
summary['read_module_exists']=(folder/'source/sector_heatmap/handoff_broker_read.py').exists()
(out/'broker-evidence-diagnosis.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary))
