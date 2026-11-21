#!/usr/bin/env python3
"""Preserve source-only deployed variants without touching services or credentials."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tarfile
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {'.py','.js','.cjs','.mjs','.css','.html','.pine','.md','.sh','.bat','.service','.toml','.yaml','.yml'}
EXCLUDED = {'data','evidence','cache','frozen-source','node_modules','__pycache__','output','outputs','tmp','release-private'}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def safe(path):
    p = Path(path)
    return not p.is_absolute() and '..' not in p.parts and not any(v.startswith('.') and v not in {'.env.example','.fyers.env.example','.gitignore','.gitattributes'} for v in p.parts)

def source_file(path):
    if path.startswith("deploy/live-source-snapshots/"):return False
    p = Path(path)
    return safe(path) and not EXCLUDED.intersection(p.parts) and (p.suffix in SUFFIXES or path in {'chart-shared-indicators.json','release-source-files.json','requirements.txt','requirements.lock','requirements-telegram.txt','requirements-research.txt'})

def baseline(revision, modes=None):
    data = subprocess.check_output(['git','archive',revision],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        if modes is not None:modes.update({m.name:m.mode for m in archive if m.isfile() and safe(m.name)})
        return {m.name:archive.extractfile(m).read() for m in archive if m.isfile() and safe(m.name)}

def verify(folder):
    manifest = json.loads((folder/'manifest.json').read_text())
    count = 0
    for entry in manifest['workspaces']:
        for path, item in entry['overrides'].items():
            if not safe(path):raise ValueError('Unsafe source path')
            obj = item['object']
            if not safe(obj):raise ValueError('Unsafe object path')
            if digest((folder/obj).read_bytes()) != item['sha256']:raise ValueError('Source object checksum mismatch')
            count += 1
    return manifest, count

def capture(folder):
    if folder.exists():raise ValueError('Snapshot destination already exists')
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    original = baseline(revision)
    registry = ROOT/'.private/dashboard-login/registry.sqlite3'
    with sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True) as db:
        accounts = db.execute('SELECT id,broker,port FROM accounts ORDER BY port').fetchall()
    sources = [('shared','SHARED',8080,ROOT)] + [(aid,broker,port,registry.parent/'accounts'/aid/'source') for aid,broker,port in accounts]
    manifest = dict(schema=1,captured_at=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),baseline_commit=revision,
        scope='Source files on disk; excludes credentials, account state, market data and in-memory process state. No deployment or runner action.',workspaces=[])
    folder.mkdir(parents=True)
    for aid,broker,port,source in sources:
        overrides = {}; missing = []
        paths = {p for p in original if source_file(p)}
        for top in [source,source/'sector_heatmap',source/'strategies',source/'scripts']:
            if not top.exists():continue
            iterator = top.iterdir() if top == source else top.rglob('*')
            for item in iterator:
                if item.is_file() and not item.is_symlink():
                    name = item.relative_to(source).as_posix()
                    if source_file(name):paths.add(name)
        for name in sorted(paths):
            p = source/name
            if not p.is_file():
                if name in original:missing.append(name)
                continue
            if p.is_symlink():raise ValueError('Symlink source cannot be archived: '+name)
            content = p.read_bytes()
            if content == original.get(name):continue
            # Fail closed on obvious embedded secrets; never print their contents.
            if re.search(rb'sk-(?:proj-)?[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',content):
                raise ValueError('Potential embedded secret in source: '+name)
            checksum = digest(content);obj = 'objects/'+checksum+Path(name).suffix
            target = folder/obj;target.parent.mkdir(exist_ok=True)
            target.write_bytes(content)
            overrides[name] = dict(object=obj,sha256=checksum,size=len(content),executable=bool(p.stat().st_mode & 0o111))
        manifest['workspaces'].append(dict(workspace=aid,broker=broker,port=port,overrides=overrides,missing=missing))
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    _,count = verify(folder)
    print(json.dumps(dict(workspaces=len(sources),overrides=count,objects=len(list((folder/'objects').glob('*'))))))

def restore(folder,workspace,destination):
    manifest,_ = verify(folder)
    entry = next(r for r in manifest['workspaces'] if r['workspace']==workspace)
    if destination.exists():raise ValueError('Restore requires a new, empty destination path')
    modes = {}
    files = baseline(manifest['baseline_commit'], modes)
    for name in entry['missing']:files.pop(name,None)
    for name,item in entry['overrides'].items():files[name]=(folder/item['object']).read_bytes()
    destination.mkdir(parents=True)
    for name,content in files.items():
        if not safe(name):raise ValueError('Unsafe baseline path')
        p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
        executable = entry['overrides'][name]['executable'] if name in entry['overrides'] else bool(modes.get(name,0) & 0o111)
        p.chmod(0o755 if executable else 0o644)
    print('Restored source only. No credentials, services, runners or orders activated.')

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['capture','verify','restore']);p.add_argument('folder',type=Path)
    p.add_argument('--workspace');p.add_argument('--destination',type=Path)
    a=p.parse_args()
    if a.action=='capture':capture(a.folder)
    elif a.action=='verify':
        m,n=verify(a.folder);print(json.dumps(dict(workspaces=len(m['workspaces']),overrides=n,verified=True)))
    else:
        if not a.workspace or not a.destination:p.error('restore requires workspace and destination')
        restore(a.folder,a.workspace,a.destination)
