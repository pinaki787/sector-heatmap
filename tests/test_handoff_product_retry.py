import unittest
from copy import deepcopy
from sector_heatmap.handoff_product_retry import eligible
class ProductRetryTests(unittest.TestCase):
 def setUp(self):
  self.p=dict(order_policy={'product_type':'MARGIN'},instrument={'contracts':[dict(symbol='NSE:T100CE',quantity=50,action='BUY')]});self.r=dict(status='REJECTED',order_ids=['ONE']);self.row=dict(id='ONE',symbol='NSE:T100CE',qty=50,filledQty=0,remainingQuantity=0,status=5,side=1,productType='MARGIN',message='This instrument is allowed only for intraday trading.');self.book=dict(s='ok',orderBook=[self.row]);self.pos=dict(s='ok',netPositions=[])
 def test_exact_restriction_and_authoritative_zero_fill(self):self.assertTrue(eligible(self.p,self.r,self.book,self.pos))
 def test_no_retry_other_rejections_partial_pending_unknown_or_timeout(self):
  for change in [dict(filledQty=1),dict(remainingQuantity=50),dict(status=6),dict(message='Insufficient funds'),dict(message='Network timeout'),dict(message='Intraday not allowed'),dict(message='User says only intraday'),dict(symbol='NSE:OTHER'),dict(qty=100)]:
   row=dict(self.row,**change);self.assertFalse(eligible(self.p,self.r,dict(s='ok',orderBook=[row]),self.pos),change)
  self.assertFalse(eligible(self.p,dict(status='EXECUTION_STATUS_UNCERTAIN',order_ids=[]),self.book,self.pos))
 def test_positions_pending_orders_product_and_duplicate_identity_block(self):
  self.assertFalse(eligible(self.p,self.r,self.book,dict(s='ok',netPositions=[dict(symbol=self.row['symbol'],netQty=50)])))
  self.assertFalse(eligible(self.p,self.r,dict(s='ok',orderBook=[self.row,dict(self.row,id='TWO',status=6)]),self.pos))
  self.assertFalse(eligible(self.p,self.r,dict(s='ok',orderBook=[self.row,self.row]),self.pos))
  p=deepcopy(self.p);p['order_policy']['product_type']='INTRADAY';self.assertFalse(eligible(p,self.r,self.book,self.pos))
 def test_unknown_broker_wording_fails_closed(self):self.row['message']='Maybe this is intraday only; retry?';self.assertFalse(eligible(self.p,self.r,self.book,self.pos))
