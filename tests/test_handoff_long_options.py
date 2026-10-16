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
                    underlying_exit_plan=dict(stop=94 if direction=='BULLISH' else 106,target=110 if direction=='BULLISH' else 90),
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
                self.assertGreater(self.client.sent[-1]['stopLoss'],0)
                self.assertGreater(self.client.sent[-1]['takeProfit'],0)
                self.assertEqual(self.client.sent[-1]['legType'],1)
        self.assertEqual(len(self.client.sent),2)

    def test_option_batch_sends_linked_exits(self):
        preview=self.service.prepare_batch(dict(items=[self.payload('BULLISH')]))
        self.service.submit_batch(preview['preview_id'],preview['confirmation_phrase'])
        self.assertEqual(len(self.client.sent),1)
        self.assertGreater(self.client.sent[0]['stopLoss'],0)
        self.assertGreater(self.client.sent[0]['takeProfit'],0)

    def test_cash_batch_carries_each_linked_exit(self):
        payload=dict(broker='fyers',underlying='NSE:TEST-EQ',quantity=2,invalidation=95,enforce_risk_controls=False,
                     proposal=dict(kind='EQUITY',direction='BULLISH',label='Cash',target=110))
        sent=[]
        def basket(orders):
            sent.extend(orders)
            return dict(s='ok',data=[dict(s='ok',id=str(i+1)) for i in range(len(orders))])
        self.client.place_basket_orders=basket
        preview=self.service.prepare_batch(dict(items=[payload]))
        self.service.submit_batch(preview['preview_id'],preview['confirmation_phrase'])
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0]['stopLoss'],5)
        self.assertEqual(sent[0]['takeProfit'],10)

    def test_protection_changes_require_new_review(self):
        from copy import deepcopy
        from sector_heatmap.fyers_execution import _review_terms
        p=self.service.prepare(self.payload('BULLISH'))
        changed=deepcopy(p);changed['protection']['stop_loss_price']+=.05
        self.assertNotEqual(_review_terms(p),_review_terms(changed))
        changed=deepcopy(p);changed['protection']['calculated_at']='later'
        self.assertEqual(_review_terms(p),_review_terms(changed))

    def test_missing_exit_plan_blocks_before_submission(self):
        payload=self.payload('BULLISH');payload.pop('underlying_exit_plan')
        with self.assertRaises(ValueError):self.service.prepare(payload)
        self.assertEqual(self.client.sent,[])

    def test_cash_order_contains_offsets_not_absolute_prices(self):
        payload=dict(broker='fyers',underlying='NSE:TEST-EQ',quantity=2,invalidation=95,cash_product='INTRADAY',enforce_risk_controls=False,
                     proposal=dict(kind='EQUITY',direction='BULLISH',label='Cash',target=110))
        preview=self.service.prepare(payload)
        self.service.submit(preview['preview_id'],preview['confirmation_phrase'])
        self.assertEqual(self.client.sent[0]['stopLoss'],5)
        self.assertEqual(self.client.sent[0]['takeProfit'],10)
        self.assertEqual(self.client.sent[0]['legType'],1)

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
