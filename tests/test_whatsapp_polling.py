from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from sector_heatmap.whatsapp_polling import WhatsAppPolling

class WhatsAppPollingTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'state.sqlite'
        self.now = datetime(2026,10,1,10,30,tzinfo=timezone.utc)
        self.account = {'verified':True,'occupied_symbols':[]}
        self.preview = {'parsed':{'action':'BUY','entry':26,'stop_loss':21,'targets':[30,35,40],'missing':[]},'mapping':{'status':'EXACT','contract':{'symbol':'NSE:CGPOWER26OCT900CE'}}}
        self.service = self.make()
        self.message = {'id':'one','group':'Trading With Mo 2.O','verified':True,'timestamp':self.now.isoformat(),'text':'CGPOWER 900 CE ABOVE 26 SL 21 TARGET 30,35,40','is_reply':False,'is_forwarded':False,'unread_verified':True,'is_unread':True,'is_latest_unread':True}
    def make(self):
        service = WhatsAppPolling(self.path,lambda _:self.preview,lambda:self.account,clock=lambda:self.now)
        self.addCleanup(service.db.close)
        return service
    def test_no_adapter_cannot_start(self):
        with self.assertRaises(ValueError):self.service.start()
        self.assertFalse(self.service.status()['running'])
    def test_dedup_survives_restart_and_reposted_message(self):
        self.assertEqual(self.service.ingest(self.message),'REVIEW')
        again=self.make()
        self.assertEqual(again.ingest(self.message),'DUPLICATE')
        self.assertEqual(again.ingest({**self.message,'id':'two'}),'IGNORED')
    def test_wrong_group_and_unverified_source(self):
        for change in [{'group':'Intraday F&O Trade Mo Group📈'},{'verified':False}]:
            self.assertEqual(self.service.ingest({**self.message,**change}),'UNVERIFIED_SOURCE')
        self.assertEqual(self.service.status()['queue'],[])
    def test_stale_future_unknown_date_reply_progress(self):
        for i,change in enumerate([{'timestamp':(self.now-timedelta(minutes=6)).isoformat()},{'timestamp':(self.now+timedelta(seconds=1)).isoformat()},{'timestamp':'10:30 AM'},{'is_reply':True},{'is_forwarded':True},{'text':self.message['text']+' TARGET HIT'},{'is_reply':None}]):
            self.assertEqual(self.service.ingest({**self.message,'id':str(i),**change}),'IGNORED')
    def test_exact_contract_and_broker_required(self):
        self.preview['mapping']['status']='AMBIGUOUS'
        self.assertEqual(self.service.ingest(self.message),'IGNORED')
        self.preview['mapping']['status']='EXACT';self.account['verified']=False
        self.assertEqual(self.service.ingest({**self.message,'id':'two'}),'IGNORED')
    def test_existing_position_or_order_excluded(self):
        self.account['occupied_symbols']=['NSE:CGPOWER26OCT900CE']
        self.assertEqual(self.service.ingest(self.message),'IGNORED')
    def test_review_rechecks_time_and_account_without_execution(self):
        self.service.ingest(self.message);key=self.service.status()['queue'][0]['id']
        self.assertEqual(self.service.review(key)['order_authority'],'NONE')
        self.account['occupied_symbols']=['NSE:CGPOWER26OCT900CE']
        with self.assertRaises(ValueError):self.service.review(key)
        self.account['occupied_symbols']=[];self.now+=timedelta(minutes=6)
        with self.assertRaises(ValueError):self.service.review(key)
    def test_stop_is_default_and_config_persists(self):
        self.service.configure({'group':'Trading With Mo 2.O','interval':120})
        restarted=self.make();self.assertEqual(restarted.config['interval'],120)
        self.assertFalse(restarted.status()['running'])
    def test_source_failure_fails_closed(self):
        def fail():raise RuntimeError('broker down')
        self.service.reconcile=fail
        self.assertEqual(self.service.ingest(self.message),'RECONCILIATION_UNAVAILABLE')
        self.assertEqual(self.service.status()['queue'],[])

    def test_missing_native_reader_blocks_start(self):
        from sector_heatmap.whatsapp_source import NativeWhatsAppSource
        self.service.source = NativeWhatsAppSource(Path(self.tmp.name)/"missing-reader")
        self.assertFalse(self.service.status()["source_ready"])
        self.assertIn("Build the native", self.service.status()["blocker"])
        with self.assertRaises(ValueError): self.service.start()

    def test_real_poll_failure_is_reported_without_ingestion(self):
        class Source:
            def read_latest(_, group):
                self.service.stop_event.set()
                raise RuntimeError("Source mismatch")
        self.service.source = Source()
        self.service._run()
        self.assertEqual(self.service.status()["error"], "Source mismatch")
        self.assertIsNotNone(self.service.status()["last_poll"])
        self.assertEqual(self.service.status()["queue"], [])

    def test_read_unknown_or_not_latest_messages_never_reach_parser(self):
        def forbidden(_): raise AssertionError("read message reached parser")
        self.service.preview=forbidden
        for change in [{"is_unread":False},{"is_unread":None},{"unread_verified":False},{"is_latest_unread":False}]:
            self.assertEqual(self.service.ingest({**self.message,**change}),"UNVERIFIED_UNREAD")
        self.assertEqual(self.service.status()["queue"],[])

    def test_failed_processing_is_not_retried_even_after_restart(self):
        def fail(): raise RuntimeError("broker unavailable")
        self.service.reconcile=fail
        self.assertEqual(self.service.ingest(self.message),"RECONCILIATION_UNAVAILABLE")
        restarted=self.make()
        self.assertEqual(restarted.ingest(self.message),"DUPLICATE")

    def test_multiple_source_messages_are_rejected(self):
        class Source:
            def read_latest(_,group):
                self.service.stop_event.set()
                return [self.message,{**self.message,"id":"two"}]
        self.service.source=Source()
        self.service._run()
        self.assertIn("only the latest unread",self.service.error)
        self.assertEqual(self.service.status()["queue"],[])
