import tempfile,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from sector_heatmap.account_parser import AccountParser
from sector_heatmap.recommendation_text import parse_text

class ParserTests(TestCase):
 def setUp(self):
  self.client=Mock(client_id='123');self.client.request.side_effect=lambda method,path,*args:{'dhanClientId':'123','dataPlan':'Active'} if path=='/profile' else {'status':'success','data':{'NSE_EQ':{'2885':{'last_price':1200}}}}
  row={'SEM_EXM_EXCH_ID':'NSE','SEM_SEGMENT':'E','SEM_SERIES':'EQ','SEM_TRADING_SYMBOL':'RELIANCE','SEM_SMST_SECURITY_ID':'2885','SEM_CUSTOM_SYMBOL':'Reliance','SEM_EXPIRY_DATE':'','SEM_OPTION_TYPE':'XX','SEM_STRIKE_PRICE':'0','SEM_LOT_UNITS':'1','SEM_TICK_SIZE':'5','SEM_INSTRUMENT_NAME':'EQUITY'}
  self.execution=Mock();self.execution._client.return_value=self.client;self.execution.master.load.return_value=[row]
  self.parser=AccountParser({'id':'own','broker':'DHAN'},self.execution)
  self.payload={'text':'BUY NSE RELIANCE AT 1200 SL 1190 TARGET 1220','symbol':'NSE_EQ:2885'}
 def test_text_is_broker_independent_and_exchange_does_not_become_underlying(self):
  self.assertEqual(parse_text(self.payload['text'])['underlying'],'RELIANCE')
 def test_native_mapping_quote_and_rule_analysis_use_owned_client(self):
  r=self.parser.parse(self.payload);self.assertEqual(r['mapping']['status'],'EXACT');self.assertEqual(r['account_id'],'own')
  q=self.parser.quote(self.payload);self.assertEqual(q['ltp'],1200);self.assertEqual(q['broker'],'DHAN')
  a=self.parser.analysis(self.payload);self.assertEqual(a['reward_to_risk'],2);self.assertTrue(a['advisory_only'])
  self.execution.submit.assert_not_called()
 def test_ambiguous_mapping_and_wrong_symbol_block_preparation(self):
  original=self.execution.master.load.return_value[0];self.execution.master.load.return_value=[original,{**original,'SEM_SMST_SECURITY_ID':'999'}]
  self.assertEqual(self.parser.parse(self.payload)['mapping']['status'],'AMBIGUOUS')
  with self.assertRaises(ValueError):self.parser.prepare(self.payload,'session')
  self.execution.prepare.assert_not_called()
 def test_profile_identity_and_missing_credentials_fail_closed(self):
  self.client.request.return_value={};self.client.request.side_effect=lambda *a:{'dhanClientId':'someone-else'}
  with self.assertRaises(PermissionError):self.parser.parse(self.payload)
  self.execution._client.side_effect=PermissionError('Authorize this saved account')
  with self.assertRaises(PermissionError):self.parser.parse(self.payload)
 def test_dhan_native_review_preserves_side_qty_stop_and_session_binding(self):
  self.execution.prepare.return_value={'preview_id':'DHAN-ONE','confirmation_phrase':'CONFIRM DHAN-ONE','submission_eligible':True}
  self.parser.prepare({**self.payload,'lots':2,'entry_mode':'LIMIT'},'session')
  args=self.execution.prepare.call_args.args[0];self.assertEqual(args['security_id'],'2885');self.assertEqual(args['quantity'],2);self.assertEqual(args['invalidation'],1190)
  with self.assertRaises(PermissionError):self.parser.submit({'preview_id':'DHAN-ONE','confirmation':'CONFIRM DHAN-ONE','live_confirmation':True},'different-session')
  self.execution.submit.assert_not_called()
 def test_trigger_and_protection_cannot_be_silently_ignored(self):
  for extra in ({'entry_mode':'STOP_LIMIT'},{'entry_mode':'LIMIT','protect_after_fill':True}):
   with self.assertRaises(ValueError):self.parser.prepare({**self.payload,**extra},'session')
  self.execution.prepare.assert_not_called()
 def test_delta_native_symbol_mapping_and_execution_capability_gate(self):
  delta=Mock();delta.catalog.return_value={'instruments':[{'symbol':'BTCUSD','underlying':'BTC','contract_type':'perpetual_futures','tick_size':.5}]};delta.ticker.return_value={'mark_price':70000}
  p=AccountParser({'id':'crypto','broker':'DELTA_INDIA'},delta)
  payload={'text':'BUY BTCUSD AT 70000 SL 69000 TARGET 72000','symbol':'BTCUSD'}
  self.assertEqual(p.parse(payload)['mapping']['contract']['symbol'],'BTCUSD')
  self.assertFalse(p.prepare(payload,'s')['submission_eligible']);delta.submit.assert_not_called()
 def test_motilal_master_mapping_stays_native(self):
  mo=Mock();mo.master.rows.side_effect=lambda exchange:[{'symbol':'MO:NSE:1','exchange':'NSE','underlying':'RELIANCE','name':'Reliance','option_type':'EQ','expiry':None,'suspended':False,'banned':False,'lot_size':1,'tick_size':.05}] if exchange=='NSE' else []
  p=AccountParser({'id':'mo','broker':'MOTILAL_OSWAL'},mo)
  self.assertEqual(p.parse(self.payload)['mapping']['contract']['symbol'],'MO:NSE:1')

