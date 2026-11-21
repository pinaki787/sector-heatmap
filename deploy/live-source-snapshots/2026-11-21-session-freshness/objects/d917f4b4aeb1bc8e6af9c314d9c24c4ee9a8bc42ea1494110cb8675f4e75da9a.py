import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from sector_heatmap.company_fundamentals import Provider,parse_filing
from sector_heatmap.fundamental_feedback import holdings,report
HTML='<table>'+''.join('<tr><td>'+a+'</td><td>'+b+'</td></tr>' for a,b in [('NSE Symbol','TEST'),('Description of presentation currency','INR'),('Level of rounding used in financial results','Lakhs'),('Nature of report standalone or consolidated','Consolidated'),('Date of end of reporting period','30-06-2026'),('Revenue from operations','10,000'),('Total profit (loss) for period','(1,000)'),('Finance costs','100'),('Basic earnings (loss) per share from continuing and discontinued operations','2')])+'</table>'
NOW=datetime(2026,10,25,tzinfo=timezone.utc).timestamp()
URL='https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_TEST.html'
META=dict(data=[dict(symbol='TEST',type='Integrated Filing- Financials',ixbrl=URL,qe_Date='30-JUN-2026',consolidated='Consolidated',cmName='Test Company',broadcast_Date='14-Aug-2026 10:00:00')])
class FundamentalsTests(unittest.TestCase):
 def test_exact_company_period_scale_and_negative_profit(self):
  v=parse_filing(HTML,'TEST','2026-06-30');self.assertEqual(v['metrics']['revenue_crore'],100);self.assertEqual(v['metrics']['profit_crore'],-10);self.assertEqual(v['metrics']['reported_profit_margin_pct'],-10);self.assertIsNone(v['metrics']['debt_equity'])
  with self.assertRaises(ValueError):parse_filing(HTML,'OTHER','2026-06-30')
  with self.assertRaises(ValueError):parse_filing(HTML,'TEST','2026-03-31')
 def test_bounded_primary_source_cache_and_missing_growth_valuation(self):
  with tempfile.TemporaryDirectory() as t,patch.dict('os.environ',{},clear=True):
   calls=[]
   def get(u):calls.append(u);return HTML if u==URL else json.dumps(META)
   p=Provider(t,clock=lambda:NOW,get=get);e=p.evidence('NSE:TEST-EQ');self.assertEqual(e['status'],'PARTIAL');self.assertEqual(len(calls),2);self.assertIn('Valuation/TTM P/E',e['missing']);p.evidence('NSE:TEST-EQ');self.assertEqual(len(calls),2);self.assertEqual(e['period_end'],'2026-06-30');self.assertEqual(e['sources'][0]['url'],URL)
 def test_noncompany_and_unmapped_market_never_fetch_or_guess(self):
  with tempfile.TemporaryDirectory() as t,patch.dict('os.environ',{},clear=True):
   p=Provider(t,get=lambda _:self.fail('No request for unmapped identity'));self.assertEqual(p.evidence('NSE:NIFTY50-INDEX')['status'],'NOT_APPLICABLE');self.assertEqual(p.evidence('BSE:TEST-EQ')['status'],'UNAVAILABLE');self.assertEqual(p.evidence('NSE:TEST26OCT100CE')['status'],'UNAVAILABLE')
 def test_failure_and_stale_data_cannot_claim_fundamental_support(self):
  e=dict(status='STALE',metrics={'profit_crore':10},reason='Old filing');self.assertEqual(report(e,{'relationship':'SUPPORTS'})['feedback']['relationship'],'INSUFFICIENT_EVIDENCE')
  self.assertEqual(report(dict(status='PARTIAL',metrics={'profit_crore':None}))['feedback']['relationship'],'INSUFFICIENT_EVIDENCE')
 def test_rule_holdings_does_not_fetch_fundamentals_or_call_ai(self):
  with patch('sector_heatmap.company_fundamentals.Provider',side_effect=AssertionError('Unexpected fundamental fetch')):
   v=holdings({'rows':[{'symbol':'NSE:TEST-EQ'}]},dict(ai_provider='RULES_ONLY'),'.');self.assertNotIn('fundamentals',v['rows'][0])
 def test_ai_holdings_keeps_action_and_excludes_private_portfolio_fields(self):
  e=dict(status='PARTIAL',metrics={'profit_crore':10},symbol='NSE:TEST-EQ',period_end='2026-06-30',missing=['Valuation'])
  captured=[]
  class AI:
   def review(self,v):
    captured.append(v);return dict(recommendations=[dict(symbol='NSE:TEST-EQ',decision='BULLISH',confidence='MODERATE',rationale='Public company evidence',risks=[],fundamental_feedback=dict(relationship='CONFLICTS',summary='Long-term profit conflicts with a technical exit.',financial_health='Profit reported; cash flow missing.',growth='Unavailable',valuation='Unavailable',key_risks=['Missing valuation']))])
  row=dict(symbol='NSE:TEST-EQ',kind='DELIVERY_EQUITY',action='EXIT',quantity=999,average_price=1234,gross_pnl=999999,evidence={'ema20':100,'private':'secret'})
  with patch('sector_heatmap.company_fundamentals.Provider') as p,patch('sector_heatmap.handoff_ai.HandoffAI.from_payload',return_value=AI()):
   p.return_value.evidence.return_value=e;v=holdings({'rows':[row]},dict(ai_provider='CODEX_CHATGPT'),'.')
  self.assertEqual(v['rows'][0]['action'],'EXIT');self.assertEqual(row['fundamentals']['feedback']['relationship'],'CONFLICTS');encoded=json.dumps(captured);self.assertNotIn('quantity',encoded);self.assertNotIn('average_price',encoded);self.assertNotIn('999999',encoded);self.assertNotIn('secret',encoded)
