import copy,json,math,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import native_sizing as native
from automatic_sizing import ReferenceMonitor,AutoSizedStrategy

DELTA=dict(account='a'*32,broker='DELTA_INDIA',underlying='ETHUSD',market='CRYPTO',execution_route='DIRECT',timeframe=5,reference_value=100)
FIELDS=['Completed native box','Completed parent start','Completed parent end','Completed native time','Current parent start','Current parent end','Host end','Calculated at','Native tick']
def reply(now=1000000):
    values=[100,(now-7200)*1000,(now-3600)*1000,(now-10800)*1000,(now-3600)*1000,(now+3600)*1000,now*1000,now*1000,.05]
    return dict(isError=False,structuredContent=dict(success=True,symbol='DELTAIN:ETHUSD.P',timeframe='30m',metainfo=dict(plots=[dict(title=name,id=str(i)) for i,name in enumerate(FIELDS)]),last_values=dict(plots={str(i):v for i,v in enumerate(values)})))
class NativeSizingTests(unittest.TestCase):
    def test_general_symbol_mapping_preserves_exchange_and_dated_contract(self):
        for symbol,broker,expected in [('ETHUSD','DELTA_INDIA','DELTAIN:ETHUSD.P'),('SOLUSD','DELTA_INDIA','DELTAIN:SOLUSD.P'),('NSE:RELIANCE-EQ','FYERS','NSE:RELIANCE'),('BSE:SENSEX-INDEX','FYERS','BSE:SENSEX'),('MCX:GOLDM26DECFUT','FYERS','MCX:GOLDMZ2026'),('NSE:RELIANCE26NOVFUT','FYERS','NSE:RELIANCEX2026')]:
            self.assertEqual(native.map_symbol(symbol,broker),expected)
        for symbol,broker in [('C-ETH-2000-010127','DELTA_INDIA'),('NSE:INVALID SYMBOL','FYERS'),('ETHUSD','OTHER')]:
            with self.assertRaises(ValueError):native.map_symbol(symbol,broker)
    def test_unknown_index_requires_unique_same_exchange_master_description(self):
        row=['']*17;row[1]='NIFTY IT';row[9]='NSE:NIFTYIT-INDEX'
        c=dict(DELTA,broker='FYERS',underlying=row[9],market='NSE')
        client=Mock();client.search_symbols.return_value={'structuredContent':{'success':True,'data':{'symbols':[{'symbol':'NSE:CNXIT','exchange':'NSE','type':'index','description':'Nifty IT Index'},{'symbol':'BSE:OTHER','exchange':'BSE','type':'index','description':'Nifty IT Index'}]}}}
        with patch('instrument_search.master_rows',return_value=[row]):self.assertEqual(native.resolve_symbol(c,client),'NSE:CNXIT')
        client.search_symbols.return_value={'structuredContent':{'success':True,'data':{'symbols':[]}}}
        with patch('instrument_search.master_rows',return_value=[row]):
            with self.assertRaises(ValueError):native.resolve_symbol(c,client)
    def test_valid_completed_window_and_full_precision_conversion(self):
        ref=native.parse_result(reply(),DELTA,now=1000001)
        self.assertEqual(ref['native_box'],100);self.assertEqual(ref['broker_symbol'],'ETHUSD');self.assertEqual(ref['native_provider'],'TRADINGVIEW')
        self.assertEqual(ref['completed_parent_at'],996400);self.assertEqual(ref['valid_until'],1036800)
        self.assertEqual(native.apply_reference(DELTA,ref)['reference_value'],100)
    def test_wrong_symbol_frame_and_failed_tool_are_rejected(self):
        for field,value in [('symbol','CRYPTO:ETHUSD'),('timeframe','1m'),('success',False)]:
            r=reply();r['structuredContent'][field]=value
            with self.assertRaises(ValueError):native.parse_result(r,DELTA,now=1000001)
    def test_forming_future_stale_and_missing_measurements_are_rejected(self):
        for field,value in [('0',0),('0',True),('0',float('nan')),('2',1001000*1000),('3',1001000*1000),('7',999000*1000),('6',900000*1000),('1',None)]:
            r=reply();r['structuredContent']['last_values']['plots'][field]=value
            with self.assertRaises(ValueError):native.parse_result(r,DELTA,now=1000001)
    def test_nse_requires_expected_completed_regular_session(self):
        c=dict(DELTA,broker='FYERS',underlying='NSE:NIFTY50-INDEX',market='NSE');r=reply();r['structuredContent']['symbol']='NSE:NIFTY'
        with patch('sector_heatmap.market_calendar.market_session',return_value={'last_completed_session':'2099-01-01'}):
            with self.assertRaisesRegex(ValueError,'expected completed'):native.parse_result(r,c,now=1000001)
    def test_mcx_overnight_gap_is_not_mistaken_for_stale_active_parent(self):
        c=dict(DELTA,broker='FYERS',underlying='MCX:GOLDM26DECFUT',market='MCX')
        r=reply();r['structuredContent']['symbol']='MCX:GOLDMZ2026'
        r['structuredContent']['last_values']['plots'].update({'1':(1000000-25*3600)*1000,'2':(1000000-24*3600)*1000,'3':(1000000-26*3600)*1000})
        ref=native.parse_result(r,c,now=1000001)
        self.assertEqual(ref['parent_hours'],14);self.assertEqual(ref['atr_length'],5)
        r['structuredContent']['last_values']['plots']['6']=900000*1000
        with self.assertRaises(ValueError):native.parse_result(r,c,now=1000001)
    def test_connection_is_not_shared_with_another_application_user(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);dbpath=root/'.private/dashboard-login/registry.sqlite3';dbpath.parent.mkdir(parents=True)
            with sqlite3.connect(dbpath) as db:
                db.execute('create table accounts(id text,user_id text,broker text)')
                db.executemany('insert into accounts values(?,?,?)',[('a'*32,'one','DELTA_INDIA'),('b'*32,'two','FYERS')])
            policy=root/'policy.json';policy.write_text(json.dumps({'enabled':True,'authorized_user_id':'one'}))
            with patch.object(native,'ROOT',root),patch.object(native,'POLICY',policy):
                self.assertEqual(native.authorize('a'*32,'DELTA_INDIA'),'one')
                with self.assertRaises(ValueError):native.authorize('b'*32,'FYERS')
                with self.assertRaises(ValueError):native.authorize('a'*32,'FYERS')
    def test_stale_official_cache_is_not_a_valid_reference(self):
        from native_reference import choose_reference
        r=native.parse_result(reply(),DELTA,now=1000001)
        self.assertIsNotNone(choose_reference([r],'ETHUSD','CRYPTO',now=1000002))
        self.assertIsNone(choose_reference([r],'ETHUSD','CRYPTO',now=r['valid_until']+1))

