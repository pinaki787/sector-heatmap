import ast,re,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from sector_heatmap.workspace_guard import WorkspaceGuard
from sector_heatmap.section_permissions import allowed
from sector_heatmap.recommendation_text import parse_text
class NativeRoutingTests(unittest.TestCase):
 def test_native_parser_routes_match_the_actual_owned_adapters(self):
  from sector_heatmap.multi_account_ticket import native_route
  aid='a'*32
  def account(broker,port):return dict(id=aid,broker=broker,port=port)
  self.assertEqual(native_route(account('DHAN',8100),'parser-parse',8080),(8100,'/api/dhan/manual-multi/parse'))
  self.assertEqual(native_route(account('DHAN',8100),'parser-prepare',8080),(8100,'/api/dhan/manual-multi/prepare'))
  self.assertEqual(native_route(account('FYERS',8102),'parser-prepare',8080),(8102,'/api/trade-recommendation/prepare-order'))
  self.assertEqual(native_route(account('MOTILAL_OSWAL',8103),'parser-submit',8080),(8080,'/api/broker-parser/'+aid+'/submit-order'))
  self.assertEqual(native_route(account('DELTA_INDIA',8101),'parser-parse',8080),(8080,'/api/broker-parser/'+aid+'/parse'))
  with self.assertRaises(ValueError):native_route(account('DELTA_INDIA',8101),'parser-submit',8080)
 def test_isolated_dhan_native_route_keeps_exact_binding(self):
  with tempfile.TemporaryDirectory() as tmp:
   guard=object.__new__(WorkspaceGuard);guard.store=SimpleNamespace(folder=lambda account:Path(tmp));aid='a'*32
   account=dict(id=aid,broker='DHAN');payload=dict(account_id=aid,broker='DHAN')
   guard.validate_action(account,'/api/dhan/manual-multi/prepare',payload)
   with self.assertRaises(PermissionError):guard.validate_action(account,'/api/dhan/manual-multi/prepare',dict(payload,account_id='b'*32))
   with self.assertRaises(PermissionError):guard.validate_action(account,'/api/dhan/manual-multi/prepare',dict(payload,broker='FYERS'))
 def test_native_permission_is_narrow_and_retains_existing_assignments(self):
  user={'admin':False,'features':['trade-parser']}
  self.assertTrue(allowed(user,'/api/dhan/manual-multi/prepare'))
  self.assertFalse(allowed(user,'/api/dhan/prepare'))
  self.assertFalse(allowed({'admin':False,'features':['investment']},'/api/dhan/manual-multi/prepare'))
class CashParserMappingTests(unittest.TestCase):
 def test_every_snapshot_disambiguates_explicit_exchange_and_cash(self):
  candidates=[dict(symbol='NSE:INFY-EQ',segment='NSE_CM',lot_size=1,tick_size=.05),dict(symbol='BSE:INFY-A',segment='BSE_CM',lot_size=1,tick_size=.05),dict(symbol='NSE:INFY26NOVFUT',segment='NSE_FO',lot_size=400,tick_size=.05)]
  for source in [Path('.'),*Path('.private/dashboard-login/accounts').glob('*/source')]:
   tree=ast.parse((source/'sector_heatmap/web.py').read_text());fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='trade_recommendation_preview')
   scope={'re':re,'parse_trade_recommendation':parse_text,'trade_recommendation_contracts':lambda parsed:candidates}
   exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(source),'exec'),scope)
   result=scope[fn.name]({'text':'BUY NSE INFY AT 1000 SL 900 TARGET 1100','amount_review':True})
   self.assertEqual(result['parsed']['underlying'],'INFY');self.assertEqual(result['mapping']['contract']['symbol'],'NSE:INFY-EQ')
   with self.assertRaisesRegex(ValueError,'Futures'):scope[fn.name]({'text':'BUY NSE INFY FUT AT 1000 SL 900 TARGET 1100','amount_review':True})
