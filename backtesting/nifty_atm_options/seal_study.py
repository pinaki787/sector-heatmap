"""Hash the credential-free replay inputs, source, caches and final artifacts."""
import hashlib,json
from pathlib import Path
root=Path.cwd();folder=root/'backtesting/nifty_atm_options'
paths=[p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='reproduction-manifest.json' and p.suffix!='.tmp']
paths.append(root/'backtesting/renko_sideways_entry/research.py')
manifest={str(p.relative_to(root)):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in sorted(paths)}
(folder/'reproduction-manifest.json').write_text(json.dumps(dict(schema_version=1,files=manifest),indent=2));print('Sealed research files',len(manifest))
