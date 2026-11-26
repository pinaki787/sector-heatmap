import unittest
from instrument_suggestions import ranked
class Suggestions(unittest.TestCase):
 def setUp(self):self.rows=[dict(symbol='NSE_EQ:9436',underlying='AXISCADES',description='Axiscades Engineering Technologies'),dict(symbol='NSE_EQ:1',underlying='AXISBANK',description='Axis Bank')]
 def test_typing_prefix_returns_exact_catalog_candidates(self):
  self.assertEqual({r['underlying'] for r in ranked(self.rows,'AXI')},{'AXISCADES','AXISBANK'})
 def test_missing_letter_suggests_original_exact_contract(self):
  rows=ranked(self.rows,'AXICADES');self.assertEqual(len(rows),1);self.assertEqual(rows[0]['symbol'],'NSE_EQ:9436');self.assertTrue(rows[0]['suggested'])
 def test_typo_does_not_override_an_exact_match_or_match_unrelated_names(self):
  self.assertEqual([r['underlying'] for r in ranked(self.rows,'AXISBANK')],['AXISBANK']);self.assertEqual(ranked(self.rows,'SOMETHING'),[]);self.assertNotIn('suggested',self.rows[0])
 def test_short_queries_never_fuzzy_match(self):self.assertEqual(ranked(self.rows,'AIX'),[])

class MasterCache(unittest.TestCase):
 def test_daily_master_objects_are_account_scoped(self):
  from native_indian import dhan_master
  self.assertIs(dhan_master('suggestion-test-one'),dhan_master('suggestion-test-one'))
  self.assertIsNot(dhan_master('suggestion-test-one'),dhan_master('suggestion-test-two'))
