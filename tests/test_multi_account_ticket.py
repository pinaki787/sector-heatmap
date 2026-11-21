import tempfile, unittest, threading
from pathlib import Path
from sector_heatmap.multi_account_ticket import Tickets,sized_review

ACCOUNTS={a:dict(id=a,broker=b,label=a) for a,b in [('a','FYERS'),('b','DHAN')]}
def resolve(aid):
    if aid not in ACCOUNTS:raise PermissionError('not owned')
    return ACCOUNTS[aid]
class MultiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Tickets(Path(self.temp.name)/'tickets.sqlite3');self.calls=[]
    def tearDown(self):self.temp.cleanup()
    def call(self,account,action,payload):
        self.calls.append((account['id'],action,payload))
        if action=='submit-batch':return dict(status='PENDING',order_ids=[account['id']])
        if action=='prepare':return dict(margin_required=100 if account['id']=='a' else 200)
        items=payload['items'];cost=sum(i.get('quantity',i['lots'])* (100 if account['id']=='a' else 200) for i in items)
        return dict(preview_id='p-'+account['id'],confirmation_phrase='confirm',items=items,aggregate=dict(cash_reserved=cost),submission_eligible=True,live_submission_enabled=True)
    def items(self):
        return [dict(account_id=a,amount=1000,ticket=dict(proposal=dict(kind='EQUITY'),underlying='NSE:ABC-EQ')) for a in ACCOUNTS]
    def test_same_full_amount_per_account_different_quantity(self):
        result=self.store.prepare('u',self.items(),resolve,self.call)
        self.assertEqual([r['allocation']['amount'] for r in result['rows']],[1000,1000])
        self.assertEqual([r['preview']['items'][0]['quantity'] for r in result['rows']],[9,4])
    def test_override(self):
        items=self.items();items[1]['amount']=2000
        result=self.store.prepare('u',items,resolve,self.call)
        self.assertEqual(result['rows'][1]['preview']['items'][0]['quantity'],9)
    def test_ownership_validated_before_any_reads(self):
        items=self.items();items[1]['account_id']='foreign'
        with self.assertRaises(PermissionError):self.store.prepare('u',items,resolve,self.call)
        self.assertFalse(self.calls)
    def test_one_failure_keeps_other_review(self):
        def call(account,action,payload):
            if account['id']=='b':raise ValueError('auth unavailable')
            return self.call(account,action,payload)
        value=self.store.prepare('u',self.items(),resolve,call)
        self.assertEqual([r['state'] for r in value['rows']],['READY','BLOCKED'])
    def test_lost_response_is_consumed_and_persistent(self):
        value=self.store.prepare('u',self.items(),resolve,self.call);sent=[]
        def call(account,action,payload):
            sent.append(account['id'])
            if account['id']=='b':raise TimeoutError('lost response')
            return dict(status='PENDING')
        result=self.store.submit('u',value['batch_id'],value['confirmation_phrase'],resolve,call)
        self.assertEqual([r['state'] for r in result['rows']],['RESULT','UNCERTAIN'])
        fresh=Tickets(self.store.path);fresh.submit('u',value['batch_id'],value['confirmation_phrase'],resolve,call)
        self.assertEqual(sent,['a','b'])
        with self.assertRaises(ValueError):fresh.prepare('u',self.items(),resolve,self.call)
    def test_owner_cannot_read_or_submit_other_user(self):
        value=self.store.prepare('u',self.items(),resolve,self.call)
        with self.assertRaises(PermissionError):self.store.get('v',value['batch_id'])
        with self.assertRaises(PermissionError):self.store.submit('v',value['batch_id'],value['confirmation_phrase'],resolve,self.call)
        self.assertEqual(self.store.history('v'),[])
    def test_budget_fail_closed(self):
        for value in (0,-1,'NaN','Infinity'):
            result=self.store.prepare('u',[dict(self.items()[0],amount=value)],resolve,self.call)
            self.assertEqual(result['rows'][0]['state'],'BLOCKED')
        def overshoot(a,action,payload):
            if action=='prepare':return dict(margin_required=100)
            return dict(aggregate=dict(cash_reserved=1001),items=payload['items'])
        with self.assertRaises(ValueError):sized_review(ACCOUNTS['a'],self.items()[0]['ticket'],1000,overshoot)
    def test_concurrent_submit_claim(self):
        value=self.store.prepare('u',self.items()[:1],resolve,self.call);sent=[]
        def call(a,action,payload):sent.append(a['id']);return dict(status='PENDING')
        args=('u',value['batch_id'],value['confirmation_phrase'],resolve,call)
        workers=[threading.Thread(target=self.store.submit,args=args) for _ in range(4)]
        for w in workers:w.start()
        for w in workers:w.join()
        self.assertEqual(sent,['a'])
    def test_crash_claim_remains_blocked(self):
        value=self.store.prepare('u',self.items()[:1],resolve,self.call)
        def crash(a,action,payload):raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.store.submit('u',value['batch_id'],value['confirmation_phrase'],resolve,crash)
        result=self.store.submit('u',value['batch_id'],value['confirmation_phrase'],resolve,self.call)
        self.assertEqual(result['rows'][0]['state'],'SUBMITTING')
    def test_no_implicit_selection_and_duplicate(self):
        with self.assertRaises(ValueError):self.store.prepare('u',[],resolve,self.call)
        with self.assertRaises(ValueError):self.store.prepare('u',[self.items()[0]]*2,resolve,self.call)

