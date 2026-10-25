import copy,unittest
from sector_heatmap.fyers_protection import reconcile
def data():
 p={"instrument":{"kind":"EQUITY","contracts":[{"symbol":"NSE:A-EQ","action":"BUY","quantity":10,"tick_size":.05}]},"order_policy":{"product_type":"INTRADAY"},"protection":{"stop_loss_price":95,"target_price":110}}
 row={"id":"owned","symbol":"NSE:A-EQ","side":1,"qty":10,"productType":"INTRADAY","status":2,"filledQty":10,"remainingQuantity":0,"tradedPrice":100,"limitPrice":100,"stopLoss":95,"takeProfit":110}
 return p,{"s":"ok","orderBook":[row]}
class Protection(unittest.TestCase):
 def test_exact_filled(self):
  p,b=data();r=reconcile(p,["owned"],b);self.assertTrue(r["protection_confirmed"]);self.assertEqual(r["protected_quantity"],10)
 def test_full_fill_without_positive_average_is_not_confirmed(self):
  p,b=data();b["orderBook"][0]["tradedPrice"]=0
  self.assertFalse(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_pending_is_not_filled(self):
  p,b=data();b["orderBook"][0].update(status=6,filledQty=0,remainingQuantity=10);r=reconcile(p,["owned"],b);self.assertFalse(r["protection_confirmed"]);self.assertEqual(r["protection_state"],"REGISTERED_AWAITING_FILL")
 def test_partial_is_not_full(self):
  p,b=data();b["orderBook"][0].update(status=6,filledQty=3,remainingQuantity=7);self.assertFalse(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_missing_exit(self):
  p,b=data();b["orderBook"][0]["takeProfit"]=0;self.assertFalse(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_wrong_parent_cannot_match_by_symbol(self):
  p,b=data();self.assertFalse(reconcile(p,["other"],b)["protection_confirmed"])
 def test_wrong_quantity(self):
  p,b=data();b["orderBook"][0]["qty"]=20;self.assertFalse(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_wrong_product(self):
  p,b=data();b["orderBook"][0]["productType"]="CNC";self.assertFalse(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_wrong_exit(self):
  p,b=data();b["orderBook"][0]["stopLoss"]=94;self.assertEqual(reconcile(p,["owned"],b)["protection_state"],"LEVEL_MISMATCH")
 def test_explicit_offsets(self):
  p,b=data();b["orderBook"][0].update(legType=1,stopLoss=5,takeProfit=10);self.assertTrue(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_unlabelled_offsets_not_guessed(self):
  p,b=data();b["orderBook"][0].update(stopLoss=5,takeProfit=10);self.assertFalse(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_rejected(self):
  p,b=data();b["orderBook"][0]["status"]=5;self.assertFalse(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_duplicate_parent_ambiguous(self):
  p,b=data();b["orderBook"].append(copy.deepcopy(b["orderBook"][0]));self.assertFalse(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_read_failure(self):
  p,b=data();self.assertFalse(reconcile(p,["owned"],{"s":"error"})["protection_confirmed"])
 def test_bearish_cash(self):
  p,b=data();p["instrument"]["contracts"][0]["action"]="SELL";p["protection"].update(stop_loss_price=105,target_price=90);b["orderBook"][0].update(side=-1,stopLoss=105,takeProfit=90);self.assertTrue(reconcile(p,["owned"],b)["protection_confirmed"])
 def test_filled_put_is_bought_contract(self):
  p,b=data();p["instrument"]["kind"]="LONG_OPTION";self.assertTrue(reconcile(p,["owned"],b)["protection_confirmed"])
