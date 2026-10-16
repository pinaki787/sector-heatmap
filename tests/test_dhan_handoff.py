import unittest
from datetime import datetime
from types import SimpleNamespace
from sector_heatmap.dhan_execution import IST
from sector_heatmap.dhan_handoff import DhanHandoff

class Tests(unittest.TestCase):
    def setUp(self):
        expiry='2026-12-29'
        self.calls=[]
        class Client:
            client_id='owner'
            def request(inner,method,path,payload=None):
                self.calls.append((method,path,payload))
                if path=='/optionchain/expirylist':return {'data':[expiry]}
                if path=='/optionchain':
                    return {'status':'success','data':{'last_price':100,'oc':{'100':{
                        'ce':{'security_id':10,'last_price':5,'top_bid_price':4.95,'top_ask_price':5,'oi':100000,'volume':100000,
                            'greeks':{'delta':.5,'gamma':.01,'theta':-.1,'vega':.2},'implied_volatility':20},
                        'pe':{'security_id':11,'last_price':5,'top_bid_price':4.95,'top_ask_price':5,'oi':100000,'volume':100000,
                            'greeks':{'delta':-.5,'gamma':.01,'theta':-.1,'vega':.2},'implied_volatility':20}}}}}
                if path=='/positions':return [{'dhanClientId':'other','netQty':1}]
                raise AssertionError('Unexpected provider path '+path)
        rows=[dict(SEM_SMST_SECURITY_ID=str(sid),SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='D',SEM_OPTION_TYPE=side,
            SEM_EXPIRY_DATE=expiry,SEM_STRIKE_PRICE='100',SEM_LOT_UNITS='25',SEM_TICK_SIZE='5') for sid,side in ((10,'CE'),(11,'PE'))]
        self.context=object.__new__(DhanHandoff)
        self.context.client=Client()
        self.context.execution=SimpleNamespace(master=SimpleNamespace(load=lambda now:rows))
        self.context.sectors=SimpleNamespace(provider=SimpleNamespace(resolve=lambda symbol:{'securityId':'1','exchangeSegment':'NSE_EQ'}))
    def test_native_call_put_contracts_and_chain_evidence(self):
        for direction,side in (('BULLISH','CE'),('BEARISH','PE')):
            plan=self.context.options('NSE:TEST-EQ',direction,{'invalidation':90 if side=='CE' else 110,'stop_basis':'price','enforce_risk_controls':False})
            self.assertEqual(plan['broker'],'DHAN')
            leg=plan['proposals'][0]['legs'][0]
            self.assertEqual(leg['option_type'],side)
            self.assertTrue(leg['symbol'].startswith('NSE_FNO:'))
            self.assertEqual(leg['lot_size'],25)
            self.assertEqual(leg['tick_size'],.05)
        self.assertTrue(all(path.startswith('/optionchain') for _,path,_ in self.calls))
    def test_mixed_owner_positions_rejected(self):
        with self.assertRaises(PermissionError):self.context.positions()
    def test_master_mismatch_never_infers_contract(self):
        self.context.execution.master.load=lambda now:[]
        plan=self.context.options('NSE:TEST-EQ','BULLISH',{'invalidation':90})
        self.assertEqual(plan['proposals'],[])


class NativeSymbolTests(unittest.TestCase):
    def test_hyphenated_cash_ticker_survives_derivative_suffix(self):
        from sector_heatmap.dhan_execution import contract_underlying
        row={'SEM_SEGMENT':'D','SEM_OPTION_TYPE':'CE','SEM_TRADING_SYMBOL':'BAJAJ-AUTO-Oct2026-9000-CE'}
        self.assertEqual(contract_underlying(row),'BAJAJ-AUTO')
        self.assertEqual(contract_underlying({'SEM_SEGMENT':'E','SEM_TRADING_SYMBOL':'BAJAJ-AUTO'}),'BAJAJ-AUTO')

    def test_bse_cash_equity_uses_bse_group_and_tick(self):
        from sector_heatmap.dhan_execution import DhanMaster
        now=datetime(2026,10,13,12,tzinfo=IST)
        master=DhanMaster();master.day=now.date()
        master.rows=[dict(SEM_SMST_SECURITY_ID='500325',SEM_EXM_EXCH_ID='BSE',SEM_SEGMENT='E',SEM_SERIES='A',
            SEM_TRADING_SYMBOL='RELIANCE',SEM_LOT_UNITS='1',SEM_TICK_SIZE='5',SEM_EXPIRY_DATE='',SEM_OPTION_TYPE='XX',SEM_STRIKE_PRICE='0')]
        contract=master.resolve({'underlying':'BSE:RELIANCE','proposal':{'kind':'EQUITY'}},now)
        self.assertEqual(contract['exchange_segment'],'BSE_EQ')
        self.assertEqual(contract['tick_size'],.05)
