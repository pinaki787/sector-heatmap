import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from copy import deepcopy
from sector_heatmap.handoff_levels import report_levels
class HorizonSchemaTests(unittest.TestCase):
    def card(self,side='PE'):
        return dict(candidate=dict(symbol='NSE:TEST-EQ',direction='BEARISH' if side=='PE' else 'BULLISH',data_quality='MARKET CLOSED'),analysis=dict(kind='LONG_OPTION',entry=100,recommended_invalidation={'price':105 if side=='PE' else 95},proposal=dict(kind='LONG_OPTION',entry_points=5,underlying_invalidation=105 if side=='PE' else 95,target_exit_points=10,expiry_iso='2026-10-27',premium_stop_estimate={'stop_loss_price':2},legs=[dict(validated=True,symbol='NSE:TEST26OCT100'+side,strike=100,option_type=side,lot_size=50,tick_size=.05)])))
    def test_bullish_and_bearish_exact_identity_and_separate_price_bases(self):
        for side in ('CE','PE'):
            card=self.card(side);before=deepcopy(card);r=report_levels(card,{'minimum_reward_to_risk':2},'intraday',broker='FYERS');self.assertEqual(card,before);self.assertEqual(r['contract']['option_type'],side);self.assertEqual(r['contract']['strike'],100);self.assertEqual(r['contract']['expiry'],'2026-10-27');self.assertEqual(r['source']['broker'],'FYERS');self.assertEqual(r['shared_current_plan']['underlying']['target'],90 if side=='PE' else 110);self.assertEqual(r['shared_current_plan']['premium']['stop_loss'],2);self.assertEqual(r['order_authority'],'NONE')
    def test_missing_timeframes_never_substitute_or_copy_levels(self):
        r=report_levels(self.card(),{'minimum_reward_to_risk':1},'intraday')
        for h in ('intraday','swing'):
            self.assertEqual(r['horizons'][h]['status'],'UNAVAILABLE');self.assertIsNone(r['horizons'][h]['underlying']['stop_loss']);self.assertIsNone(r['horizons'][h]['premium']['target'])
    def test_rejected_contract_is_not_selected(self):
        c=self.card();c['analysis']['proposal']['legs'][0]['validated']=False;r=report_levels(c,{},'intraday');self.assertEqual(r['status'],'UNAVAILABLE');self.assertNotIn('contract',r)
    def test_cash_untouched(self):self.assertIsNone(report_levels({'analysis':{'kind':'EQUITY'}},{},'intraday'))
    def detailed(self,side='PE'):
        c=self.card(side);bull=side=='CE';c['candidate']['timeframe_states']={
            '15m':dict(close=100,ema20=97 if bull else 103,atr=2,data_quality='MARKET CLOSED',last_updated='2026-10-23T15:15:00+05:30'),
            'daily':dict(close=100,ema20=90 if bull else 110,atr=12,data_quality='MARKET CLOSED',last_updated='2026-10-23T05:30:00+05:30')}
        c['analysis']['proposal']['legs'][0]['greeks']=dict(delta=.5 if bull else -.5,gamma=.02,theta=-1,vega=.8,iv=30)
        return c
    def render(self,c,rr=2):return report_levels(c,{'minimum_reward_to_risk':rr},'intraday',now=datetime(2026,10,25,12,tzinfo=ZoneInfo('Asia/Kolkata')),broker='FYERS')
    def test_distinct_completed_timeframes_and_directional_rr_for_calls_and_puts(self):
        for side in ('CE','PE'):
            c=self.detailed(side);before=deepcopy(c);r=self.render(c);self.assertEqual(c,before);i,w=r['horizons']['intraday'],r['horizons']['swing'];self.assertEqual(i['status'],'PROPOSED');self.assertEqual(w['status'],'PROPOSED');self.assertEqual(i['underlying']['stop_loss'],98 if side=='CE' else 102);self.assertEqual(w['underlying']['stop_loss'],90 if side=='CE' else 110);self.assertEqual(i['underlying']['target'],104 if side=='CE' else 96);self.assertEqual(w['underlying']['target'],120 if side=='CE' else 80)
            for h in (i,w):self.assertTrue(0<h['premium']['stop_loss']<h['premium']['entry']<h['premium']['target']);self.assertEqual(h['premium_estimates']['levels']['target']['expiry'],'2026-10-27')
    def test_missing_daily_evidence_does_not_borrow_intraday(self):
        c=self.detailed();c['candidate']['timeframe_states']['daily'].pop('atr');r=self.render(c);self.assertEqual(r['horizons']['intraday']['status'],'PROPOSED');self.assertEqual(r['horizons']['swing']['status'],'UNAVAILABLE');self.assertIn('no other horizon',r['horizons']['swing']['reason'])
    def test_stale_frame_and_missing_greeks_are_explicit(self):
        c=self.detailed();c['candidate']['timeframe_states']['15m']['data_quality']='STALE';c['analysis']['proposal']['legs'][0]['greeks']={};r=self.render(c);self.assertEqual(r['horizons']['intraday']['status'],'UNAVAILABLE');w=r['horizons']['swing'];self.assertEqual(w['status'],'PARTIAL');self.assertEqual(w['underlying']['stop_loss'],110);self.assertIsNone(w['premium']['target']);self.assertIn('Greeks',w['reason'])
    def test_no_rr_or_expiry_does_not_invent_targets_or_premiums(self):
        c=self.detailed();c['analysis']['proposal'].pop('expiry_iso');r=self.render(c,rr=None);i=r['horizons']['intraday'];self.assertIsNone(i['underlying']['target']);self.assertIsNone(i['premium']['target']);self.assertIn('reward-to-risk',i['reason']);self.assertIn('expiry',i['reason'])
    def test_wrong_option_side_withholds_report_contract(self):
        c=self.detailed();c['candidate']['direction']='BULLISH';r=self.render(c);self.assertEqual(r['status'],'UNAVAILABLE');self.assertNotIn('contract',r)
if __name__=='__main__':unittest.main()
