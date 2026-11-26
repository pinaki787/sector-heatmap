import unittest
from execution import available_funds

class SharedFundsTests(unittest.TestCase):
 def test_shared_cash_available_for_commodity(self):
  rows=[dict(id=10,equityAmount=109075.67,commodityAmount=0),dict(id=3,equityAmount=109075.67)]
  self.assertEqual(available_funds(rows,commodity=True),109075.67)
 def test_no_collateral_or_double_counting(self):
  rows=[dict(id=10,equityAmount=1000,commodityAmount=200),dict(id=3,equityAmount=300)]
  self.assertEqual(available_funds(rows,commodity=True),300)
  self.assertEqual(available_funds(rows),1000)
 def test_unavailable_not_invented(self):
  self.assertIsNone(available_funds([],commodity=True))
  self.assertEqual(available_funds([dict(id=10,equityAmount=1000,commodityAmount=0)],commodity=True),0)
