import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from sector_heatmap.holdings_sectors import lookup
from sector_heatmap.section_permissions import allowed
class HoldingsSectorsTests(unittest.TestCase):
 def test_exact_identity_funds_unknown_and_no_portfolio_data_sent(self):
  rows=[dict(symbol='NSE:TECHM-EQ',kind='DELIVERY_EQUITY',quantity=123,average_price=456),dict(symbol='NSE:GOLDBEES-EQ',kind='DELIVERY_EQUITY'),dict(symbol='NSE:MISS-EQ',kind='DELIVERY_EQUITY'),dict(symbol='NSE:NIFTY-FUT',kind='OPEN_POSITION')]
  result={'data':[{'s':'NSE:TECHM','d':['TECHM','Technology services','stock','Tech']},{'s':'NSE:GOLDBEES','d':['GOLDBEES','Finance','fund','Gold']},{'s':'NSE:WRONG','d':['MISS','Finance','stock','Mismatch']}]}
  with tempfile.TemporaryDirectory() as folder,patch('sector_heatmap.holdings_sectors.download',return_value=json.dumps(result)) as download:
   out=lookup(Path(folder),rows)
   self.assertEqual(out['classifications']['NSE:TECHM-EQ']['sector'],'Technology services')
   self.assertEqual(out['classifications']['NSE:GOLDBEES-EQ']['sector'],'ETF / fund')
   self.assertEqual(out['classifications']['NSE:MISS-EQ']['sector'],'Unclassified')
   self.assertNotIn('quantity',json.dumps(download.call_args.args[2]))
   lookup(Path(folder),rows);self.assertEqual(download.call_count,1)
 def test_parent_and_new_assignment_both_required(self):
  path='/api/dhan/holdings-analysis/sectors/analyze'
  self.assertFalse(allowed({'features':['holdings']},path))
  self.assertFalse(allowed({'features':['holdings-allocation']},path))
  self.assertTrue(allowed({'features':['holdings','holdings-allocation']},path))
  self.assertTrue(allowed({'admin':True},path))
