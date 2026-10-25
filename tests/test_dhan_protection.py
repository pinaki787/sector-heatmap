import copy,unittest
from sector_heatmap.dhan_protection import reconcile

class NativeProtection(unittest.TestCase):
 def setUp(self):
  self.ticket=dict(dhanClientId="owned",transactionType="BUY",exchangeSegment="NSE_EQ",productType="INTRADAY",securityId="1333",quantity=10,price=100)
  self.protection=dict(stop_loss_price=95,target_price=108)
  self.parent=dict(dhanClientId="owned",orderId="order",correlationId="preview",transactionType="BUY",
   exchangeSegment="NSE_EQ",productType="INTRADAY",securityId="1333",quantity=10,remainingQuantity=0,
   filledQty=10,averageTradedPrice=100,legName="ENTRY_LEG",orderStatus="TRADED",afterMarketOrder=False,
   legDetails=[dict(orderId="order",legName="STOP_LOSS_LEG",transactionType="SELL",remainingQuantity=0,price=95,orderStatus="PENDING"),
               dict(orderId="order",legName="TARGET_LEG",transactionType="SELL",remainingQuantity=0,price=108,orderStatus="PENDING")])
 def result(self,rows=None):
  return reconcile(self.ticket,self.protection,"order","preview",rows if rows is not None else [self.parent],.05)
 def test_exact_full_fill_and_both_server_held_exits(self):
  r=self.result();self.assertTrue(r["protection_confirmed"]);self.assertEqual(r["protected_quantity"],10)
 def test_wrong_owner_contract_product_or_correlation(self):
  for key in ("dhanClientId","correlationId","securityId","productType","exchangeSegment"):
   with self.subTest(key=key):
    p=copy.deepcopy(self.parent);p[key]="other"
    self.assertFalse(self.result([p])["protection_confirmed"])
 def test_pending_partial_and_terminal_entries_not_confirmed(self):
  for status,filled,left in (("PENDING",0,10),("PART_TRADED",5,5),("REJECTED",0,10),("CLOSED",10,0)):
   p=copy.deepcopy(self.parent);p.update(orderStatus=status,filledQty=filled,remainingQuantity=left)
   self.assertFalse(self.result([p])["protection_confirmed"])
 def test_missing_cancelled_wrong_side_or_price_exit_not_confirmed(self):
  for mutation in ("missing","cancelled","side","price","quantity"):
   p=copy.deepcopy(self.parent)
   if mutation=="missing":p["legDetails"].pop()
   elif mutation=="cancelled":p["legDetails"][0]["orderStatus"]="CANCELLED"
   elif mutation=="side":p["legDetails"][0]["transactionType"]="BUY"
   elif mutation=="price":p["legDetails"][0]["price"]=94
   else:p["legDetails"][0]["remainingQuantity"]=5
   self.assertFalse(self.result([p])["protection_confirmed"])
 def test_duplicate_parent_and_invalid_fill_price(self):
  self.assertFalse(self.result([self.parent,self.parent])["protection_confirmed"])
  self.parent["averageTradedPrice"]=0
  self.assertFalse(self.result()["protection_confirmed"])
 def test_reconciliation_never_mutates_broker_evidence(self):
  before=copy.deepcopy(self.parent);self.result();self.assertEqual(self.parent,before)