class HandlerOwnershipTests(TestCase):
 def test_real_handler_checks_owner_and_payload_before_native_provider(self):
  import ast,json
  from unittest.mock import patch
  from sector_heatmap.workspaces import WorkspaceStore
  source=ast.parse(Path('sector_heatmap/web.py').read_text())
  method=next(n for n in ast.walk(source) if isinstance(n,ast.FunctionDef) and n.name=='private_parser')
  with tempfile.TemporaryDirectory() as tmp:
   store=WorkspaceStore(Path(tmp)/'registry.sqlite3');owner=store.create_user('owner','long-owner-password',bootstrap=True);other=store.create_user('other','long-other-password',actor=owner)
   account=store.create_account(owner,'DHAN','Algo','123');store.configure(owner,account['id'],{'DHAN_CLIENT_ID':'123','DHAN_ACCESS_TOKEN':'test-token'})
   auth=SimpleNamespace(store=store,authorize=Mock(return_value=other))
   namespace={'__name__':'sector_heatmap.web','__package__':'sector_heatmap','workspace_guard':None,'local_auth':auth,'json':json}
   exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),'private_parser','exec'),namespace)
   handler=SimpleNamespace(headers={},server=SimpleNamespace(),send_json=Mock(),dhan_service=Mock())
   path='/api/broker-parser/'+account['id']+'/parse'
   with patch('sector_heatmap.account_parser.AccountParser') as provider:
    with self.assertRaises(PermissionError):namespace['private_parser'](handler,path,{'text':'BUY RELIANCE AT 100 SL 90'})
    provider.assert_not_called()
    auth.authorize.return_value=owner
    with self.assertRaises(PermissionError):namespace['private_parser'](handler,path,{'account_id':'another','text':'BUY RELIANCE AT 100 SL 90'})
    provider.assert_not_called()
    namespace['private_parser'](handler,'/api/broker-parser/'+account['id']+'/whatsapp/status')
    data=handler.send_json.call_args.args[1]
    self.assertEqual(data['queue'],[]);self.assertFalse(data['source_ready']);provider.assert_not_called()
    provider.return_value.parse.return_value={'broker':'DHAN','account_id':account['id']}
    namespace['private_parser'](handler,path,{'account_id':account['id'],'broker':'DHAN','text':'BUY RELIANCE AT 100 SL 90'})
    handler.dhan_service.assert_called_once_with(account['id'])

class NativeConflictTests(TestCase):
 setUp=ParserTests.setUp
 def test_explicit_native_cash_id_cannot_override_conflicting_option_instruction(self):
  result=self.parser.parse({'text':'BUY NSE_EQ:2885 RELIANCE 1200 CE AT 10 SL 8 TARGET 15'})
  self.assertNotEqual(result['mapping']['status'],'EXACT')

class ModeTests(TestCase):
 setUp=ParserTests.setUp
 def test_dhan_paper_ticket_cannot_silently_become_live(self):
  with self.assertRaisesRegex(ValueError,'Paper'):self.parser.prepare({**self.payload,'mode':'PAPER'},'session')
  self.execution.prepare.assert_not_called()
 def test_motilal_cash_review_uses_native_owner_mode_and_typed_confirmation(self):
  mo=Mock();mo.master.rows.side_effect=lambda ex:[{'symbol':'MO:NSE:1','exchange':'NSE','underlying':'RELIANCE','name':'Reliance','option_type':'EQ','expiry':None,'suspended':False,'banned':False,'lot_size':1,'tick_size':.05}] if ex=='NSE' else []
  mo.tickets.preview.return_value={'ticket_id':'ticket','mode':'PAPER','confirmation':'PAPER ticket'}
  p=AccountParser({'id':'mo','broker':'MOTILAL_OSWAL','user_id':'owner'},mo)
  r=p.prepare({'text':self.payload['text'],'symbol':'MO:NSE:1','mode':'PAPER','lots':1,'max_notional':50000},'session')
  self.assertEqual(r['mode'],'PAPER');self.assertEqual(r['confirmation_phrase'],'PAPER ticket')
  self.assertEqual(mo.tickets.preview.call_args.args[0],'owner');mo.tickets.submit.assert_not_called()
  with self.assertRaises(PermissionError):p.submit({'preview_id':r['preview_id'],'confirmation':'PAPER ticket','live_confirmation':True},'other-session')
  mo.tickets.submit.assert_not_called()
