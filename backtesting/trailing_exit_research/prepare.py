"""Freeze baseline one-minute entry opportunities for paired exit research."""
import json,hashlib,csv
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from source_snapshot.signals import Engine
OUT=Path(__file__).resolve().parent; IST=ZoneInfo('Asia/Kolkata')
def day(t):return str(datetime.fromtimestamp(t,IST).date())
def prepare():
 raw=json.loads((OUT/'underlying.json').read_text())['response']['candles']
 cfg=json.loads((OUT/'config.json').read_text());engine=Engine(cfg,1)
 rows=[];invalid=[]
 for c in sorted(raw):
  try:r=engine.update(dict(zip(('timestamp','open','high','low','close','volume'),c)));rows.append(r)
  except ValueError:invalid.append(c[0])
 trades=[];p=None;pending=None;rearm=False;counts={};lock=None;skips=0
 for i,r in enumerate(rows):
  t=r['timestamp'];d=day(t);dt=datetime.fromtimestamp(t,IST);minutes=dt.hour*60+dt.minute
  if pending:
   kind,at,sign=pending;pending=None
   if kind=='entry' and t==at and minutes<1410:
    p=dict(i=i,at=t,sign=sign,price=r['open'],high=r['open'],low=r['open'])
    counts[d]=counts.get(d,0)+1
   elif kind=='exit' and p:
    p.update(end_i=i,end_at=t,exit_price=r['open']);trades.append(p);rearm=True
    if cfg.get('sideways_enabled') and p['sign']*(r['open']-p['price'])<0 and int(t//60-p['at']//60)+1<=cfg.get('sideways_max_candles',3):lock=(p['high'],p['low'])
    p=None;continue
  if lock and (r['close']>lock[0] or r['close']<lock[1]):lock=None;rearm=True
  if p:
   if minutes>=1409 or d!=day(p['at']):
    p.update(end_i=i,end_at=t,exit_price=r['open']);trades.append(p);p=None;rearm=True;continue
   p['high']=max(p['high'],r['high']);p['low']=min(p['low'],r['low'])
   adverse=r['close']<r['ema10'] if p['sign']==1 else r['close']>r['ema10']
   if adverse or r['cross_direction']==('BEARISH' if p['sign']==1 else 'BULLISH'):pending=('exit',t+60,None)
  elif i>500 and minutes<1409:
   direction=r['entry_direction'] or (r['direction'] if rearm and r['entry_qualified'] else None)
   if direction and not lock:pending=('entry',t+60,1 if direction=='BULLISH' else -1);rearm=False
   elif direction and lock:skips+=1
 (OUT/'analyzed.json').write_text(json.dumps(rows));(OUT/'entries.json').write_text(json.dumps(trades,indent=2))
 (OUT/'prepare_summary.json').write_text(json.dumps(dict(raw=len(raw),valid=len(rows),invalid=invalid,days=len({day(r['timestamp']) for r in rows}),first=day(rows[0]['timestamp']),last=day(rows[-1]['timestamp']),trades=len(trades),skipped_lock=skips,open_trade=p,semantics='Completed-close baseline proxy; next contiguous open entries; no invented daily quota (runtime quota is per armed run);  quick-loss lock uses gross underlying loss, not option after-cost loss. Entries frozen across arms.'),indent=2))
 print('candles',len(rows),'invalid',len(invalid),'trades',len(trades),'days',len(counts))
if __name__=='__main__':prepare()
