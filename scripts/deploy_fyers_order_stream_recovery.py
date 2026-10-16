"""Apply an approved notification-only patch and replace one flat FYERS worker."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import time
import urllib.request
import urllib.error


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--account-id',required=True)
    p.add_argument('--patch-source',required=True)
    p.add_argument('--expected-sha256',required=True)
    args=p.parse_args()
    root=Path('/home/trading/sector-heatmap')
    folder=root/'.private/dashboard-login/accounts'/args.account_id
    source=folder/'source'
    pid=json.loads((folder/'dashboard-owner.lock').read_text())['pid']
    env=dict(s.split('=',1) for s in Path(f'/proc/{pid}/environ').read_text().split('\0') if '=' in s)
    with sqlite3.connect('file:'+env['SECTOR_PULSE_WORKSPACE_REGISTRY']+'?mode=ro',uri=True) as db:
        registered=db.execute('SELECT broker,port FROM accounts WHERE id=?',(args.account_id,)).fetchone()
    if env.get('SECTOR_PULSE_WORKSPACE_ID')!=args.account_id or not registered or registered!=('FYERS',int(env['HEATMAP_PORT'])):
        raise SystemExit('Owning FYERS process identity changed.')
    if Path(f'/proc/{pid}/cwd').resolve()!=source:raise SystemExit('Unexpected process directory.')
    python=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')[0].decode()
    check="""
from sector_heatmap.fyers_execution import _current_client
from sector_heatmap.fyers_history import account_read
c=_current_client();p=account_read(c,'positions');o=account_read(c,'orderbook')
if p.get('s')!='ok' or o.get('s')!='ok':raise SystemExit('Broker reconciliation unavailable; restart cancelled.')
positions=[r for r in p.get('netPositions',[]) if float(r.get('netQty',0))!=0]
orders=[r for r in o.get('orderBook',[]) if int(r.get('status',0)) in (3,4,6)]
print('Broker preflight: open positions',len(positions),'pending orders',len(orders),flush=True)
if positions or orders:raise SystemExit('Broker exposure/pending orders; restart cancelled.')
"""
    subprocess.run([python,'-c',check],cwd=source,env=env,check=True,timeout=30)
    relative=Path('strategies/renko_supertrend/stream.py')
    target=source/relative
    before=target.read_bytes()
    if hashlib.sha256(before).hexdigest()!=args.expected_sha256:raise SystemExit('Deployed source changed; no replacement.')
    after=Path(args.patch_source).read_bytes();ast.parse(after)
    backup=root/'.private/order-stream-backups'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    backup.mkdir(parents=True,mode=0o700)
    shutil.copy2(target,backup/'account-stream.py')
    canonical=root/relative
    canonical_before=canonical.read_bytes()
    # Copy only if canonical is exactly the reviewed account baseline.
    if canonical_before!=before:raise SystemExit('Canonical source differs; review required.')
    shutil.copy2(canonical,backup/'canonical-stream.py')
    frozen=False;terminated=False
    try:
        os.kill(pid,signal.SIGSTOP);frozen=True
        states=[]
        for path in source.glob('.private/**/*state*.json'):
            try:s=json.loads(path.read_text())
            except (ValueError,OSError):continue
            if isinstance(s,dict) and (s.get('position') or s.get('pending')):
                raise RuntimeError('Saved exposure/pending order appeared; restart cancelled.')
            if isinstance(s,dict) and s.get('running'):states.append(str(path.relative_to(source)))
            dest=backup/'states'/path.relative_to(source/'.private')
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        (backup/'manifest.json').write_text(json.dumps(dict(old_pid=pid,account=args.account_id,running_states=states,policy='Restart preserves saved records; no automatic Live rearm.'),indent=2))
        for path in (target,canonical):
            tmp=path.with_suffix('.order-stream-approved.tmp');tmp.write_bytes(after);os.replace(tmp,path)
        # The successor waits for the old process's account ownership lock.
        wrapper="""
import runpy
import sector_heatmap.workspace_guard as m
original=m.lock_file
m.lock_file=lambda fd,blocking=False:original(fd,blocking=True)
guard=m.WorkspaceGuard.from_environment()
m.lock_file=original
factory=m.WorkspaceGuard.from_environment
def existing(cls):
 m.WorkspaceGuard.from_environment=factory
 return guard
m.WorkspaceGuard.from_environment=classmethod(existing)
runpy.run_path('heatmap_server.py',run_name='__main__')
"""
        with open(folder/'dashboard.log','a') as output:
            new=subprocess.Popen([python,'-c',wrapper],cwd=source,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        time.sleep(.3)
        if new.poll() is not None:raise RuntimeError('Replacement failed before handoff.')
        os.kill(pid,signal.SIGTERM);terminated=True
        os.kill(pid,signal.SIGCONT);frozen=False
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            if new.poll() is not None:raise RuntimeError('Replacement exited; inspect account log.')
            owner=json.loads((folder/'dashboard-owner.lock').read_text())['pid']
            if owner==new.pid:
                try:
                    with urllib.request.urlopen('http://127.0.0.1:'+env['HEATMAP_PORT']+'/',timeout=1) as response:ready=response.status==200
                except urllib.error.HTTPError as response:ready=response.code in (401,403)
                except OSError:ready=False
                if ready:
                    print(json.dumps(dict(status='READY',old_pid=pid,new_pid=new.pid,backup=str(backup),sha256=hashlib.sha256(after).hexdigest(),automatic_rearm=False)))
                    return
            time.sleep(.5)
        raise RuntimeError('Readiness timeout; no repeat restart attempted.')
    finally:
        if frozen:os.kill(pid,signal.SIGCONT)
        if not terminated:
            target.write_bytes(before);canonical.write_bytes(canonical_before)


if __name__=='__main__':main()
