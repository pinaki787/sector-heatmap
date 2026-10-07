#!/usr/bin/env python3
"""Archive committed source and built UI, never account or runtime state."""
import io,subprocess,sys,tarfile,gzip
from pathlib import Path
root=Path(__file__).resolve().parents[1]
output=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/sector-pulse.tar.gz').resolve()
if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip():raise SystemExit('Commit all intended source changes before packaging; keep private data ignored.')
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
source=subprocess.check_output(['git','archive','--format=tar','HEAD'],cwd=root)
dist=root/'client/dist'
if not (dist/'index.html').is_file():raise SystemExit('Build UI first: python3.11 setup.py')
output.parent.mkdir(parents=True,exist_ok=True)
epoch=int(subprocess.check_output(['git','show','-s','--format=%ct','HEAD'],cwd=root,text=True).strip())
with output.open('wb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as zipped, tarfile.open(fileobj=zipped,mode='w') as release:
    with tarfile.open(fileobj=io.BytesIO(source)) as tracked:
        for item in tracked:
            if any(part in {'.private','.env','.fyers.env','.venv','output','outputs','tmp','node_modules'} for part in Path(item.name).parts):raise SystemExit('Private/generated path tracked: '+item.name)
            original=item.name;content=tracked.extractfile(item) if item.isfile() else None;item.name='sector-pulse/'+original;item.uid=item.gid=0;item.uname=item.gname='';item.mtime=epoch
            release.addfile(item,content)
    for file in sorted(dist.rglob('*')):
        if file.is_file():
            item=release.gettarinfo(str(file),arcname='sector-pulse/client/dist/'+str(file.relative_to(dist)));item.uid=item.gid=0;item.uname=item.gname='';item.mtime=epoch
            with file.open('rb') as data:release.addfile(item,data)
    stamp=(commit+'\n').encode();item=tarfile.TarInfo('sector-pulse/RELEASE_COMMIT');item.size=len(stamp);item.mtime=epoch;release.addfile(item,io.BytesIO(stamp))
print(str(output)+' source '+commit)
