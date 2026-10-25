import unittest
from sector_heatmap.handoff_broker_read import fyers_state
class State(unittest.TestCase):
 def state(self,positions=None,orders=None,holdings=None):
  return fyers_state(dict(s="ok",netPositions=positions or []),dict(s="ok",orderBook=orders or []),
   dict(s="ok",fund_limit=[dict(id=10,equityAmount=100000,commodityAmount=0)]),dict(s="ok",holdings=holdings or []))
 def test_flat_and_full_funds(self):
  r=self.state();self.assertEqual(r["used_capital"],0);self.assertEqual(r["daily_loss"],0);self.assertTrue(r["orders_verified"])
 def test_realized_and_unrealized_loss(self):
  r=self.state([dict(symbol="NSE:HDFCBANK-EQ",netQty=0,pl=-8000),dict(symbol="NSE:SBIN-EQ",netQty=2,netAvg=100,pl=-2000)])
  self.assertEqual(r["daily_loss"],10000);self.assertEqual(r["used_capital"],200)
 def test_holdings_exclude_and_use_capital(self):
  r=self.state(holdings=[dict(symbol="NSE:SBIN-EQ",quantity=3,costPrice=100)])
  self.assertEqual(r["exposed_underlyings"],["NSE:SBIN-EQ"]);self.assertEqual(r["used_capital"],300)
 def test_pending_order_reserves(self):
  r=self.state(orders=[dict(symbol="NSE:SBIN-EQ",status=6,remainingQuantity=10,limitPrice=100)])
  self.assertEqual(r["used_capital"],1000);self.assertIn("NSE:SBIN-EQ",r["exposed_underlyings"])
 def test_multiple_pending_orders_for_one_underlying_all_reserve_capital(self):
  orders=[dict(symbol="NSE:SBIN-EQ",status=6,remainingQuantity=10,limitPrice=100),
          dict(symbol="NSE:SBIN-EQ",status=6,remainingQuantity=5,limitPrice=101)]
  self.assertEqual(self.state(orders=orders)["used_capital"],1505)
 def test_commodity_multiplier_is_part_of_full_capital_exposure(self):
  position=dict(symbol="MCX:CRUDEOIL26NOVFUT",netQty=1,netAvg=6000,pl=0,qtyMulti_com=100)
  self.assertEqual(self.state(positions=[position])["used_capital"],600000)
 def test_unknown_commodity_multiplier_cannot_understate_exposure(self):
  with self.assertRaises(ValueError):self.state(positions=[dict(symbol="MCX:CRUDEOIL26NOVFUT",netQty=1,netAvg=6000,pl=0)])
 def test_unknown_status_blocks(self):
  with self.assertRaises(ValueError):self.state(orders=[dict(symbol="NSE:SBIN-EQ",status=999)])
 def test_unknown_daily_pnl_blocks(self):
  with self.assertRaises(ValueError):self.state([dict(symbol="NSE:SBIN-EQ",netQty=0)])

class DhanState(unittest.TestCase):
 def make(self,positions=None,orders=None,holdings=None,client="owned"):
  from sector_heatmap.handoff_broker_read import dhan_state
  return dhan_state("owned",positions or [],orders or [],dict(dhanClientId=client,availabelBalance=100000),
    holdings or [],lambda row,held:"NSE:TEST-EQ")
 def test_native_holdings_reserve_notional(self):
  r=self.make(holdings=[dict(totalQty=10,avgCostPrice=100)])
  self.assertEqual(r["used_capital"],1000);self.assertEqual(r["exposed_underlyings"],["NSE:TEST-EQ"])
 def test_foreign_funds_rejected(self):
  with self.assertRaises(PermissionError):self.make(client="other")
 def test_native_daily_loss_includes_realized_and_unrealized(self):
  r=self.make(positions=[dict(netQty=0,realizedProfit=-5000,unrealizedProfit=-5000)])
  self.assertEqual(r["daily_loss"],10000)
 def test_unknown_orders_fail_closed(self):
  with self.assertRaises(ValueError):self.make(orders=[dict(orderStatus="UNRECOGNIZED")])

class MotilalState(unittest.TestCase):
 def make(self,positions=None,orders=None,holdings=None,margin=None):
  from sector_heatmap.handoff_broker_read import motilal_state
  return motilal_state(positions or [],orders or [],holdings or [],
    margin or [dict(srno=k,amount=v) for k,v in ((102,100000),(103,80000),(600,-2000),(700,-8000))],
    lambda row,holding:dict(underlying="NSE:TEST-EQ",symbol="MO:NSE:123"))
 def test_nonadditive_native_funds_and_combined_daily_loss(self):
  r=self.make();self.assertEqual(r["available_funds"],80000);self.assertEqual(r["daily_loss"],10000)
 def test_native_full_position_amount(self):
  r=self.make(positions=[dict(buyquantity=100,sellquantity=0,buyamount=10000,bookedprofitloss=0,marktomarket=-10)])
  self.assertEqual(r["used_capital"],10000);self.assertIn("NSE:TEST-EQ",r["exposed_underlyings"])
 def test_unknown_order_and_missing_margins_block(self):
  with self.assertRaises(ValueError):self.make(orders=[dict(orderstatus="UNKNOWN")])
  with self.assertRaises(ValueError):self.make(margin=[dict(srno=102,amount=100000)])

class NativeReadErrors(unittest.TestCase):
 def test_expired_motilal_session_has_specific_safe_reconnect_message(self):
  from sector_heatmap.handoff_broker_read import public_read_error
  from sector_heatmap.motilal_api import MotilalError
  text=public_read_error(MotilalError("sensitive synthetic token must never appear",auth_required=True))
  self.assertIn("Motilal sign-in",text);self.assertIn("reconnect",text);self.assertNotIn("sensitive",text)
 def test_unknown_native_errors_never_echo_exception_payload(self):
  from sector_heatmap.handoff_broker_read import public_read_error
  self.assertEqual(public_read_error(RuntimeError("sensitive synthetic")),"Owned broker evidence unavailable.")
