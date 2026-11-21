"""Approved Handoff coordinator restart with policy and order-state preservation."""
from pathlib import Path
import sqlite3,json,subprocess,time,socket,datetime
root=Path(__file__).resolve().parents[1]
out=root/'output/handoff-source-allocation-20261030';out.mkdir(exist_ok=True)
before=[]
for p in sorted((root/'.private/dashboard-login/accounts').glob('*/handoff-schedule.sqlite3')):
 with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True) as db:
  policy=db.execute('SELECT body FROM policy WHERE id=1').fetchone()
  if not policy:continue
  receipts=db.execute('SELECT state,count(*) FROM receipts GROUP BY state').fetchall()
  if any(state in {'SUBMITTING','UNCERTAIN','PROTECTION_PENDING'} and count for state,count in receipts):
   raise RuntimeError('Handoff has unresolved order intent; restart withheld for reconciliation: '+p.parent.name)
  before.append({'account':p.parent.name,'policy_raw':policy[0],'receipts':receipts})
(out/'restart-policy-before.json').write_text(json.dumps(before,indent=2));(out/'restart-policy-before.json').chmod(0o600)
# A status revision lets the authenticated hosted response prove the new runtime.
for source in [root,*[a/'source' for a in (root/'.private/dashboard-login/accounts').iterdir() if (a/'source').is_dir()]]:
 p=source/'sector_heatmap/handoff_runtime.py'
 if not p.exists():continue
 s=p.read_text();needle='        value=item["schedule"].status()'
 if "'shared-broker-handoff-20261030-v1'" not in s:
  if needle not in s:raise RuntimeError('Runtime status anchor differs: '+str(source))
  s=s.replace(needle,needle+"\n        value['runtime_revision']='shared-broker-handoff-20261030-v1'",1);p.write_text(s)
old=subprocess.check_output(['systemctl','show','sector-pulse-notification-admin.service','-p','MainPID','--value'],text=True).strip()
subprocess.run(['sudo','-n','systemctl','restart','sector-pulse-notification-admin.service'],check=True,timeout=45)
new=subprocess.check_output(['systemctl','show','sector-pulse-notification-admin.service','-p','MainPID','--value'],text=True).strip()
for _ in range(80):
 try:
  with socket.create_connection(('127.0.0.1',8090),timeout=.3):break
 except OSError:time.sleep(.25)
else:raise RuntimeError('Handoff listener did not recover.')
checks=[]
for item in before:
 p=root/'.private/dashboard-login/accounts'/item['account']/'handoff-schedule.sqlite3'
 with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True) as db:current=db.execute('SELECT body FROM policy WHERE id=1').fetchone()[0]
 assert json.loads(current)==json.loads(item['policy_raw']),'Saved account policy changed'
 policy=json.loads(current)
 checks.append({'account':item['account'],'preserved':True,'enabled':policy.get('enabled'),'mode':policy.get('mode'),'capital':policy.get('capital')})
result={'service':'sector-pulse-notification-admin.service','old_pid':int(old),'new_pid':int(new),'listener_ready':True,'policy_checks':checks}
(out/'approved-restart-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
