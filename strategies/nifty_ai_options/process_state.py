"""Exact-process recovery for user-started AI jobs; never starts a process."""
import json,os,signal
from pathlib import Path

def fingerprint(pid,proc=Path('/proc')):
    try:
        text=(proc/str(pid)/'stat').read_text()
        fields=text[text.rfind(')')+2:].split()
        if fields[0]=='Z':return None
        return fields[19]  # Linux field22: process start ticks, not wall clock.
    except (OSError,IndexError):return None

def identity(pid,directory,*,proc=Path('/proc')):
    started=fingerprint(pid,proc)
    if started is None:return None
    try:args=(proc/str(pid)/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
    except (OSError,UnicodeError):return None
    expected=str(Path(directory)/'config.json')
    if 'stream' not in args or '--config' not in args or '--output' not in args:return None
    try:
        if args[args.index('--config')+1]!=expected or args[args.index('--output')+1]!=str(directory):return None
    except IndexError:return None
    if not any(Path(a).name=='run.py' for a in args):return None
    return dict(pid=pid,start_ticks=started)

class RecoveredProcess:
    def __init__(self,record,directory):
        self.pid=record['pid'];self.record=record;self.directory=Path(directory)
    def poll(self):
        return None if identity(self.pid,self.directory)==self.record else 1
    def terminate(self):
        # Validate immediately before signalling; a reused PID never qualifies.
        if self.poll() is None:os.kill(self.pid,signal.SIGTERM)

def recover(owner,data,instrument=None):
    directory=Path(data)/'runs'/owner
    candidates=sorted((p for p in directory.iterdir() if p.is_dir() and (p/'config.json').exists()),reverse=True) if directory.exists() else []
    active=[];latest=None
    for path in candidates:
        config=json.loads((path/'config.json').read_text())
        if config.get('account')!=owner:raise ValueError('Saved AI run account differs from private owner')
        if config.get('_verification_only'):continue
        if instrument is not None and config.get('underlying')!=instrument:continue
        run=dict(id=path.name,directory=path,mode=config.get('execution_mode','PAPER'))
        if latest is None:latest=(run,None)
        record=path/'process.json'
        if record.exists():
            process=RecoveredProcess(json.loads(record.read_text()),path)
            if process.poll() is None:active.append((run,process))
    if len(active)>1:raise ValueError('Multiple AI processes require explicit reconciliation')
    return active[0] if active else latest or (None,None)

def assert_stopped(source,root=Path('/home/trading/sector-heatmap')):
    """Restart guard covers exact AI child processes and retained broker ledgers."""
    source=Path(source);data=root/'.private/nifty-ai-options'
    accounts=root/'.private/dashboard-login/accounts'
    if source==root:
        owners=[p.name for p in (data/'runs').iterdir() if p.is_dir()] if (data/'runs').exists() else []
    elif source.name=='source' and source.parent.parent==accounts:
        owners=[source.parent.name]
    else:return
    for owner in owners:
        if len(owner)!=32 or any(c not in '0123456789abcdef' for c in owner):continue
        for record_path in (data/'runs'/owner).glob('*/process.json'):
            record=json.loads(record_path.read_text())
            if identity(record.get('pid'),record_path.parent.resolve())==record:raise ValueError('Restart blocked: user-started AI Renko job '+record_path.parent.name+' is running; no restart was sent.')
        for directory in (data/'runs'/owner).iterdir() if (data/'runs'/owner).exists() else []:
            if not directory.is_dir():continue
            config_path=directory/'config.json'
            if not config_path.exists():continue
            config=json.loads(config_path.read_text())
            proof=directory/'preflight/preflight.json'
            if not proof.exists():proof=directory/'preflight.json'
            details=json.loads(proof.read_text()) if proof.exists() else {}
            key=owner if config.get('broker') in ('DELTA_INDIA','DHAN','MOTILAL_OSWAL') else details.get('account_sha256')
            if not isinstance(key,str) or len(key) not in (32,64) or any(c not in '0123456789abcdef' for c in key):continue
            for path in list((data/'runtime'/key).rglob('*.json'))+list((data/'runtime'/'instruments'/owner).rglob('*.json')):
                state=json.loads(path.read_text())
                if any(state.get(k) for k in ('position','pending','positions','closing_legs','detached_position','stop_verification_position')):
                    raise ValueError('Restart blocked: AI Renko retained position/pending intent for '+owner+' requires reconciliation; no restart was sent.')
