import unittest,math,calendar
from datetime import datetime,timezone,date
from sector_heatmap.seasonality import calculate,symbol_options,period_key

def stamp(day):return datetime.fromisoformat(day+'T12:00:00+00:00').timestamp()
def candles(items):return [dict(date=d,close=p) for d,p in items]
class SeasonalityTests(unittest.TestCase):
 def test_compound_not_sum(self):
  data=calculate(candles([('2024-12-31',100),('2025-01-31',110),('2025-02-28',99)]),stamp('2025-03-10'))
  m=data['modes']['Monthly'];self.assertAlmostEqual(m['net_return'],-1);self.assertAlmostEqual(m['years'][0]['net_return'],-1)
  self.assertAlmostEqual(math.prod(1+p['value']/100 for p in m['years'][0]['periods'])-1,-.01)
 def test_missing_month_invalidates_net(self):
  m=calculate(candles([('2024-12-31',100),('2025-01-31',110),('2025-03-31',120)]),stamp('2025-04-10'))['modes']['Monthly']
  self.assertIsNone(m['net_return']);self.assertIsNone(m['years'][0]['net_return']);self.assertIsNone(m['years'][0]['periods'][1]['value'])
 def test_forming_month_not_included(self):
  m=calculate(candles([('2024-12-31',100),('2025-01-31',110),('2025-02-10',500)]),stamp('2025-02-11'))['modes']['Monthly']
  self.assertAlmostEqual(m['net_return'],10);self.assertEqual(m['to_date'],'2025-01-31')
 def test_partial_first_year_no_net(self):
  m=calculate(candles([('2025-03-31',100),('2025-04-30',110),('2025-05-30',120)]),stamp('2025-06-10'))['modes']['Monthly']
  self.assertIsNone(m['years'][0]['net_return']);self.assertAlmostEqual(m['net_return'],20);self.assertEqual(m['from_date'],'2025-03-31')
 def test_full_year_matches_direct_close(self):
  points=[('2024-12-31',100)]+[(f'2025-{m:02d}-{calendar.monthrange(2025,m)[1]}',100+m*5) for m in range(1,13)]
  report=calculate(candles(points),stamp('2026-01-10'));self.assertAlmostEqual(report['modes']['Monthly']['years'][0]['net_return'],60)
  self.assertAlmostEqual(report['modes']['Yearly']['years'][0]['net_return'],60)
 def test_iso_week_year(self):self.assertEqual(period_key(date(2024,12,30),'Weekly'),(2025,1))
 def test_invalid_prices(self):
  for value in (0,-1,float('nan'),float('inf')):
   with self.assertRaises(ValueError):calculate(candles([('2025-01-01',100),('2025-01-02',value)]),stamp('2025-02-01'))
 def test_duplicates_rejected(self):
  with self.assertRaises(ValueError):calculate(candles([('2025-01-01',100),('2025-01-01',101)]),stamp('2025-02-01'))
 def test_no_missing_zero(self):
  stats=calculate(candles([('2024-12-31',100),('2025-01-31',100)]),stamp('2025-03-10'))['modes']['Monthly']['statistics']
  self.assertEqual(stats[0]['samples'],1);self.assertEqual(stats[0]['average'],0);self.assertEqual(stats[1]['samples'],0);self.assertIsNone(stats[1]['average'])
 def test_symbol_identity(self):
  self.assertEqual(symbol_options({'symbol':'NSE:TECHM-EQ'}),('NSE:TECHM','TECHM.NS'))
  for symbol in ('TECHM','BTCUSD','NSE:TECHM-FUT','https://bad','NSE:ABC/DEF'):
   with self.assertRaises(ValueError):symbol_options({'symbol':symbol})
if __name__=='__main__':unittest.main()
