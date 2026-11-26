"""Recover proven pre-submission rejections, never unknown broker acknowledgements."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import time
from sector_heatmap.workspaces import private_write

REVISION='delta-proven-no-send-v1'

def fingerprint(order):
    return {k:order[k] for k in ('symbol','qty','side','productType','orderTag')}

def receipt_path(delta,tag):
    if not isinstance(tag,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',tag):raise ValueError('Invalid local intent identity.')
    return Path(delta.live_path).parent/'delta-pre-submit-rejections'/(tag+'.json')

def record(delta,order,account_identity,*,basis='SAME_CALL_BEFORE_NATIVE_INTENT',evidence=None):
    if not account_identity:raise ValueError('Verified account identity required for no-send receipt.')
    if order['orderTag'] in delta.live['orders']:raise ValueError('Native intent exists; unknown acknowledgement cannot be cleared.')
    value=dict(revision=REVISION,account_identity=account_identity,order=fingerprint(order),basis=basis,at=time.time(),evidence=evidence)
    private_write(receipt_path(delta,order['orderTag']),json.dumps(value,allow_nan=False))
    return value

def verify(runner):
    p=runner.state.get('pending');c=runner.state.get('config') or {};adapter=runner.adapter
    if not p or c.get('mode')!='LIVE' or p.get('id') or runner.state.get('position') or not runner.is_entry_order(p['order'],p['position']):return None
    delta=adapter.delta
    if not hasattr(delta,'live_path'):return None
    path=receipt_path(delta,p['tag'])
    if not path.exists():return None
    receipt=json.loads(path.read_text())
    if (receipt.get('revision')!=REVISION or receipt.get('basis') not in ('SAME_CALL_BEFORE_NATIVE_INTENT','OPERATOR_RECONCILED_ORPHAN')
            or receipt.get('account_identity')!=runner.state.get('account_identity') or receipt.get('order')!=fingerprint(p['order'])):
        raise ValueError('No-send receipt does not match the retained account/order.')
    prove_absent(adapter,p,receipt['account_identity'])
    return deepcopy(receipt)

def prove_absent(adapter,p,expected_account):
    delta=adapter.delta
    adapter.authenticated_client()
    if adapter.execution.account_identity!=expected_account:raise ValueError('Broker account changed; no-send recovery blocked.')
    with delta.lock:
        if p['tag'] in delta.live['orders']:raise ValueError('Native intent appeared; retain broker reconciliation.')
        client='spdi_'+hashlib.sha256(p['tag'].encode()).hexdigest()[:26]
        active=adapter.execution.active_orders()
        if any(row.get('client_order_id')==client or row.get('product_id')==p['position']['product_id'] for row in active):
            raise ValueError('Active broker order conflicts with no-send recovery.')
        try:delta._private('GET','/v2/orders/client_order_id/'+client)
        except ValueError as error:
            if str(error)!='Delta India order_not_found (HTTP 400).':raise
        else:raise ValueError('Broker order exists; retain broker reconciliation.')
        if delta._position(p['position']['product_id'])!=0:raise ValueError('Broker exposure exists; no-send recovery blocked.')
        return dict(client_order_id=client,product_id=p['position']['product_id'],broker_order_not_found=True,broker_position=0,checked_at=time.time())

def recover(runner):
    receipt=verify(runner)
    if receipt is None:return False
    pending=runner.state['pending']
    runner.record_order(pending,'NOT_SUBMITTED',0,None)
    runner.state.setdefault('no_send_recoveries',[]).append(dict(tag=pending['tag'],run_id=runner.state.get('run_id'),at=runner.clock(),receipt=receipt))
    runner.state['pending']=None
    runner.state['accepting_entries']=False
    runner.event('LOCAL_INTENT_RECONCILED','Proven no-send entry reconciled against broker: no order or fill; no resubmission. New entries remain disabled.')
    if runner.state.get('squareoff_requested'):runner.stop()
    else:
        runner.state.update(running=False,status='RECOVERY_REQUIRED',message='Unsubmitted entry reconciled. Review and explicitly Start for fresh entries; no signal replay.')
        runner.save()
    return True
