import tempfile
from types import SimpleNamespace
from pathlib import Path
import unittest
from .delta_broker import Broker
from .delta_contracts import PRODUCT

class DeltaPaperStopTests(unittest.TestCase):
 def broker(self):
  def unavailable(*args):raise AssertionError("Paper Stop attempted a REST product/catalog lookup")
  delta=SimpleNamespace(clock=lambda:100,product=unavailable)
  return Broker(delta,Path(tempfile.gettempdir())/"unused-paper-stop-test")
 def position(self):
  return dict(symbol="C-BTC-81400-291026",product=PRODUCT,tick_size=.1,quantity_multiplier=.001,lot_size=1,product_id=160001,expiry_epoch=200,quote_currency="USD",settlement_currency="USD")
 def test_exact_saved_paper_contract_does_not_require_entry_catalog_or_network_identity(self):
  b=self.broker();p=self.position();c=dict(mode="PAPER",broker="DELTA_INDIA",execution_route="OPTIONS")
  self.assertEqual(b.validate_saved_paper_stop(c,p)["account_identity"],"PAPER-PUBLIC-DELTA-INDIA")
  self.assertEqual(b.contract(p["symbol"]),p);self.assertEqual(b.order(p["symbol"],1,-1,{})["symbol"],p["symbol"])
  b.connected=True;b.quotes[p["symbol"]]=dict(bid=10,ask=11,exchange_at=100,received_at=100)
  self.assertEqual(b.quote(p["symbol"])["bid"],10)
  b.quotes[p["symbol"]]["exchange_at"]=70
  with self.assertRaisesRegex(ValueError,"Fresh executable"):b.quote(p["symbol"])
 def test_live_and_incomplete_saved_contracts_cannot_use_recovery_cache(self):
  for mode in ("LIVE",None):
   with self.assertRaises(ValueError):self.broker().validate_saved_paper_stop(dict(mode=mode,broker="DELTA_INDIA"),self.position())
  p=self.position();p.pop("tick_size")
  with self.assertRaises(ValueError):self.broker().validate_saved_paper_stop(dict(mode="PAPER",broker="DELTA_INDIA"),p)
 def test_new_activation_clears_saved_stop_metadata_before_fresh_validation(self):
  b=self.broker();p=self.position();b.validate_saved_paper_stop(dict(mode="PAPER",broker="DELTA_INDIA"),p)
  with self.assertRaises(AssertionError):b.validate_config(dict(mode="LIVE",broker="DELTA_INDIA",underlying="BTCUSD"))
  self.assertEqual(b.paper_stop_contracts,{})
