import unittest,math
from datetime import datetime
from zoneinfo import ZoneInfo
from sector_heatmap.premium_exit_mapping import premium_stop_from_greeks
from sector_heatmap.handoff import build_long_option_proposals
from tests.test_handoff import chain_leg
from tests.test_handoff_analysis import Provider,AnalysisTests
from sector_heatmap.handoff_analysis import opportunities

class PremiumStopTests(unittest.TestCase):
    def inputs(self,side='PE'):
        return dict(spot=100,stop=105 if side=='PE' else 95,premium=5,strike=100,expiry='2026-10-27',option_type=side,tick=.05,greeks=dict(delta=-.5 if side=='PE' else .5,gamma=.02,theta=-1,vega=.8,iv=30),now=datetime(2026,10,25,12,tzinfo=ZoneInfo('Asia/Kolkata')))
    def test_call_put_tick_aligned_positive_adverse_estimates(self):
        for side in ('CE','PE'):
            r=premium_stop_from_greeks(**self.inputs(side));self.assertEqual(r['status'],'ESTIMATED');self.assertTrue(0<r['stop_loss_price']<5);self.assertAlmostEqual(r['stop_loss_price']/.05,round(r['stop_loss_price']/.05));self.assertIn('Time and IV held unchanged',r['assumptions'])
    def test_iv_greeks_and_underlying_changes_affect_estimate(self):
        p=self.inputs();a=premium_stop_from_greeks(**p);p['greeks']['iv']=60;b=premium_stop_from_greeks(**p);self.assertNotEqual(a['stop_loss_price'],b['stop_loss_price']);p['stop']=110;c=premium_stop_from_greeks(**p);self.assertLess(c['stop_loss_price'],b['stop_loss_price'])
    def test_invalid_missing_greeks_expiry_direction_fail_closed(self):
        for change in ({'expiry':'2026-10-24'},{'stop':99},{'premium':float('inf')},{'greeks':{}},{'greeks':dict(delta=.5,gamma=.02,theta=-1,vega=.8,iv=30)}):
            p=self.inputs();p.update(change)
            with self.assertRaises(ValueError):premium_stop_from_greeks(**p)
    def test_distant_move_does_not_use_taylor_turnaround(self):
        p=self.inputs();p.update(spot=939,stop=981,premium=8.8,strike=940);p['greeks'].update(delta=-.37,gamma=.0122,iv=31.04)
        r=premium_stop_from_greeks(**p);self.assertTrue(0<r['stop_loss_price']<p['premium']);self.assertNotAlmostEqual(r['raw_stop_loss_price'],r['delta_gamma_local_estimate'])

class DiagnosticTests(unittest.TestCase):
    def options(self,**changes):
        leg=chain_leg('NSE:BLUESTARCO26OCT1500PE',1500,'PE',9.4,20.85,oi=86775,volume=241475);leg.update(changes)
        chain={'data':{'optionsChain':[dict(option_type='',ltp=1499),leg]}};expiry=dict(date='27-10-2026',expiry='1793095800');master={leg['symbol']:dict(lot_size=325,tick_size=.05,expiry_epoch=expiry['expiry'])}
        return chain,expiry,master
    def test_spread_only_failure_does_not_accuse_greeks(self):
        c,e,m=self.options();r=build_long_option_proposals(c,e,m,'BEARISH',{'invalidation':1548.23});self.assertIn('75.70%',r['reason']);self.assertIn('12.00%',r['reason']);self.assertNotIn('Greeks',r['reason']);self.assertEqual(len(r['rejected_contracts'][0]['validation_reasons']),1);self.assertEqual(r['rejected_contracts'][0]['greeks']['delta'],-.5)
    def test_missing_greeks_and_expiry_report_separately(self):
        c,e,m=self.options(bid=10,ask=10.5,greeks={'delta':-.5});m[next(iter(m))]['expiry_epoch']='wrong';r=build_long_option_proposals(c,e,m,'BEARISH',{'invalidation':1548.23});self.assertIn('Gamma',r['reason']);self.assertIn('expiry does not match',r['reason']);self.assertNotIn('spread',r['reason'])
    def test_rejected_contract_evidence_survives_saved_handoff_shape(self):
        c,e,m=self.options();options=build_long_option_proposals(c,e,m,'BEARISH',{'invalidation':1548.23});provider=Provider();provider.options=lambda *args:options;payload=AnalysisTests().payload();payload['instrument_route']='stock_options';r=opportunities(payload,provider,{});x=next(x for x in r['exclusions'] if x.get('rejected_contracts'));self.assertEqual(x['rejected_contracts'][0]['symbol'],'NSE:BLUESTARCO26OCT1500PE');self.assertEqual(x['liquidity_rules']['max_spread_pct'],12)
if __name__=='__main__':unittest.main()