class BrokerPoolAndParserTests(MultiTests):
    def test_pool_is_per_broker_not_per_stock(self):
        items=self.items()
        for item in items:item['ticket']={'items':[dict(proposal=dict(kind='EQUITY'),underlying='NSE:A-EQ'),dict(proposal=dict(kind='EQUITY'),underlying='NSE:B-EQ')]}
        value=self.store.prepare('u',items,resolve,self.call)
        self.assertEqual([r['allocation']['amount'] for r in value['rows']],[1000,1000])
        self.assertEqual([[i['quantity'] for i in r['preview']['items']] for r in value['rows']],[[4,4],[2,2]])
        self.assertTrue(all(r['allocation']['reserved']<=1000 for r in value['rows']))
    def test_same_broker_second_account_needs_distinct_explicit_scope(self):
        accounts=dict(ACCOUNTS,c=dict(id='c',broker='FYERS',label='Other FYERS'))
        with self.assertRaisesRegex(ValueError,'one explicit execution account'):
            self.store.prepare('u',[self.items()[0],dict(self.items()[0],account_id='c')],accounts.__getitem__,self.call)
        self.assertFalse(self.calls)
    def test_parser_native_quantity_and_single_submit_route(self):
        from sector_heatmap.multi_account_ticket import identity
        contract=dict(symbol='native',underlying='ABC',exchange_segment='NSE_EQ',option_type=None,lot_size=1)
        ticket=dict(_manual_parser=True,source_account_id='a',text='BUY ABC AT 100 SL 90 TARGET 110',_identity=identity(contract))
        sent=[]
        def call(a,action,payload):
            if action=='parser-parse':return dict(mapping=dict(contract=contract))
            if action=='parser-prepare':return dict(preview_id='P',confirmation_phrase='C',margin_required=payload['lots']*100,submission_eligible=True,live_submission_enabled=True,order=dict(symbol='native',qty=payload['lots'],limitPrice=100))
            sent.append(action);return dict(status='PENDING')
        value=self.store.prepare('u',[dict(account_id='a',amount=1000,ticket=ticket)],resolve,call)
        self.assertEqual(value['rows'][0]['preview']['order']['qty'],9)
        self.store.submit('u',value['batch_id'],value['confirmation_phrase'],resolve,call)
        self.assertEqual(sent,['parser-submit'])
    def test_paper_is_not_upgraded(self):
        value=self.store.prepare('u',[dict(self.items()[0],ticket=dict(mode='PAPER',proposal=dict(kind='EQUITY')))],resolve,self.call)
        self.assertEqual(value['rows'][0]['state'],'BLOCKED')
        self.assertFalse(self.calls)
    def test_native_dhan_description_preserves_instrument_product_and_levels(self):
        from sector_heatmap.multi_account_ticket import native_description
        from sector_heatmap.recommendation_text import parse_text
        from types import SimpleNamespace
        from unittest.mock import Mock
        row=dict(SEM_SMST_SECURITY_ID='1',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='E',SEM_TRADING_SYMBOL='ABC')
        master=Mock();master.resolve.return_value=dict(security_id='1',exchange_segment='NSE_EQ',option_type=None);master.load.return_value=[row]
        result=native_description(SimpleNamespace(master=master),dict(security_id='1',exchange_segment='NSE_EQ',transaction_type='BUY',product_type='CNC',limit_price='100',invalidation='90',target_price='120'))
        parsed=parse_text(result['text'])
        self.assertEqual((parsed['underlying'],parsed['entry'],parsed['stop_loss'],parsed['targets']),('ABC',100,90,[120]))
        self.assertEqual(result['amount_product'],'CNC')
        self.assertTrue(result['_source_native'])

class PortableOptionMappingTests(unittest.TestCase):
    def test_only_native_symbol_may_change(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock,patch
        from sector_heatmap.fyers_execution import FyersExecutionService,FyersExecutionUnavailable
        service=object.__new__(FyersExecutionService)
        service.master=Mock();service.master.lookup.return_value={}
        service.now=lambda:datetime.now(timezone.utc)
        selected=dict(symbol='FYERS-EXACT',strike=25000,lot_size=65,tick_size=.05,expiry_epoch='1900000000',open_interest=100,volume=100,greeks={})
        options=dict(status='READY',expiry_iso='2030-01-01',proposals=[dict(legs=[selected])])
        quote=dict(bid=99.9,ask=100)
        proposal=dict(kind='LONG_OPTION',direction='BULLISH',legs=[dict(action='BUY',symbol='DHAN-NATIVE',strike=25000,option_type='CE')])
        payload=dict(underlying='NSE:NIFTY50-INDEX',expiry='2030-01-01',lots=1,portable_manual_ticket=True)
        with patch('sector_heatmap.fyers_execution.fetch_fyers_chain',return_value=({'data':{'optionsChain':[]}},'expiry')),patch('sector_heatmap.fyers_execution.build_long_option_proposals',return_value=options),patch('sector_heatmap.fyers_execution._quotes',return_value={'FYERS-EXACT':quote}):
            result=service._preflight_long_option(Mock(),payload,proposal,None)
            self.assertEqual(result['contracts'][0]['symbol'],'FYERS-EXACT')
            self.assertEqual(result['contracts'][0]['strike'],25000)
            self.assertEqual(result['quantity'],65)
            with self.assertRaises(FyersExecutionUnavailable):service._preflight_long_option(Mock(),dict(payload,expiry='2030-02-01'),proposal,None)
            with self.assertRaises(FyersExecutionUnavailable):service._preflight_long_option(Mock(),dict(payload,portable_manual_ticket=False),proposal,None)
            changed=dict(proposal,legs=[dict(proposal['legs'][0],strike=25100)])
            with self.assertRaises(FyersExecutionUnavailable):service._preflight_long_option(Mock(),payload,changed,None)

if __name__=='__main__':unittest.main()
