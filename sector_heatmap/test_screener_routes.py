import unittest
from unittest.mock import Mock,patch
from . import screener_routes as routes

class RouteTests(unittest.TestCase):
    def row(self,ticker,expiry=9999999999,kind='CE'):
        row=['']*18;row[3]='65';row[8]=str(expiry);row[13]=ticker;row[16]=kind;return ','.join(row)
    def test_only_active_option_contracts_classify(self):
        text='\n'.join([self.row('ABC'),self.row('OLD',1),self.row('FUT',kind='XX')])
        self.assertEqual(routes.option_underlyings(text,now=100),{'ABC'})
    def test_equity_only_retains_label_and_disabled_options(self):
        master=Mock();master._content.return_value=self.row('OTHER')
        result=routes.analyze([dict(symbol='ABC')],None,master,Mock(),{})
        self.assertEqual(result['classifications'][0]['classification'],'Equity')
        self.assertFalse(result['classifications'][0]['routes']['LONG_OPTION']['eligible'])
    def test_unavailable_master_is_not_equity_only(self):
        master=Mock();master._content.side_effect=OSError()
        result=routes.analyze([dict(symbol='ABC')],None,master,Mock(),{})
        self.assertIsNone(result['classifications'][0]['options_available'])
    def test_both_option_choices_built_separately(self):
        master=Mock();master._content.return_value=self.row('ABC');master.lookup.return_value={}
        proposal=dict(structure='DEBIT',sizing=dict(status='SIZED',lots=1),reward_to_risk=2,max_loss_per_lot=100)
        built=dict(proposals=[proposal]);fetch=Mock(return_value=({'data':{'optionsChain':[]}},{}))
        with patch.object(routes,'build_long_option_proposals',return_value=built) as naked,patch.object(routes,'build_defined_risk_spreads',return_value=built) as spread,patch.object(routes,'evidence_conviction',return_value=dict(rating='High',score=8)):
            result=routes.analyze([dict(symbol='ABC',direction='BEARISH',stop=100)],None,master,fetch,{})
        self.assertEqual({p['route'] for p in result['plans']},{'LONG_OPTION','OPTION_SPREAD'})
        self.assertEqual(naked.call_args.args[3],'BEARISH');self.assertEqual(spread.call_args.args[3],'BEARISH')
        fetch.assert_called_once()
    def test_one_failed_route_does_not_remove_other(self):
        master=Mock();master._content.return_value=self.row('ABC')
        proposal=dict(structure='DEBIT',sizing=dict(status='SIZED',lots=1),reward_to_risk=2,max_loss_per_lot=100)
        with patch.object(routes,'build_long_option_proposals',side_effect=ValueError()),patch.object(routes,'build_defined_risk_spreads',return_value=dict(proposals=[proposal])),patch.object(routes,'evidence_conviction',return_value=dict(rating='High',score=8)):
            result=routes.analyze([dict(symbol='ABC',direction='BULLISH',stop=100)],None,master,Mock(return_value=({'data':{}},{})),{})
        self.assertEqual(len(result['plans']),1);self.assertEqual(result['plans'][0]['route'],'OPTION_SPREAD')

    def test_budget_is_weighted_and_conserved(self):
        shares=routes.budget_slices([dict(allocation_weight=7),dict(allocation_weight=5)],10000)
        self.assertGreater(shares[0],shares[1]);self.assertAlmostEqual(sum(shares),10000)
    def test_invalid_allocation_weight_blocks(self):
        for value in [-1,0,float('nan'),True]:
            with self.assertRaises(ValueError):routes.budget_slices([dict(allocation_weight=value)],10000)