class FakeEngine:
    def __init__(self,config):
        self.config=dict(config);self.spot_size=config['reference_value']/46;self.position=None;self.pending_direction=None
        self.contract=dict(symbol='ETHUSD',spot_brick=self.spot_size);self.last_time={}
    def reset_contract(self,contract):self.contract=dict(contract,spot_brick=self.spot_size)
    def update(self,event):
        self.last_time[event['kind']]=event['timestamp']
        if event.get('exit') and self.position:
            p=self.position;self.position=None;return [dict(action='CLOSE_LONG',position=p)]
        if event.get('enter') and not self.position:
            self.position=dict(self.contract);return [dict(action='OPEN_LONG',position=dict(self.position))]
        return []
    def update_hybrid(self,event):
        self.last_time['hybrid_count']=self.last_time.get('hybrid_count',0)+1
        return self.update(event)
    def selected_gate_entry(self):return dict(action='OPEN_LONG')
class RuntimeRefreshTests(unittest.TestCase):
    def setup_engine(self):
        self.now=1000;self.ref=dict(native_box=100,completed_parent_at=900,valid_until=1100,reference_session='fixture',source='official',tv_symbol='DELTAIN:ETHUSD.P')
        config=native.apply_reference(DELTA,self.ref)
        self.monitor=ReferenceMonitor(config,clock=lambda:self.now,start=False)
        return AutoSizedStrategy(FakeEngine(config),self.monitor)
    def test_stale_size_blocks_entries_but_existing_exit_survives(self):
        e=self.setup_engine();e.position=dict(symbol='ETHUSD',spot_brick=100/46);self.now=1200
        result=e.update(dict(kind='underlying',timestamp=1,close=100,exit=True));self.assertEqual(result[0]['action'],'CLOSE_LONG')
        self.assertEqual(result[0]['position']['spot_brick'],100/46)
        self.assertEqual(e.update(dict(kind='underlying',timestamp=2,close=110,enter=True)),[]);self.assertIsNone(e.position)
        self.assertIsNone(e.selected_gate_entry())
    def test_changed_size_is_frozen_for_open_position_then_rebuilt_when_flat(self):
        e=self.setup_engine();e.reset_contract(dict(symbol='ETHUSD'));e.position=dict(e.contract)
        self.monitor.reference=dict(self.ref,native_box=200,completed_parent_at=950)
        e.update(dict(kind='underlying',timestamp=1,close=90));self.assertEqual(e.spot_size,100/46)
        e.update(dict(kind='underlying',timestamp=2,close=80,exit=True));self.assertIsNone(e.position)
        result=e.update(dict(kind='underlying',timestamp=3,close=110,enter=True));self.assertEqual(e.spot_size,200/46)
        self.assertEqual(result[0]['position']['spot_brick'],200/46)
    def test_pending_broker_intent_prevents_geometry_rebuild(self):
        e=self.setup_engine();e._exposure=lambda:True;self.monitor.reference=dict(self.ref,native_box=200)
        self.assertEqual(e.update(dict(kind='underlying',timestamp=1,close=110,enter=True)),[]);self.assertEqual(e.spot_size,100/46)
    def test_refresh_failure_does_not_extend_old_reference_lifetime(self):
        e=self.setup_engine();self.now=1101;self.monitor.fetch=Mock(side_effect=ValueError('unavailable'));self.monitor.refresh()
        self.assertIsNone(self.monitor.current());self.now=1200;self.assertIsNone(self.monitor.current())
        self.assertEqual(self.monitor.status()['state'],'WAITING_FOR_NATIVE_SIZE')

class HybridSizingRefreshTests(RuntimeRefreshTests):
    def test_hybrid_observations_replay_through_the_same_decision_path(self):
        e=self.setup_engine()
        e.update_hybrid(dict(kind='price',timestamp=1,close=90))
        e.update_hybrid(dict(kind='price',timestamp=2,close=91))
        self.monitor.reference=dict(self.ref,native_box=200)
        e.update_hybrid(dict(kind='price',timestamp=3,close=92))
        self.assertEqual(e.spot_size,200/46)
        self.assertEqual(e.last_time['hybrid_count'],3)
    def test_stale_sizing_blocks_hybrid_entry_but_retains_owned_exit(self):
        e=self.setup_engine();self.now=1200
        self.assertEqual(e.update_hybrid(dict(kind='price',timestamp=1,close=90,enter=True)),[])
        e.position=dict(symbol='ETHUSD',spot_brick=100/46)
        actions=e.update_hybrid(dict(kind='price',timestamp=2,close=89,exit=True))
        self.assertEqual(actions[0]['action'],'CLOSE_LONG')
