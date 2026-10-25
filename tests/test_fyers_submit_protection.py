from datetime import datetime
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from sector_heatmap.fyers_execution import DailyRiskLedger,FyersExecutionService
from test_fyers_execution import FakeClient,FakeMaster

class SubmittedProtection(unittest.TestCase):
 @patch("sector_heatmap.fyers_execution.load_config",return_value={"FYERS_ACCESS_TOKEN":"APP:synthetic"})
 def test_exact_linked_exits_sent_and_confirmed_fill_reconciled(self,_):
  with tempfile.TemporaryDirectory() as t:
   client=FakeClient();sent=[]
   def place(order):
    sent.append(order)
    client.orders_data=[dict(id="owned-order",symbol=order["symbol"],qty=order["qty"],side=order["side"],productType=order["productType"],status=2,filledQty=order["qty"],remainingQuantity=0,tradedPrice=order["limitPrice"],limitPrice=order["limitPrice"],stopLoss=order["stopLoss"],takeProfit=order["takeProfit"],legType=order["legType"])]
    return dict(s="ok",id="owned-order")
   client.place_order=place
   service=FyersExecutionService(client_factory=lambda *_:client,master=FakeMaster(),cm_master=FakeMaster(),
    ledger=DailyRiskLedger(Path(t)/"ledger.json"),now=lambda:datetime(2026,8,30,10).astimezone(),live_gate=lambda:True)
   preview=service.prepare(dict(broker="fyers",underlying="NSE:TEST-EQ",invalidation=95,quantity=10,
    proposal=dict(kind="EQUITY",label="Equity long",direction="BULLISH",quantity=10,target=108)))
   result=service.submit(preview["preview_id"],preview["confirmation_phrase"])
   self.assertEqual(len(sent),1);self.assertEqual(sent[0]["stopLoss"],5);self.assertEqual(sent[0]["takeProfit"],8)
   self.assertFalse(sent[0]["offlineOrder"]);self.assertEqual(sent[0]["legType"],1)
   self.assertTrue(result["protection_confirmed"]);self.assertEqual(result["protected_quantity"],10)
   with self.assertRaises(ValueError):service.submit(preview["preview_id"],preview["confirmation_phrase"])
   self.assertEqual(len(sent),1)
