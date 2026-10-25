import json,tempfile,unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from sector_heatmap.telegram_trade_format import parts,units
from sector_heatmap.trade_notifications import Outbox,send

def event():
 return dict(id="synthetic-reference",kind="POSITION_SUMMARY",mode="LIVE",broker="FYERS",
  strategy="Account positions",time=1792557000,daily_pnl=93.7500000000004,
  positions=[dict(symbol="NSE:EXAMPLE-EQ",netQty=10.0,price=125.5,pnl=93.7500000000004)])

class Markup(HTMLParser):
 def __init__(self):super().__init__();self.stack=[];self.text=""
 def handle_starttag(self,tag,attrs):
  assert tag in {"b","i"} and not attrs
  self.stack.append(tag)
 def handle_endtag(self,tag):assert self.stack.pop()==tag
 def handle_data(self,data):self.text+=data

class Format(unittest.TestCase):
 def test_readable_numbers_time_and_safe_html(self):
  e=event();e["positions"][0]["symbol"]="<BAD>&CO"
  body=parts(e)[0];parser=Markup();parser.feed(body)
  self.assertEqual(parser.stack,[])
  self.assertIn("<BAD>&CO",parser.text)
  self.assertIn("Qty 10",parser.text)
  self.assertIn("+₹93.75",parser.text)
  self.assertNotIn("000000000004",body)
  self.assertIn("IST",body)
 def test_long_unicode_message_preserves_every_position_and_fits_telegram(self):
  e=event();e["positions"]=[dict(symbol="😀&<TEST-"+str(i)+">",netQty=1,pnl=i) for i in range(100)]
  fragments=parts(e);self.assertGreater(len(fragments),1)
  visible=""
  for fragment in fragments:
   self.assertLessEqual(units(fragment),4096)
   parser=Markup();parser.feed(fragment);self.assertEqual(parser.stack,[]);visible+=parser.text
  for i in range(100):self.assertIn("TEST-"+str(i)+">",visible)
 def test_trade_exit_keeps_execution_and_before_fee_pnl_information(self):
  e=event();e.pop("kind");e.update(action="EXIT",symbol="NSE:EXAMPLE-EQ",side="SELL",
   quantity=4,cumulative_quantity=10,price=101.25,cumulative_average=100.75,
   realized_pnl=-1234.567,reason="Stop <confirmed>",currency="INR")
  body=parts(e)[0]
  for text in ("-₹1,234.57","Filled · this update","Cumulative average","Stop &lt;confirmed&gt;","before fees"):
   self.assertIn(text,body)
 def test_transport_uses_html_and_never_truncates_a_validated_part(self):
  captured=[]
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return b'{"ok":true}'
  def open_request(request,**kwargs):captured.append(json.loads(request.data));return Response()
  with patch("sector_heatmap.trade_notifications.urllib.request.urlopen",open_request):
   self.assertEqual(send("telegram",dict(telegram=dict(chat_id=-1,token="synthetic")),event()),("SENT",None))
  self.assertEqual(captured[0]["parse_mode"],"HTML")
  self.assertIn("<b>",captured[0]["text"])
 def test_retry_sends_only_unsent_parts_and_destination_change_is_not_replayed(self):
  e=event();e["positions"]=[dict(symbol="TEST-"+str(i),netQty=1,pnl=i) for i in range(200)]
  with tempfile.TemporaryDirectory() as folder:
   box=Outbox(Path(folder)/"outbox.sqlite3",clock=lambda:100)
   config=dict(telegram=dict(chat_id=-1));sent=[];fail=[True]
   def sender(channel,config,row):
    body=row["_telegram_html"];sent.append(body)
    if len(sent)==2 and fail[0]:return "RETRY","temporary"
    return "SENT",None
   self.assertEqual(box.deliver_telegram(config,e,sender)[0],"RETRY")
   first=sent[0];fail[0]=False
   self.assertEqual(box.deliver_telegram(config,e,sender)[0],"SENT")
   self.assertEqual(sent.count(first),1)
   before=len(sent)
   self.assertEqual(box.deliver_telegram(dict(telegram=dict(chat_id=-2)),e,sender)[0],"REVIEW")
   self.assertEqual(len(sent),before);box.db.close()
 def test_uncertain_part_is_never_automatically_replayed(self):
  with tempfile.TemporaryDirectory() as folder:
   box=Outbox(Path(folder)/"outbox.sqlite3",clock=lambda:100);calls=[]
   def sender(*args):calls.append(1);return "REVIEW","unknown"
   config=dict(telegram=dict(chat_id=-1))
   self.assertEqual(box.deliver_telegram(config,event(),sender)[0],"REVIEW")
   self.assertEqual(box.deliver_telegram(config,event(),sender)[0],"REVIEW")
   self.assertEqual(len(calls),1);box.db.close()

class MarketCardTransportTests(unittest.TestCase):
 def test_retained_image_is_sent_once_without_private_trade_reformatting(self):
  from unittest.mock import Mock,patch
  from sector_heatmap.trade_notifications import Outbox
  box=object.__new__(Outbox);sender=Mock(return_value=("SENT",None));config={"telegram":{"chat_id":-1}}
  for kind in ["SECTOR_CARD","HANDOFF_CARD"]:
   event={"id":"synthetic-"+kind,"kind":kind,"image":"synthetic.png"}
   with patch("sector_heatmap.telegram_trade_format.parts",side_effect=AssertionError("private formatter must not see market images")):
    self.assertEqual(box.deliver_telegram(config,event,sender),("SENT",None))
   self.assertEqual(sender.call_args.args,("telegram",config,event))
  self.assertEqual(sender.call_count,2)
