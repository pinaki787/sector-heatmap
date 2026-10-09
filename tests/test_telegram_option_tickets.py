import unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
from sector_heatmap.telegram_managed import OptionTickets
from strategies.renko_supertrend.test_delta_integration import config,NativeFake
from strategies.renko_supertrend.delta_runner import DeltaRunner
from tests.test_telegram_options import OptionPlanTests

class TicketTests(unittest.TestCase):
 def setUp(self):
  self.delta=Mock();route=OptionPlanTests().route();route['symbol']=route['product']['symbol'];self.delta.chart_option.return_value=route
  self.runner=Mock();self.runner.state={};self.runner.runtime_revision='fixture';self.runner.telegram_entry.return_value=dict(run_id='run',pending=None,position=dict(symbol='C-ETH-100',quantity=2))
  self.factory=Mock(return_value=self.runner)
  self.t=OptionTickets(self.delta,lambda text:dict(action='SELL' if 'SELL' in text else 'BUY',entry=100,entry_instruction='STOP_LIMIT',stop_loss=90,targets=[110]),self.factory,lambda:dict(config('ETHUSD'),ema_exit_enabled=True),clock=lambda:1000)
 def preview(self,text='ETHUSD BUY ABOVE 100',**kw):return self.t.preview(dict(text=text,**kw))
 def terms(self,t,**kw):return dict(ticket_id=t['ticket_id'],text=t['text'],quantity='2',mode='PAPER',entry_confirmed=True,timeframe='1 minute',ema_exit_enabled=True,ema_exit_length=10,supertrend_exit_enabled=True,**kw)
 def test_preview_has_no_size_or_orders_and_does_not_start_runner(self):
  t=self.preview();self.assertIsNone(t['quantity']);self.assertEqual(t['contract']['quantity_multiplier'],.01);self.factory.assert_not_called();self.delta.submit.assert_not_called()
 def test_paper_submit_routes_to_renko_once_and_preserves_underlying_reference(self):
  t=self.preview();p=self.terms(t);r=self.t.submit(p);self.t.submit(p)
  self.assertEqual(r['status'],'RENKO_CONFIRMED_POSITION');self.runner.telegram_entry.assert_called_once();c=self.runner.telegram_entry.call_args.args[0];self.assertEqual(c['mode'],'PAPER');self.assertEqual(c['execution_route'],'OPTIONS');self.assertEqual(c['lots'],2);self.assertIsNone(c['spot_stop']);self.assertEqual(c['expected_contract'],t['contract']['symbol']);self.delta.submit.assert_not_called()
 def test_live_pending_is_not_reported_as_fill(self):
  t=self.preview();self.runner.telegram_entry.return_value=dict(pending=dict(position=dict(symbol='C-ETH-100')),position=None)
  p=self.terms(t);p['mode']='LIVE';r=self.t.submit(p);self.assertEqual(r['status'],'RENKO_PENDING_RECONCILIATION')
 def test_size_confirmation_and_changed_contract_block_submission(self):
  t=self.preview();p=self.terms(t);p['quantity']=''
  with self.assertRaises(ValueError):self.t.submit(p)
  p=self.terms(t);p['entry_confirmed']=False
  with self.assertRaises(ValueError):self.t.submit(p)
  self.delta.chart_option.return_value['symbol']='different'
  with self.assertRaises(ValueError):self.t.submit(self.terms(t))
  self.runner.telegram_entry.assert_not_called()
 def test_gold_manual_preview_requires_visible_proxy_choice_not_original_quote(self):
  with self.assertRaises(ValueError):self.preview('XAUUSD BUY ABOVE 100')
  self.delta.chart_option.return_value['signal_symbol']='XAUTUSD'
  t=self.preview('XAUUSD BUY ABOVE 100',gold_proxy=True);self.assertTrue(t['gold_proxy']);self.assertEqual(t['plan']['underlying'],'XAUTUSD');self.assertIn('USER_CONFIRMS_NOW',t['trigger_policy'])
 def test_active_owner_and_expired_ticket_block(self):
  t=self.preview();self.runner.state={'position':{'symbol':'held'}}
  with self.assertRaises(ValueError):self.t.submit(self.terms(t))
  self.runner.state={};self.t.clock=lambda:1201
  with self.assertRaises(ValueError):self.t.submit(self.terms(t))

class RealRenkoTicketTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.b=NativeFake();self.r=DeltaRunner(self.b,Path(self.tmp.name)/'state.json',lambda:self.b.now);self.addCleanup(self.r.release)
 def payload(self,mode='PAPER'):
  return dict(config(),mode=mode,execution_route='OPTIONS',configuration_revision=self.r.runtime_revision,request_id='TGabcdefghijklmnopqrstuv',direction='BULLISH',ema_exit_enabled=True,expected_contract='C-BTC-90000-071026')
 def test_paper_owned_fill_no_native_order_no_reentry_restart_stopped(self):
  with patch('threading.Thread'):
   result=self.r.telegram_entry(self.payload())
  self.assertIsNotNone(result['position']);self.assertFalse(self.r.state['accepting_entries']);self.assertTrue(self.r.state['management_only']);self.assertEqual(self.b.sent,[])
  self.r.release();restored=DeltaRunner(NativeFake(),self.r.path,lambda:self.b.now);self.assertFalse(restored.state['running']);self.assertEqual(restored.state['position']['symbol'],'C-BTC-90000-071026')
 def test_live_order_acceptance_owns_pending_without_fabricated_position(self):
  with patch('threading.Thread'):
   result=self.r.telegram_entry(self.payload('LIVE'))
  self.assertEqual(len(self.b.sent),1);self.assertIsNotNone(result['pending']);self.assertIsNone(result['position']);self.assertFalse(self.r.state['accepting_entries'])
 def test_unattended_paper_trigger_checked_at_final_entry(self):
  p=self.payload();p['telegram_trigger']=dict(underlying='BTCUSD',direction='BULLISH',underlying_instruction='STOP_LIMIT',underlying_entry=999999);p['telegram_valid_until']=self.b.now+300
  with patch('threading.Thread'),self.assertRaises(ValueError):self.r.telegram_entry(p)
  self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[]);self.assertFalse(self.r.state['running'])
 def test_expected_contract_change_blocks_before_native_submit(self):
  p=self.payload('LIVE');p['expected_contract']='CHANGED'
  with patch('threading.Thread'),self.assertRaises(ValueError):self.r.telegram_entry(p)
  self.assertEqual(self.b.sent,[]);self.assertFalse(self.r.state['running'])

 def test_terminal_partial_fill_retains_only_confirmed_quantity_for_management(self):
  p=self.payload('LIVE');p['lots']=2
  with patch('threading.Thread'):self.r.telegram_entry(p)
  pending=self.r.state['pending'];self.b.qty=1
  self.b.book=[dict(pending['order'],id=pending['id'],status=1,filledQty=1,tradedPrice=10)]
  self.r.reconcile()
  self.assertIsNone(self.r.state['pending']);self.assertEqual(self.r.state['position']['quantity'],1);self.assertFalse(self.r.state['accepting_entries'])
 def test_rejected_unfilled_entry_does_not_create_position(self):
  with patch('threading.Thread'):self.r.telegram_entry(self.payload('LIVE'))
  pending=self.r.state['pending'];self.b.book=[dict(pending['order'],id=pending['id'],status=5,filledQty=0)]
  self.r.reconcile();self.r.step();self.assertIsNone(self.r.state['position']);self.assertFalse(self.r.state['running'])

 def test_delta_contract_quantity_is_not_indian_lot_cap(self):
  from strategies.renko_supertrend.delta_contracts import configuration
  p=self.payload();p['lots']=1000;self.assertEqual(configuration(p)['lots'],1000)
  p['lots']=True
  with self.assertRaises(ValueError):configuration(p)
