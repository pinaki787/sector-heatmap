import json,tempfile,unittest
from pathlib import Path
from strategies.nifty_ai_options.trade_journal import sync_account,report,recorded_fill
class JournalTest(unittest.TestCase):
 def test_fill_and_account_mode_isolation(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);owner='a'*32;other='b'*32
   for mode,n in [('PAPER',1),('LIVE',2)]:
    d=base/'runs'/owner/str(n);d.mkdir(parents=True)
    (d/'config.json').write_text(json.dumps(dict(account=owner,broker='FYERS',execution_mode=mode,underlying='NSE:NIFTY50-INDEX')))
    records=[dict(action=dict(action='BUY',timestamp=10,position=dict(symbol='NSE:TESTCE',quantity=65)),result=dict(fill_price=20,filled_quantity=65,filled_at=11,order_id='entry'+mode,total_costs=2)),dict(action=dict(action='SELL',timestamp=20,position=dict(symbol='NSE:TESTCE',quantity=65,fill_price=20)),result=dict(fill_price=22,filled_quantity=65,filled_at=21,order_id='exit'+mode,total_costs=3))]
    (d/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
   sync_account(owner,base);sync_account(owner,base)
   r=report(owner,'1',base);self.assertEqual(r['total'],2)
   self.assertEqual(r['current_run']['net_profit'],125)
   self.assertEqual(len(report(owner,data=base,mode='PAPER')['rows']),1)
   self.assertEqual(report(other,data=base)['total'],0)
   # File replacement/replay remains idempotent.
   p=base/'runs'/owner/'1'/'events.jsonl';text=p.read_text();p.unlink();p.write_text(text)
   sync_account(owner,base);self.assertEqual(report(owner,data=base)['total'],2)
 def test_unknown_cost_and_open_exit(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);o='a'*32;d=base/'runs'/o/'r';d.mkdir(parents=True)
   (d/'config.json').write_text(json.dumps(dict(account=o,broker='FYERS',execution_mode='PAPER')))
   r=dict(action=dict(action='BUY',timestamp=1,position=dict(symbol='MCX:TEST',qtyMultiplier=10)),result=dict(simulated_fill=200,filled_quantity=1,dry_run=True))
   (d/'events.jsonl').write_text(json.dumps(r)+'\n'+json.dumps(dict(event=dict(kind='price',symbol='MCX:TEST',close=205,timestamp=2)))+'\n')
   sync_account(o,base);row=report(o,'r',base)['rows'][0]
   self.assertIsNone(row['exit_premium']);self.assertIsNone(row['net_profit']);self.assertEqual(row['unrealized_gross'],50)
 def test_pending_not_fill(self):
  self.assertIsNone(recorded_fill({},dict(deferred=True,fill_price=10,filled_quantity=1)))
if __name__=='__main__':unittest.main()

class PartialJournalTests(unittest.TestCase):
 def test_partial_exit_splits_only_confirmed_quantity_and_preserves_remaining_cost(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);owner='a'*32;d=base/'runs'/owner/'run';d.mkdir(parents=True)
   (d/'config.json').write_text(json.dumps(dict(account=owner,broker='MOTILAL_OSWAL',execution_mode='PAPER',underlying='BSE:SENSEX-INDEX')))
   p=dict(symbol='MO:BSEFO:123',side='CE',quantity=10,fill_price=20)
   records=[dict(action=dict(action='BUY',timestamp=10,position=p),result=dict(fill_price=20,filled_quantity=10,filled_at=11,order_id='entry',total_costs=2)),dict(action=dict(action='SELL',timestamp=20,position=p),result=dict(fill_price=22,filled_quantity=5,filled_at=21,order_id='partial',total_costs=2))]
   events=d/'events.jsonl';events.write_text(''.join(json.dumps(r)+'\n' for r in records))
   sync_account(owner,base);sync_account(owner,base)
   rows=report(owner,'run',base)['rows']
   opened=[r for r in rows if r['status']=='OPEN'];closed=[r for r in rows if r['status']=='CLOSED']
   self.assertEqual(len(opened),1);self.assertEqual(opened[0]['quantity'],5);self.assertEqual(opened[0]['entry_cost'],1)
   self.assertEqual(closed[0]['quantity'],5);self.assertEqual(closed[0]['gross_profit'],10);self.assertEqual(closed[0]['net_profit'],7);self.assertEqual(closed[0]['currency'],'INR')
   with events.open('a') as out:out.write(json.dumps(dict(action=dict(action='SELL',timestamp=30,position=p),result=dict(fill_price=21,filled_quantity=5,filled_at=31,order_id='remaining',total_costs=2)))+'\n')
   sync_account(owner,base);r=report(owner,'run',base)
   self.assertEqual(r['current_run']['open_trades'],0);self.assertEqual(r['current_run']['net_profit'],9)
