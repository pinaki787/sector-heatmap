import unittest
from sector_heatmap.market_handoff import analyze,indicators,catalog,native_adapter
from sector_heatmap.handoff_ai import HandoffAI

NOW=1792134005


class Broker:
    def __init__(self):self.stopped=False;self.position_reads=0;self.new_exposure=False;self.stale=False
    def positions(self):
        self.position_reads+=1
        return [{'symbol':'NSE:NIFTY26O1923150CE','netQty':65}] if self.new_exposure and self.position_reads>1 else []
    def orders(self):return []
    def start(self):pass
    def stop(self):self.stopped=True
    def underlying(self,symbol):return {'instrument':'INDEX'}
    def live_price(self,c,now):return 101.,now
    def resolve(self,c,direction):return dict(symbol='NSE:NIFTY26O1923150'+('CE' if direction=='BULLISH' else 'PE'),lot_size=65,tick_size=.05)
    def quote(self,symbol):return dict(bid=10.95,ask=11.,exchange_at=NOW-20 if self.stale else NOW,received_at=NOW)
    def candles(self,c):
        seconds={'5 minutes':300,'15 minutes':900,'1 hour':3600}[c['timeframe']]
        opening=int(NOW)//seconds*seconds
        base=10 if c['underlying'].endswith(('CE','PE')) else 100
        return [dict(timestamp=opening-(60-i)*seconds,open=base+i*.01,high=base+i*.01+.2,low=base+i*.01-.2,close=base+i*.01+.05) for i in range(60)]


class AI:
    def review(self,evidence):return dict(provider='OpenAI',model='fixture',summary='Completed broker evidence',recommendations=[dict(symbol=r['symbol'],decision='BULLISH',confidence='MODERATE',rationale='Trend supported',risks=[]) for r in evidence['instruments']])


class MarketHandoffTests(unittest.TestCase):
    def run_analysis(self,broker):return analyze({'symbols':['NSE:NIFTY50-INDEX']},broker,AI(),'FYERS','selected',clock=lambda:NOW)
    def test_dhan_catalog_recognizes_native_index_metadata_and_requests_commodities(self):
        calls=[]
        class Native:
            def search(self,text,market=None):
                calls.append(market)
                return [dict(symbol='NSE:NIFTY',name='NIFTY')] if text=='NIFTY' else []
            def underlying(self,symbol):return dict(SEM_SEGMENT='I',SEM_INSTRUMENT_NAME='INDEX')
        result=catalog(Native(),'DHAN')
        self.assertEqual(result['instruments'][0]['symbol'],'NSE:NIFTY')
        self.assertEqual(set(calls),{'ALL'})

    def test_native_option_history_uses_exact_contract_master(self):
        class Base:
            def __init__(self,service):pass
            def _rows(self):return [dict(SEM_SMST_SECURITY_ID='123',SEM_SEGMENT='D')]
            def _segment(self,row):return 'NSE_FNO'
            def contract(self,symbol):return dict(symbol=symbol)
            def underlying(self,symbol):raise ValueError('Not a cash underlying')
        broker=native_adapter(Base,None)
        self.assertEqual(broker.underlying('NSE_FNO:123')['SEM_SMST_SECURITY_ID'],'123')
        with self.assertRaises(ValueError):broker.underlying('NSE_FNO:999')

    def test_native_atm_premium_entry_stop_target_and_evidence(self):
        broker=Broker();r=self.run_analysis(broker);plan=r['instruments'][0]['recommended_plan']
        self.assertTrue(broker.stopped);self.assertEqual(plan['entry'],11)
        self.assertLess(plan['stop_loss'],plan['entry']);self.assertGreater(plan['target'],plan['entry'])
        self.assertEqual(r['account_id'],'selected');self.assertEqual(r['order_authority'],'NONE')
    def test_exposure_appearing_during_ai_is_excluded_before_publish(self):
        broker=Broker();broker.new_exposure=True;r=self.run_analysis(broker)
        self.assertEqual(r['instruments'],[]);self.assertIn('Exposure appeared',r['exclusions'][0]['reason'])
    def test_stale_option_evidence_forces_wait_without_invented_prices(self):
        broker=Broker();broker.stale=True;r=self.run_analysis(broker)
        self.assertEqual(r['instruments'][0]['recommendation']['decision'],'WAIT')
        self.assertIsNone(r['instruments'][0]['recommended_plan'])
    def test_bad_or_stale_completed_candles_are_rejected(self):
        rows=Broker().candles({'underlying':'X','timeframe':'5 minutes'})
        rows[-1]['low']=200
        with self.assertRaises(ValueError):indicators(rows,300,NOW)
        rows=Broker().candles({'underlying':'X','timeframe':'5 minutes'})
        with self.assertRaises(ValueError):indicators(rows,300,NOW+1000)
    def test_ai_request_is_structured_and_cannot_invent_another_symbol(self):
        class Response:
            status_code=200
            def json(self):return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"summary":"x","recommendations":[{"symbol":"OTHER","decision":"BULLISH","confidence":"HIGH","rationale":"x","risks":[]}]}'}]}]}
        calls=[]
        ai=HandoffAI('.',sender=lambda *args,**kwargs:calls.append(kwargs) or Response(),key_reader=lambda:'fixture-secret')
        with self.assertRaisesRegex(ValueError,'submitted broker'):ai.review({'instruments':[{'symbol':'NIFTY'}]})
        self.assertTrue(calls[0]['json']['text']['format']['strict']);self.assertFalse(calls[0]['json']['store'])

    def test_disabling_api_analysis_never_reads_a_key_or_sends_a_request(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'.private').mkdir();(root/'.private/openai-api-analysis-disabled').touch()
            nested=root/'accounts'/'selected'/'source';nested.mkdir(parents=True)
            calls=[]
            ai=HandoffAI(nested,sender=lambda *a,**k:calls.append('request'),key_reader=lambda:calls.append('key'))
            with self.assertRaisesRegex(ValueError,'disabled by your preference'):ai.review({'instruments':[]})
            self.assertEqual(calls,[])
