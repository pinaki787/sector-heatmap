import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from sector_heatmap.telegram_paper import PaperPipeline
from tests.test_telegram_option_tickets import TicketTests

class PaperPipelineTests(TicketTests):
 def setUp(self):
  super().setUp();template=self.t.template;self.t.template=lambda:dict(template(),supertrend_exit_enabled=True,ema_exit_length=10);self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.poll=Mock();self.poll.route='SUBSCRIBER';self.poll.lock=__import__('threading').RLock();self.poll.data={'queue':[]};self.poll.running.return_value=True;self.poll.verified={'channel_id':1}
  self.feed=Mock();self.feed.tick.return_value={'ltp':101,'exch_feed_time':1000}
  self.pipe=PaperPipeline(self.t,self.poll,Path(self.tmp.name)/'pipeline.json',clock=lambda:1000,feed=self.feed)
  with patch('threading.Thread'):self.pipe.start(dict(mode='PAPER',quantity=1000))
 def row(self,id='1',text='ETHUSD BUY ABOVE 100',**kw):
  self.poll.data['queue'].append(dict(id=id,revision=text,text=text,timestamp=1000,state='REVIEW',edited_at=None,**kw))
 def test_new_trigger_enters_paper_1000_once_and_restart_no_replay(self):
  self.row();self.pipe.step();self.pipe.step();self.runner.telegram_entry.assert_called_once();args=self.runner.telegram_entry.call_args.args[0];self.assertEqual(args['mode'],'PAPER');self.assertEqual(args['lots'],1000);self.assertIsNone(args['telegram_trigger'])
  restored=PaperPipeline(self.t,self.poll,self.pipe.path,clock=lambda:1000,feed=self.feed);self.assertFalse(restored.running)
  with patch('threading.Thread'):restored.start(dict(mode='PAPER',quantity=1000))
  restored.step();self.runner.telegram_entry.assert_called_once()
 def test_immediate_paper_does_not_wait_for_underlying_condition(self):
  self.row();self.feed.tick.return_value={'ltp':99,'exch_feed_time':980};self.pipe.step();self.runner.telegram_entry.assert_called_once()
 def test_gold_missed_edits_and_duplicate_do_not_submit(self):
  self.row('gold','Good morning');self.row('missed',missed_review=True);self.row('edited');self.poll.data['queue'][-1]['edited_at']=1000;self.pipe.step();self.runner.telegram_entry.assert_not_called();self.assertEqual(self.pipe.records['gold']['status'],'IGNORED_CHATTER')
  self.row('valid');self.row('duplicate');self.pipe.step();self.runner.telegram_entry.assert_called_once();self.assertEqual(self.pipe.records['duplicate']['status'],'DUPLICATE_SKIPPED')
 def test_baseline_and_live_start_denied(self):
  self.row();self.pipe.stop()
  with self.assertRaises(ValueError):self.pipe.start(dict(mode='LIVE',quantity=1000))
  with patch('threading.Thread'):self.pipe.start(dict(mode='PAPER',quantity=1000))
  self.pipe.step();self.runner.telegram_entry.assert_not_called()
 def test_edit_before_processing_is_ignored(self):
  self.row();self.poll.data['queue'][0]['edited_at']=1000;self.pipe.step();self.runner.telegram_entry.assert_not_called()
