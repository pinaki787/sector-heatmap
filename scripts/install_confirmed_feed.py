"""Install the reviewed FYERS source candidate without restarting any process."""
from pathlib import Path
import hashlib,json,os,shutil
root=Path.cwd();stage=root/'.private/confirmed-feed-candidate-1792680287'
manifest=json.loads((stage/'manifest.json').read_text());account=Path(manifest['account'])
for name,digest in manifest['before'].items():
 assert hashlib.sha256((account/name).read_bytes()).hexdigest()==digest,('Source changed during review',name)
backup=stage/'account-before'
for name in manifest['files']:
 p=account/name
 if p.exists():
  original=backup/name;original.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,original)
for name in manifest['files']:
 p=account/name;p.parent.mkdir(parents=True,exist_ok=True)
 temp=p.with_name(p.name+'.confirmed-install');temp.write_bytes((stage/name).read_bytes())
 temp.chmod(p.stat().st_mode&0o777 if p.exists() else 0o644);os.replace(temp,p)
proof={name:hashlib.sha256((account/name).read_bytes()).hexdigest() for name in manifest['files']}
(stage/'source-installed.json').write_text(json.dumps({'phase':'SOURCE_INSTALLED_AWAITING_ACTIVATION','files':proof},indent=2))
print(json.dumps({'phase':'SOURCE_INSTALLED_AWAITING_ACTIVATION','files':len(proof),'backup':str(backup)}))
