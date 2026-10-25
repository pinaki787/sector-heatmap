import unittest
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
from sector_heatmap.handoff_outcomes import outcomes
from sector_heatmap.handoff_levels import report_levels
from tests.test_handoff_horizon_levels import HorizonSchemaTests
NOW=datetime(2026,10,25,12,tzinfo=ZoneInfo('Asia/Kolkata'))
class OutcomeTests(unittest.TestCase):
    def contract(self,side='CE'):return dict(symbol='NSE:TEST26OCT100'+side,strike=100,option_type=side,expiry='2026-10-27',lot_size=50,validated=True)
    def horizon(self):return dict(status='PROPOSED',source={'data_quality':'MARKET CLOSED'},underlying={'entry':9999,'target':1,'stop_loss':999999},premium={'entry':100,'target':110,'stop_loss':90})
    def test_bought_call_and_put_use_premium_pnl_not_underlying_direction(self):
        for side in ('CE','PE'):
            r=outcomes(self.horizon(),self.contract(side),1,'FYERS',NOW);self.assertEqual(r['target']['gross_pnl'],500);self.assertEqual(r['stop']['gross_pnl'],-500);self.assertEqual(r['stop']['gross_loss'],500);self.assertEqual(r['position_side'],'BUY_OPTION');self.assertEqual(r['currency'],'INR')
    def test_known_fees_net_profit_and_loss_include_both_legs(self):
        r=outcomes(self.horizon(),self.contract(),1,'FYERS',NOW);t=r['target'];self.assertEqual(t['estimated_costs']['entry']['total'],26.24);self.assertEqual(t['estimated_costs']['exit']['total'],34.5);self.assertEqual(t['estimated_costs']['total'],60.74);self.assertEqual(t['net_pnl'],439.26);stop=r['stop'];self.assertEqual(stop['estimated_loss'],500+stop['estimated_costs']['total']);self.assertEqual(stop['net_pnl'],-stop['estimated_loss'])
    def test_lot_scaling_preserves_two_order_fee_assumption(self):
        one=outcomes(self.horizon(),self.contract(),1,'FYERS',NOW);three=outcomes(self.horizon(),self.contract(),3,'FYERS',NOW);self.assertEqual(three['sizing']['quantity'],150);self.assertEqual(three['target']['gross_pnl'],1500);self.assertEqual(three['stop']['gross_loss'],1500);self.assertEqual(three['target']['estimated_costs']['entry']['brokerage'],20);self.assertLess(three['target']['estimated_costs']['total'],3*one['target']['estimated_costs']['total'])
    def test_unknown_costs_withhold_net_and_are_not_zero(self):
        r=outcomes(self.horizon(),self.contract(),1,'MOTILAL_OSWAL',NOW);self.assertEqual(r['status'],'PARTIAL');self.assertEqual(r['target']['gross_pnl'],500);self.assertIsNone(r['target']['estimated_costs']['total']);self.assertIsNone(r['target']['net_pnl']);self.assertIsNone(r['stop']['estimated_loss'])
    def test_missing_invalid_sizing_or_rejected_contract_withholds(self):
        for change,lots in [({'lot_size':None},1),({'lot_size':65.5},1),({'validated':False},1),({},0),({},None),({},True),({},1.5),({},1e308),({'expiry':None},1)]:
            c=self.contract();c.update(change);r=outcomes(self.horizon(),c,lots,'FYERS',NOW);self.assertEqual(r['status'],'UNAVAILABLE');self.assertIsNone(r['target'])
    def test_stale_or_missing_premium_never_uses_underlying_points(self):
        h=self.horizon();h['source']['data_quality']='STALE';self.assertEqual(outcomes(h,self.contract(),1,'FYERS',NOW)['status'],'UNAVAILABLE');h=self.horizon();h['premium']['target']=None;r=outcomes(h,self.contract(),1,'FYERS',NOW);self.assertIsNone(r['target']);self.assertEqual(r['stop']['gross_loss'],500)
    def test_selected_report_lots_do_not_mutate_original_sizing_or_level_policy(self):
        fixture=HorizonSchemaTests();card=fixture.detailed('PE');card['analysis']['proposal']['sizing']={'lots':1,'quantity':50};original=deepcopy(card);r=report_levels(card,{'minimum_reward_to_risk':2},'intraday',now=NOW,broker='FYERS',selected_lots=3,lots_supplied=True);self.assertEqual(card,original)
        for h in ('intraday','swing'):self.assertEqual(r['horizons'][h]['outcomes']['sizing']['lots'],3);self.assertEqual(r['horizons'][h]['outcomes']['sizing']['quantity'],150)
        self.assertNotEqual(r['horizons']['intraday']['outcomes']['target']['gross_pnl'],r['horizons']['swing']['outcomes']['target']['gross_pnl'])
    def test_other_currency_market_withholds_inr_convention(self):
        c=self.contract();c['symbol']='OTHER:TEST';r=outcomes(self.horizon(),c,1,'FYERS',NOW);self.assertEqual(r['status'],'UNAVAILABLE');self.assertIsNone(r['currency'])
if __name__=='__main__':unittest.main()
