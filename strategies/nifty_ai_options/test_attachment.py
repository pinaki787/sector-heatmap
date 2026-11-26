import unittest,tempfile,json
from pathlib import Path
from attachment import candidate_rows,verify_position
from execution import Execution
SYMBOL='NSE:NIFTY50CE'
META=dict(symbol=SYMBOL,option_type='CE',lot_size=65,tick_size=.05,expiry_epoch=4102444800,underlying_asset='NIFTY')
CONFIG=dict(broker='FYERS',execution_route='OPTIONS',execution_mode='LIVE',underlying='NSE:NIFTY50-INDEX',lots=1,product='MARGIN')
REQUEST=dict(symbol=SYMBOL,quantity=65,product='MARGIN')
class API:
    qty=65;product='MARGIN';pending=False
    def positions(self):return dict(s='ok',netPositions=[dict(symbol=SYMBOL,netQty=self.qty,productType=self.product,buyAvg=44)])
    def orderbook(self):return dict(s='ok',orderBook=[dict(symbol=SYMBOL,status=6)] if self.pending else [])
    def funds(self):return dict(s='ok',fund_limit=[dict(id=10,equityAmount=100000)])
    def place_order(self,**kwargs):raise AssertionError('Attachment must not place an order')
class Tests(unittest.TestCase):
    def test_list_and_exact_verification(self):
        api=API();rows=candidate_rows(api,CONFIG,lambda s:META)
        self.assertEqual(rows[0]['quantity'],65)
        self.assertEqual(verify_position(api,CONFIG,REQUEST,lambda s:META)['average_price'],44)
    def test_changed_quantity_pending_product_paper_and_short_reject(self):
        for qty,product,pending,mode in [(0,'MARGIN',False,'LIVE'),(-65,'MARGIN',False,'LIVE'),(130,'MARGIN',False,'LIVE'),(65,'INTRADAY',False,'LIVE'),(65,'MARGIN',True,'LIVE'),(65,'MARGIN',False,'PAPER')]:
            with self.subTest(qty=qty,product=product,pending=pending,mode=mode):
                api=API();api.qty=qty;api.product=product;api.pending=pending
                with self.assertRaises(ValueError):verify_position(api,dict(CONFIG,execution_mode=mode),REQUEST,lambda s:META)
    def test_adoption_journals_exact_owned_holding_without_buy(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();e=Execution(api,'account',folder,True,1,'MARGIN',lambda s:META)
            try:
                config=dict(CONFIG,attach_position=REQUEST)
                owned=dict(symbol=SYMBOL,quantity=65,side='CE',fill_price=44,entry_timestamp=123,attached_existing=True)
                e.adopt_existing(owned,config)
                self.assertEqual(e.state['position'],owned)
                self.assertEqual(e.state['attachments'][0]['orders_submitted'],0)
                e.adopt_existing(owned,config)
                self.assertEqual(e.state['attachments'][-1]['previous_position'],owned)
            finally:e.close()
    def test_changed_broker_holding_before_commit_leaves_journal_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();e=Execution(api,'account',folder,True,1,'MARGIN',lambda s:META)
            try:
                api.qty=130
                with self.assertRaises(ValueError):e.adopt_existing(dict(symbol=SYMBOL,quantity=65),dict(CONFIG,attach_position=REQUEST))
                self.assertIsNone(e.state['position']);self.assertIsNone(e.state['pending'])
            finally:e.close()


class AttachmentLifecycleTests(unittest.TestCase):
    def test_adopted_position_exit_sells_owned_quantity_without_new_buy(self):
        from unittest.mock import patch
        import time
        class Broker(API):
            sent=[]
            def place_order(self,data):
                self.sent.append(data);self.qty=0
                return dict(s='ok',id='owned-exit')
            def orderbook(self):
                return dict(s='ok',orderBook=[dict(id='owned-exit',status=2,filledQty=65,tradedPrice=45)] if self.sent else [])
        with tempfile.TemporaryDirectory() as folder:
            api=Broker();api.sent=[]
            e=Execution(api,'account',folder,True,1,'MARGIN',lambda s:META)
            try:
                owned=dict(symbol=SYMBOL,quantity=65,side='CE',option_type='CE',expiry=str(META['expiry_epoch']),fill_price=44,entry_timestamp=time.time(),attached_existing=True)
                e.adopt_existing(owned,dict(CONFIG,attach_position=REQUEST))
                with patch('execution.time.sleep'):
                    e.submit(dict(action='SELL',position=owned,timestamp=time.time()),dict(ltp=45,timestamp=time.time()))
                self.assertEqual(len(api.sent),1);self.assertEqual(api.sent[0]['side'],-1);self.assertEqual(api.sent[0]['qty'],65)
                self.assertIsNone(e.state['position']);self.assertIsNone(e.state['pending'])
            finally:e.close()
    def test_explicit_reattachment_preserves_retained_ownership_for_same_broker_position(self):
        import hashlib
        class Broker(API):
            def get_profile(self):return dict(s='ok',data=dict(fy_id='owner'))
        with tempfile.TemporaryDirectory() as folder:
            account=hashlib.sha256(b'owner').hexdigest();api=Broker()
            e=Execution(api,account,folder,True,1,'MARGIN',lambda s:META)
            owned=dict(symbol=SYMBOL,quantity=65,side='CE',fill_price=44,entry_timestamp=123,attached_existing=True)
            config=dict(CONFIG,attach_position=REQUEST)
            e.adopt_existing(owned,config);e.close()
            resumed=Execution(api,account,folder,True,1,'MARGIN',lambda s:META,attachment_config=config)
            try:self.assertEqual(resumed.state['position'],owned)
            finally:resumed.close()


class LaunchPathRegressionTests(unittest.TestCase):
    def test_actual_preflight_function_has_no_runtime_attachment_variable(self):
        import live
        from unittest.mock import Mock,patch
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';config.write_text(json.dumps(dict(reference_value=400,account='test')))
            api=Mock()
            def choice(api,master,config,side,**kw):
                return dict(symbol=side,expiry='4102444800'),.15 if side=='CE' else -.15
            with patch('live.client',return_value=api),patch('live.Reads',side_effect=lambda a:a),patch('live.validate_config',return_value={}),patch('live.Master'),patch('live.choose',side_effect=choice):
                api.market_status.return_value=dict(s='ok')
                live.preflight(SimpleNamespace(config=str(config),output=str(Path(folder)/'preflight')))
            self.assertTrue((Path(folder)/'preflight/preflight.json').exists())
    def test_runtime_bootstrap_selects_exact_attached_contract(self):
        import ast,live
        from unittest.mock import Mock
        from types import SimpleNamespace
        source=Path(live.__file__).read_text();tree=ast.parse(source)
        stream=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='stream')
        node=next(n for n in ast.walk(stream) if isinstance(n,ast.FunctionDef) and n.name=='select')
        code=compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'runtime-select','exec')
        engine=SimpleNamespace(under_result=dict(direction=-1),last_time={},contract=dict(option_brick=16.67),premium_result=dict(host_atr=1),update=Mock(),reset_contract=Mock())
        choose=Mock(return_value=(dict(symbol=SYMBOL),.15))
        env=dict(engine=engine,config=dict(timeframe=5),api=Mock(),master=Mock(),choose=choose,history=Mock(return_value=[[1,None,None,None,44,None]]),start='start',end='end',out=Path('/unused'),chart_source=Mock())
        exec(code,env)
        result=env['select']('CE',dict(symbol=SYMBOL,expiry='4102444800'))
        self.assertEqual(result,SYMBOL)
        self.assertEqual(choose.call_args.kwargs['exact_symbol'],SYMBOL)
        self.assertEqual(choose.call_args.args[2]['expiry'],'4102444800')
