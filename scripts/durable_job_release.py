"""Verify or install a reviewed source overlay. Never restarts services or trades.

The caller must separately obtain restart authorization and reconcile broker and
runner state before activation. Dry-run is the default; source changes require
--apply. All destination baselines are checked before the first write.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path

RENAMED={'renko-batch.py':'strategies/renko_supertrend/batch.py',
         'ema-runner.py':'strategies/ema_crossover/runner.py'}
NEW_FILES={'analysis-jobs.js','market-handoff.js',*[f'sector_heatmap/{name}.py' for name in
           ('persistent_jobs','job_http','exposure_guard','handoff_ai','market_handoff')]}


def digest(data):return hashlib.sha256(data).hexdigest()


def plan(stage,targets):
    stage=Path(stage).resolve()
    baseline=json.loads((stage/'baseline-sha256.json').read_text())
    expected={RENAMED.get(name,'sector_heatmap/'+name if name.endswith('.py') else name):value
              for name,value in baseline.items()}
    paths=sorted(set(expected)|NEW_FILES)
    sources={}
    for relative in paths:
        path=stage/relative
        if not path.exists():continue  # Baseline-only dependencies are not overwritten.
        if path.is_symlink() or not path.resolve().is_relative_to(stage):raise ValueError('Source escaped release directory.')
        data=path.read_bytes()
        if path.suffix=='.py':ast.parse(data)
        sources[relative]=data
    if not NEW_FILES<=sources.keys():raise ValueError('Release is missing durable-job modules or assets.')
    changes=[];conflicts=[]
    for target in targets:
        target=Path(target).resolve()
        if not (target/'heatmap_server.py').is_file():raise ValueError('Target is not a dashboard source directory.')
        for relative,data in sources.items():
            dest=target/relative
            if dest.is_symlink() or not dest.resolve().is_relative_to(target):raise ValueError('Destination escaped source directory.')
            before=dest.read_bytes() if dest.exists() else None
            if before==data:continue
            if relative in expected:
                valid=before is not None and digest(before)==expected[relative]
            else:valid=before is None
            if not valid:conflicts.append(str(dest));continue
            changes.append((dest,before,data))
    if conflicts:raise ValueError('Unreviewed destination drift: '+', '.join(conflicts))
    return changes


def install(changes,backup):
    backup=Path(backup)
    backup.mkdir(parents=True,mode=0o700,exist_ok=False)
    records=[]
    for index,(dest,before,after) in enumerate(changes):
        if before is not None:(backup/str(index)).write_bytes(before)
        records.append(dict(path=str(dest),before=digest(before) if before is not None else None,
                            after=digest(after),backup=str(index),mode=dest.stat().st_mode&0o777 if dest.exists() else 0o644))
    (backup/'manifest.json').write_text(json.dumps(records,indent=2))
    written=[]
    try:
        for record,(dest,before,after) in zip(records,changes):
            current=dest.read_bytes() if dest.exists() else None
            if current!=before:raise ValueError('Destination changed during installation: '+str(dest))
            dest.parent.mkdir(parents=True,exist_ok=True)
            temporary=dest.with_name(dest.name+'.durable-jobs.tmp')
            try:
                temporary.write_bytes(after);temporary.chmod(record['mode']);os.replace(temporary,dest)
            finally:temporary.unlink(missing_ok=True)
            written.append((record,dest,before))
    except BaseException:
        for record,dest,before in reversed(written):
            if before is None:dest.unlink()
            else:
                temporary=dest.with_name(dest.name+'.durable-rollback.tmp')
                temporary.write_bytes(before);temporary.chmod(record['mode']);os.replace(temporary,dest)
        raise
    return dict(files_changed=len(written),backup=str(backup),services_restarted=False,orders_submitted=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',required=True)
    parser.add_argument('--target',action='append',required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--backup')
    args=parser.parse_args()
    changes=plan(args.stage,args.target)
    if not args.apply:
        print(json.dumps(dict(dry_run=True,files_changed=len(changes),targets=args.target)));return
    if not args.backup:parser.error('--backup is required with --apply')
    print(json.dumps(install(changes,args.backup)))


if __name__=='__main__':main()
