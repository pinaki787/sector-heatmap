from unittest.mock import patch
from tests.test_parser_order_preparation import ParserOrderPreparationTests
class AmountParserPreflightTests(ParserOrderPreparationTests):
    def setUp(self):
        super().setUp()
        self.prepare.__globals__['available_funds']=lambda value:15000
        self.client.positions.return_value={'s':'ok','netPositions':[]}
        self.client.orderbook.return_value={'s':'ok','orderBook':[]}
    def test_amount_budget_and_funds_are_hard_gates(self):
        with patch('sector_heatmap.fyers_execution._fresh_depth_quote',return_value={'bid':529,'ask':530}):
            with self.assertRaisesRegex(ValueError,'amount/funds'):
                self.prepare({'lots':1,'entry_mode':'LIMIT','limit_price':530,'amount_review':True,'manual_amount_budget':10000})
            ticket=self.prepare({'lots':1,'entry_mode':'LIMIT','limit_price':530,'amount_review':True,'manual_amount_budget':12000})
        self.assertEqual(ticket['margin_required'],10706)
        stored=self.prepare.__globals__['parser_order_previews'][ticket['preview_id']]['payload']
        self.assertTrue(stored['amount_review']);self.assertEqual(stored['manual_amount_budget'],12000)
        self.client.place_order.assert_not_called()
    def test_existing_position_blocks_duplicate(self):
        self.client.positions.return_value={'s':'ok','netPositions':[{'symbol':'BSE:SENSEX26O0872300PE','netQty':20}]}
        with patch('sector_heatmap.fyers_execution._fresh_depth_quote',return_value={'bid':529,'ask':530}):
            with self.assertRaisesRegex(ValueError,'duplicate'):
                self.prepare({'lots':1,'entry_mode':'LIMIT','limit_price':530,'amount_review':True,'manual_amount_budget':12000})
        self.client.place_order.assert_not_called()
