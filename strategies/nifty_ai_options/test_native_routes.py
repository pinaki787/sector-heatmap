"""No-submit HTTP adapter and capability boundaries for selected native accounts."""
import io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from sector_heatmap.workspace_guard import WorkspaceGuard
from sector_heatmap.motilal_server import handler_factory

class NativeRoutesTests(unittest.TestCase):
 def test_guard_binds_every_ai_action_to_exact_broker_account(self):
  with tempfile.TemporaryDirectory() as root:
   store=SimpleNamespace(folder=lambda account:Path(root))
   guard=WorkspaceGuard(store,'a'*32,1,2)
   for broker in ('FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'):
    account=dict(id='a'*32,broker=broker)
    for action in ('prepare','start','stop','manual-entry','reconfigure','position-control'):
     path='/api/renko-supertrend/ai-options/'+action
     guard.validate_action(account,path,dict(account_id=account['id'],broker=broker))
     for bad in (dict(account_id='b'*32,broker=broker),dict(account_id=account['id'],broker='WRONG')):
      with self.assertRaises(PermissionError):guard.validate_action(account,path,bad)
 def setup_handler(self,path,payload=None):
  account=dict(id='a'*32,broker='MOTILAL_OSWAL');user=dict(admin=True,csrf='csrf')
  guard=Mock();guard.account_id=account['id'];guard.authorize.return_value=(user,account)
  guard.store.sidebar_visibility.return_value={'renko-supertrend':True}
  klass=handler_factory(guard,Mock());handler=klass.__new__(klass)
  handler.path=path;handler.headers={'X-CSRF-Token':'csrf'}
  handler.rfile=io.BytesIO()
  handler.send_json=Mock();handler.response=Mock()
  if payload is not None:
   raw=json.dumps(payload).encode();handler.rfile=io.BytesIO(raw);handler.headers.update({'Content-Length':str(len(raw)),'Content-Type':'application/json'})
  return handler,guard,account
 def test_motilal_reads_and_position_action_dispatch_only_to_selected_ai_service(self):
  for action in ('status','search','chart-source'):
   handler,guard,account=self.setup_handler('/api/renko-supertrend/ai-options/'+action+'?account_id='+'a'*32)
   ai=Mock();ai.snapshot.return_value={};ai.search.return_value=[];ai.chart_source.return_value={}
   with patch('strategies.nifty_ai_options.ui_bridge.Service',return_value=ai) as factory:
    handler.do_GET()
   self.assertEqual(handler.send_json.call_args.args[0],200);self.assertEqual(factory.call_args.args[0],account['id'])
  payload=dict(account_id='a'*32,broker='MOTILAL_OSWAL',operation='STOP')
  handler,guard,account=self.setup_handler('/api/renko-supertrend/ai-options/position-control',payload)
  ai=Mock();ai.position_action.return_value=dict(phase='QUEUED')
  with patch('strategies.nifty_ai_options.ui_bridge.Service',return_value=ai):handler.do_POST()
  ai.position_action.assert_called_once_with(payload);guard.validate_action.assert_called_once_with(account,'/api/renko-supertrend/ai-options/position-control',payload)
 def test_motilal_csrf_visibility_and_read_owner_reject_before_ai_dispatch(self):
  for kind in ('csrf','hidden','owner'):
   handler,guard,account=self.setup_handler('/api/renko-supertrend/ai-options/status?account_id='+'b'*32)
   if kind=='csrf':handler.headers['X-CSRF-Token']='wrong'
   if kind=='hidden':guard.store.sidebar_visibility.return_value={'renko-supertrend':False}
   with patch('strategies.nifty_ai_options.ui_bridge.Service') as factory:
    if kind=='csrf':
     with self.assertRaises(PermissionError):handler.identity(True)
    else:
     handler.do_GET();self.assertEqual(handler.send_json.call_args.args[0],403)
    factory.assert_not_called()

 def test_iso_expiry_metadata_keeps_native_value_and_selected_calendar_deadline(self):
  from ui_bridge import expiry_options
  from datetime import datetime
  from zoneinfo import ZoneInfo
  for broker in ('DHAN','MOTILAL_OSWAL'):
   adapter=Mock();adapter.option_rows.return_value=[dict(expiry='2026-12-16',strike=100,option_type=side) for side in ('CE','PE')]
   adapter.session.return_value=dict(closing_minutes=1435)
   with patch('native_indian.bound_native',return_value=adapter):
    result=expiry_options('a'*32,dict(broker=broker,underlying='MCX:EXACT',execution_route='OPTIONS'))
   row=result['expiries'][0];self.assertEqual(row['value'],'2026-12-16')
   stamp=datetime.fromtimestamp(row['expires_at'],ZoneInfo('Asia/Kolkata'));self.assertEqual((stamp.hour,stamp.minute),(23,55))

 def test_uncertified_future_calendar_does_not_hide_current_verified_native_expiries(self):
  from ui_bridge import expiry_options
  adapter=Mock();adapter.option_rows.return_value=[dict(expiry=e,strike=100,option_type=side) for e in ('2026-12-16','2027-01-20') for side in ('CE','PE')]
  def session(at):
   from datetime import datetime,timezone
   if datetime.fromtimestamp(at,timezone.utc).year!=2026:raise ValueError('Calendar update required')
   return dict(closing_minutes=1435)
  adapter.session.side_effect=session
  with patch('native_indian.bound_native',return_value=adapter):
   result=expiry_options('a'*32,dict(broker='DHAN',underlying='MCX:EXACT',execution_route='OPTIONS'))
  self.assertEqual([row['value'] for row in result['expiries']],['2026-12-16']);self.assertEqual(result['calendar_unavailable_dates'],['2027-01-20'])
