import json,sqlite3,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from .workspace_disconnect import stop_for_disconnect

class DisconnectTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);(self.folder/'source').mkdir()
  self.runtime=SimpleNamespace(store=SimpleNamespace(folder=lambda a:self.folder),running=Mock(return_value=True),processes={})
  self.account=dict(id='a',broker='MOTILAL_OSWAL');self.positions=[];self.orders=[]
  self.db=sqlite3.connect(':memory:');self.db.execute('CREATE TABLE tickets(state TEXT)')
  self.service=Mock();self.service.book.side_effect=lambda operation:dict(data=self.positions if operation=='positions' else self.orders);self.service.tickets.db.return_value=self.db
 def tearDown(self):self.db.close();self.temp.cleanup()
 def call(self):
  with patch('sector_heatmap.workspace_disconnect.Service',return_value=self.service),patch('sector_heatmap.workspace_disconnect.stop_connection') as stop:
   try:stop_for_disconnect(self.runtime,self.account)
   finally:self.stop=stop
 def test_idle_connection_can_stop_and_disconnect_without_deleting_saved_login(self):
  for name in ['motilal-session.json','motilal-saved-login.enc','credentials.json']:(self.folder/name).write_text('fixture')
  self.call();self.stop.assert_called_once();self.assertTrue((self.folder/'disconnected.json').exists());self.assertFalse((self.folder/'motilal-session.json').exists());self.assertTrue((self.folder/'motilal-saved-login.enc').exists())
 def test_active_runner_blocks_before_process_shutdown(self):
  p=self.folder/'motilal-strategies/renko/test/state.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(dict(running=True,position=None,pending=None)))
  with self.assertRaises(ValueError):self.call()
  self.stop.assert_not_called()
 def test_broker_position_blocks_shutdown(self):
  self.positions=[dict(buyquantity=1,sellquantity=0)]
  with self.assertRaisesRegex(ValueError,'position'):self.call()
  self.stop.assert_not_called()
 def test_pending_or_unknown_order_blocks_shutdown(self):
  for state in ['CONFIRM','PARTIAL','UNKNOWN']:
   self.orders=[dict(orderstatus=state)]
   with self.assertRaises(ValueError):self.call()
   self.stop.assert_not_called()
 def test_ambiguous_quantities_fail_closed(self):
  for row in [{},dict(buyquantity='NaN',sellquantity=0),dict(buyquantity='x',sellquantity=0)]:
   self.positions=[row]
   with self.assertRaises(ValueError):self.call()
   self.stop.assert_not_called()
 def test_unresolved_ticket_blocks_shutdown(self):
  self.db.execute("INSERT INTO tickets VALUES ('UNCERTAIN')")
  with self.assertRaisesRegex(ValueError,'reviewed submission'):self.call()
  self.stop.assert_not_called()
 def test_broker_unavailable_does_not_change_connection(self):
  self.service.book.side_effect=ValueError('Unavailable')
  with self.assertRaises(ValueError):self.call()
  self.stop.assert_not_called();self.assertFalse((self.folder/'disconnected.json').exists())
 def test_shutdown_failure_does_not_claim_disconnected(self):
  with patch('sector_heatmap.workspace_disconnect.Service',return_value=self.service),patch('sector_heatmap.workspace_disconnect.stop_connection',side_effect=ValueError('Timeout')):
   with self.assertRaises(ValueError):stop_for_disconnect(self.runtime,self.account)
  self.assertFalse((self.folder/'disconnected.json').exists())
