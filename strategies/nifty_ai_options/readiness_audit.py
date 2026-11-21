"""Read-only process ownership and durable runner inventory; no service actions."""
import os,json,sqlite3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path('/home/trading/sector-heatmap')
processes=[]
keys=['SECTOR_PULSE_WORKSPACE_ID','SECTOR_PULSE_WORKSPACE_BROKER','SECTOR_PULSE_WORKSPACE_ROOT','SECTOR_PULSE_WORKSPACE_SOURCE','SECTOR_PULSE_WORKSPACE_REGISTRY','PORT','HEATMAP_PORT']
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        cmd=(proc/'cmdline').read_bytes().split(b'\0')
        joined=b' '.join(cmd)
        if not any(x in joined for x in (b'heatmap_server.py',b'sector_heatmap.workspace_supervisor',b'sector_heatmap.motilal_server')):continue
        if not cmd[0] or b'python' not in cmd[0]:continue
        env=dict(v.split(b'=',1) for v in (proc/'environ').read_bytes().split(b'\0') if b'=' in v)
        processes.append(dict(pid=int(proc.name),cwd=str((proc/'cwd').resolve()),owner={k:env[k.encode()].decode() for k in keys if k.encode() in env},
                              cgroup=(proc/'cgroup').read_text().strip(),executable=cmd[0].decode()))
    except (PermissionError,FileNotFoundError,ProcessLookupError):pass
with sqlite3.connect((ROOT/'.private/dashboard-login/registry.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    accounts=db.execute('select id,broker from accounts').fetchall()
roots=[ROOT]+[ROOT/'.private/dashboard-login/accounts'/aid/'source' for aid,broker in accounts]
states=[]
for base in roots:
    directory=base/'.private'
    if not directory.exists():continue
    for path,dirs,files in os.walk(directory):
        depth=len(Path(path).relative_to(directory).parts)
        dirs[:]=[d for d in dirs if d not in ('accounts','data','raw','chart-history','chart-order-rollouts','history','backtesting','node_modules') and depth<4]
        for name in files:
            if name not in ('state.json','runner.json') and not name.endswith('-state.json'):continue
            file=Path(path)/name
            try:
                if file.stat().st_size>20_000_000:continue
                state=json.loads(file.read_text())
                if not isinstance(state,dict) or not any(k in state for k in ('running','position','pending')):continue
                config=state.get('config') or {}
                def pos(value):
                    if not isinstance(value,dict):return bool(value)
                    return {k:value.get(k) for k in ('symbol','quantity','qty','direction','status') if k in value}
                states.append(dict(file=str(file),running=state.get('running'),mode=config.get('mode',state.get('mode')),
                    symbol=config.get('underlying',state.get('instrument')),position=pos(state.get('position')),pending=pos(state.get('pending')),
                    recovery={k:state.get(k) for k in ('interrupted','recovering','stop_requested','status') if k in state},
                    modified_at=datetime.fromtimestamp(file.stat().st_mtime,ZoneInfo('Asia/Kolkata')).isoformat()))
            except (ValueError,OSError):pass
report=dict(checked_at=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),processes=processes,accounts=[dict(id=a,broker=b) for a,b in accounts],runner_states=states,
            active_or_exposed=[s for s in states if s['running'] or s['position'] or s['pending']],actions_taken=[])
out=ROOT/'strategies/nifty_ai_options/evidence/readiness-audit.json';out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
