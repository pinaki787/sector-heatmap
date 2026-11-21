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
r=subprocess.run([str(root/'.venv/bin/python'),'-B','-c',"from pathlib import Path\nimport json,traceback\nfrom sector_heatmap.handoff_broker_read import read\ntry:\n value=read();print(json.dumps({'ok':True,'state':value}))\nexcept Exception as e:\n print(json.dumps({'ok':False,'error_type':type(e).__name__,'module':type(e).__module__,'auth_required':getattr(e,'auth_required',None),'frames':[{'file':Path(x.filename).name,'line':x.lineno,'function':x.name} for x in traceback.extract_tb(e.__traceback__)]}))\n"],cwd=folder/'source',env=env,capture_output=True,text=True,timeout=65)
for name,value in [('evidence-stdout.txt',r.stdout),('evidence-stderr.txt',r.stderr)]:
 p=out/name;p.write_text(value);p.chmod(0o600)
summary={'returncode':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr)}
try:
 value=json.loads(r.stdout);summary['valid_json']=True;summary['ok']=value.get('ok');summary['error']=value.get('error');summary['diagnostic']=value if not value.get('ok') else None
 if value.get('ok'):summary['verified']={k:value['state'].get(k) for k in ['positions_verified','orders_verified','holdings_verified','available_funds','used_capital','daily_loss']}
except Exception as e:
 summary['valid_json']=False;summary['parse_error_type']=type(e).__name__
summary['read_module_exists']=(folder/'source/sector_heatmap/handoff_broker_read.py').exists()
(out/'broker-evidence-diagnosis.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary))
