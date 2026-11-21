"""Use owning restart guard's CURRENT states, exclude backups; never reload."""
import sys,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from sector_heatmap.service_restart import runtime_states,stopped_state_paths
from sector_heatmap.restart_state_read import read_runtime_state
previous=json.loads((Path(__file__).parent/'evidence/readiness-audit.json').read_text())
results=[]
with sqlite3.connect((ROOT/'.private/dashboard-login/registry.sqlite3').as_uri()+'?mode=ro',uri=True) as db:accounts=db.execute('select id,broker from accounts').fetchall()
for owner,broker,source in [('shared','SHARED',ROOT)]+[(aid,broker,ROOT/'.private/dashboard-login/accounts'/aid/'source') for aid,broker in accounts]:
    states=[]
    for path in runtime_states(source):
        s=read_runtime_state(path,source);c=s.get('config') or {}
        states.append(dict(file=str(path),mode=c.get('mode',s.get('mode')),symbol=c.get('underlying',s.get('symbol')),status=s.get('status'),
            running=bool(s.get('running')),entries=bool(s.get('accepting_entries')),position=bool(s.get('position') or s.get('positions') or s.get('runner_position')),
            pending=bool(s.get('pending') or s.get('runner_pending')),active=bool(s.get('active') or s.get('loop_running'))))
    try:stopped_state_paths(source);guard='PASS'
    except Exception as error:guard=str(error)
    bounce=source.parent/'bounce-status.json'
    results.append(dict(owner=owner,broker=broker,source=str(source),restart_guard=guard,states=states,
        bounce=json.loads(bounce.read_text()).get('status') if bounce.exists() else None))
report=dict(processes=previous['processes'],current_owners=results,actions_taken=[])
(Path(__file__).parent/'evidence/readiness-current.json').write_text(json.dumps(report,indent=2))
for r in results:
    print(json.dumps(dict(owner=r['owner'],broker=r['broker'],guard=r['restart_guard'],bounce=r['bounce'],states=len(r['states']),
        attention=[s for s in r['states'] if s['running'] or s['entries'] or s['position'] or s['pending'] or s['active']])))
