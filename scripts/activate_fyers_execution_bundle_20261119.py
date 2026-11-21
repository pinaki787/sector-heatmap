"""Apply the explicitly approved four-file FYERS bundle and guarded worker reload.
No runner/order methods are called. Native positions are retained.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
AID='bf46fc364b610a0dfd338419e133cb41'
CASE=ROOT/'.private/chart-order-rollouts/fyers-sensex-execution-alignment-20261119'
BASE=ROOT/'.private/dashboard-login/accounts'/AID
SOURCE=BASE/'source'
REGISTRY=ROOT/'.private/dashboard-login/registry.sqlite3'
from sector_heatmap import workspace_bounce
from sector_heatmap.service_restart import stopped_state_paths
from sector_heatmap.workspaces import WorkspaceStore,WorkspaceRuntime,private_write

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def critical_snapshot(paths):
    result={}
    fields=('config','run_id','started_at','position','positions','pending','order_history','trade_history','trades_used','realized_pnl','accepting_entries','running')
    for path in paths:
        state=json.loads(path.read_text())
        critical={k:state.get(k) for k in fields}
        result[str(path.relative_to(SOURCE))]=hashlib.sha256(json.dumps(critical,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return result

def main():
    if sys.argv[1:]!=['--approved-combined-fyers-reload']:
        raise ValueError('Exact explicit combined FYERS reload approval required.')
    manifest=json.loads((CASE/'fyers-activation-bundle.json').read_text())
    assert manifest['account']==AID and manifest['combined_checks']['passed'] and manifest['combined_checks']['tests']==86
    entries=manifest['entries']
    for row in entries:
        source=ROOT/row['source'];candidate=ROOT/row['candidate']
        assert source.is_relative_to(SOURCE) and sha(source)==row['base_sha256']
        assert sha(candidate)==row['candidate_sha256']
    previous=int(json.loads((BASE/'dashboard-owner.lock').read_text())['pid'])
    assert (Path('/proc')/str(previous)/'cwd').resolve()==SOURCE.resolve()
    paths=stopped_state_paths(SOURCE)
    # The production FYERS bounce policy gates all application-owned runtime.
    # Native unclaimed positions do not get closed or adopted by this reload.
    spec=importlib.util.spec_from_file_location('approved_reload_exposure',ROOT/'scripts/probe_chart_reload_exposure.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    exposure=probe.inspect(AID)
    assert exposure['broker']=='FYERS' and exposure['open_orders']==0
    if exposure['gate'] not in ('PASS','BLOCKED_EXPOSURE'):raise ValueError('Native exposure unverified')
    # Preserve the observed two unclaimed native positions; any change in exposure
    # coverage requires a new inspection, not a relaxed or bypassed runner guard.
    prior=json.loads((CASE/'combined-reload-exposure-details.json').read_text())
    if exposure['open_positions']!=len(prior['positions']):raise ValueError('Native position coverage changed; inspect before reload')
    with sqlite3.connect((BASE/'handoff-exits.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM trades').fetchone()[0]:
            raise ValueError('Handoff exit claims need review before reload')
    with sqlite3.connect((BASE/'handoff-entry-waits.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM waits').fetchone()[0]:
            raise ValueError('Handoff entry waits need review before reload')
    before=critical_snapshot(paths)
    audit=CASE/('approved-reload-'+str(time.time_ns()))
    audit.mkdir(mode=0o700)
    private_write(audit/'before-critical-hashes.json',json.dumps(before,indent=2))
    private_write(audit/'preflight.json',json.dumps({'previous_pid':previous,'state_paths':len(paths),'native_exposure':exposure,'ownership':'No application-owned active runtime, Handoff exit trades or entry waits; observed native positions retained','approval':'Approve combined FYERS worker reload','checked_at':time.time()},indent=2))
    for i,row in enumerate(entries):
        source=ROOT/row['source']
        private_write(audit/f'source-{i}.backup.py',source.read_text())
    stopped_state_paths(SOURCE)
    for row in entries:
        source=ROOT/row['source'];candidate=ROOT/row['candidate']
        assert sha(source)==row['base_sha256']
        private_write(source,candidate.read_text())
    manifest.update(status='OWNER_SOURCE_UPDATED_RELOAD_REQUESTED',approval_answer='Approve combined FYERS worker reload',audit=str(audit.relative_to(ROOT)))
    private_write(CASE/'fyers-activation-bundle.json',json.dumps(manifest,indent=2))
    store=WorkspaceStore(REGISTRY)
    with store.db() as db:
        actor=db.execute('SELECT id,username,admin FROM users WHERE username=?',('pinaki87',)).fetchone()
    if not actor or not actor['admin']:raise PermissionError('Registered administrator required')
    runtime=WorkspaceRuntime(store,ROOT,8080)
    state=workspace_bounce.begin(store,runtime,dict(actor),AID)
    print(json.dumps({'phase':state['status'],'previous_pid':previous,'broker':'FYERS','audit':str(audit.relative_to(ROOT))}),flush=True)
    deadline=time.monotonic()+85
    last=None
    while state['status'] in workspace_bounce._ACTIVE:
        if state['status']!=last:
            print(json.dumps({'phase':state['status'],'message':state['message']}),flush=True);last=state['status']
        if time.monotonic()>deadline:raise RuntimeError('Readiness did not settle; no second reload requested')
        time.sleep(1)
        state=workspace_bounce.status(store,dict(actor),AID)
    private_write(audit/'bounce-result.json',json.dumps(state,indent=2))
    if state['status']!='READY':raise RuntimeError('Guarded bounce failed: '+state.get('message',''))
    new=int(json.loads((BASE/'dashboard-owner.lock').read_text())['pid'])
    assert new!=previous and (Path('/proc')/str(new)/'cwd').resolve()==SOURCE.resolve()
    after=critical_snapshot(stopped_state_paths(SOURCE))
    private_write(audit/'after-critical-hashes.json',json.dumps(after,indent=2))
    assert before==after,'Saved runner config/ledger/lifecycle fields changed'
    for row in entries:assert sha(ROOT/row['source'])==row['candidate_sha256']
    result={'status':'READY','previous_pid':previous,'new_pid':new,'saved_critical_fields_preserved':True,'state_paths':len(after),'orders_submitted':0,'runners_started':0,'reloaded_scope':'FYERS dashboard worker only'}
    private_write(audit/'result.json',json.dumps(result,indent=2))
    manifest.update(status='FYERS_WORKER_READY_AWAITING_HOSTED_VERIFICATION',restart_performed=True,activation_result=result)
    private_write(CASE/'fyers-activation-bundle.json',json.dumps(manifest,indent=2))
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    main()
