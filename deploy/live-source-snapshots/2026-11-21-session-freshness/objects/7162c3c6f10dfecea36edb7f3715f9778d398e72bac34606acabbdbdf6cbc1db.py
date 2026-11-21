from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from sector_heatmap.handoff import build_long_option_proposals
from sector_heatmap.fyers_execution import FyersExecutionService, DailyRiskLedger
from tests.test_fyers_execution import FakeClient, FakeMaster


class OrderClient(FakeClient):
    def __init__(self):
        super().__init__();self.sent=[]
    def place_order(self, order):
        self.sent.append(dict(order))
        self.orders_data.append(dict(order,id=str(len(self.sent)),status=2,filledQty=order['qty']))
        return dict(s='ok',id=str(len(self.sent)))
    def place_basket_orders(self, orders):
        raise AssertionError('A single bought option must not submit a spread basket')


class LongOptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.client=OrderClient()
        token=patch('sector_heatmap.fyers_execution.load_config',return_value={'FYERS_ACCESS_TOKEN':'TEST:fake'})
        token.start();self.addCleanup(token.stop)
        self.service=FyersExecutionService(client_factory=lambda *_:self.client,master=FakeMaster(),cm_master=FakeMaster(),
            ledger=DailyRiskLedger(Path(self.tmp.name)/'ledger.json'),now=lambda:datetime(2026,8,30,10,0).astimezone(),live_gate=lambda:True)

    def payload(self, direction):
        symbol,kind=('CE100','CE') if direction=='BULLISH' else ('PE100','PE')
        return dict(broker='fyers',underlying='NSE:TEST-EQ',expiry='2026-09-03',lots=1,invalidation=94 if direction=='BULLISH' else 106,
                    enforce_risk_controls=False,minimum_reward_to_risk=1,
                    proposal=dict(kind='LONG_OPTION',source='ANALYSIS_HANDOFF',label='Buy ATM option',direction=direction,target_exit_points=10,
                                  legs=[dict(action='BUY',symbol=symbol,strike=100,option_type=kind)]))

    def test_bullish_call_and_bearish_put_submit_one_buy_only(self):
        for direction,symbol in [('BULLISH','CE100'),('BEARISH','PE100')]:
            with self.subTest(direction=direction):
                preview=self.service.prepare(self.payload(direction))
                self.assertEqual(len(preview['instrument']['contracts']),1)
                self.assertEqual(preview['instrument']['worst_case_risk'],preview['instrument']['minimum_cash_required'])
                result=self.service.submit(preview['preview_id'],preview['confirmation_phrase'])
                self.assertEqual(result['status'],'OPEN')
                self.assertEqual(self.client.sent[-1]['symbol'],symbol)
                self.assertEqual(self.client.sent[-1]['side'],1)
        self.assertEqual(len(self.client.sent),2)

    def test_sell_leg_wrong_type_or_spread_fails_before_broker_mutation(self):
        for changes in [dict(action='SELL'),dict(option_type='CE')]:
            payload=self.payload('BEARISH');payload['proposal']['legs'][0].update(changes)
            with self.assertRaisesRegex(ValueError,'SELL legs are forbidden'):
                self.service.prepare(payload)
        payload=self.payload('BEARISH');payload['proposal']['legs']*=2
        with self.assertRaises(ValueError):self.service.prepare(payload)
        payload=self.payload('BEARISH');payload['proposal']['kind']='OPTION_SPREAD'
        with self.assertRaisesRegex(ValueError,'spread tickets must be refreshed'):self.service.prepare(payload)
        self.assertEqual(self.client.sent,[])

    def test_builder_chooses_atm_matching_type_with_no_sell(self):
        chain=self.client.optionchain({'strikecount':10});expiry=chain['data']['expiryData'][0]
        master=FakeMaster().lookup([r['symbol'] for r in chain['data']['optionsChain']])
        for direction,symbol in [('BULLISH','CE100'),('BEARISH','PE100')]:
            r=build_long_option_proposals(chain,expiry,master,direction,dict(invalidation=94 if direction=='BULLISH' else 106,stop_basis='price',minimum_reward_to_risk=1))
            p=r['proposals'][0]
            self.assertEqual(p['legs'][0]['symbol'],symbol)
            self.assertEqual([leg['action'] for leg in p['legs']],['BUY'])
            self.assertIsNone(p['max_profit_per_lot'])

    def test_bearish_cash_equity_remains_sell(self):
        payload=dict(broker='fyers',underlying='NSE:TEST-EQ',quantity=2,invalidation=105,cash_product='INTRADAY',enforce_risk_controls=False,
                     proposal=dict(kind='EQUITY',direction='BEARISH',label='Cash short',target=90))
        with patch.object(self.service,'_equity_leverage',return_value=(5,'30/08/2026')):
            preview=self.service.prepare(payload)
        self.assertEqual(preview['instrument']['contracts'][0]['action'],'SELL')

    def test_option_batch_needs_no_allocation_and_lots_remain_editable(self):
        payload=self.payload('BEARISH')
        for lots in (1,3):
            payload['lots']=lots
            preview=self.service.prepare_batch(dict(items=[payload]))
            self.assertEqual(preview['items'][0]['instrument']['lots'],lots)
            self.assertEqual(preview['aggregate']['order_count'],1)
            self.assertEqual(preview['items'][0]['instrument']['contracts'][0]['action'],'BUY')

    def test_optional_option_budget_caps_funding(self):
        with self.assertRaisesRegex(RuntimeError,'cannot fund'):
            self.service.prepare_batch(dict(items=[self.payload('BEARISH')],allocation_budget=100))
