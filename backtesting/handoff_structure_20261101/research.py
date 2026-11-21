"""Fixed-design causal swing test; research only."""
import json,hashlib
from pathlib import Path
import requests,pandas as pd,numpy as np
from sector_heatmap.analysis import calculate_timeframe_state
P=Path(__file__).resolve().parent
SYMS="RELIANCE TCS INFY HDFCBANK ICICIBANK SBIN ITC HINDUNILVR LT MARUTI SUNPHARMA TATASTEEL".split()
def load(s):
 p=P/(s+'.json')
 if not p.exists():
  r=requests.get('https://query1.finance.yahoo.com/v8/finance/chart/'+s+'.NS',params={'range':'10y','interval':'1d'},headers={'User-Agent':'Mozilla/5.0'},timeout=45);r.raise_for_status();p.write_text(r.text)
 j=json.loads(p.read_text())['chart']['result'][0]
 ix=pd.to_datetime(j['timestamp'],unit='s',utc=True).tz_convert('Asia/Kolkata')
 d=pd.DataFrame(j['indicators']['quote'][0],index=ix)
 f=pd.Series(j['indicators']['adjclose'][0]['adjclose'],index=ix)/d.close
 d[['open','high','low','close']]=d[['open','high','low','close']].mul(f,axis=0)
 return d.dropna(subset=['open','high','low','close']).loc[lambda x:x.index.date<pd.Timestamp('2026-11-01').date()]
def candles(d):
 return [dict(timestamp=int(t.timestamp()),**{k:float(v) for k,v in r.items()}) for t,r in d.iterrows()]
def structures(d):
 hs=[];ls=[];out=[];bb=False;sb=False
 for i in range(len(d)):
  k=i-2
  if k>=2:
   h=d.high.iloc[k];l=d.low.iloc[k]
   if all(h>d.high.iloc[x] for x in range(k-2,k+3) if x!=k):hs.append((k,h));sb=False
   if all(l<d.low.iloc[x] for x in range(k-2,k+3) if x!=k):ls.append((k,l));bb=False
  if ls and d.low.iloc[i]<ls[-1][1]:bb=True
  if hs and d.high.iloc[i]>hs[-1][1]:sb=True
  if len(hs)<2 or len(ls)<2:out.append('unconfirmed');continue
  bull=hs[-1][1]>hs[-2][1] and ls[-1][1]>ls[-2][1] and not bb
  bear=hs[-1][1]<hs[-2][1] and ls[-1][1]<ls[-2][1] and not sb
  out.append('bull' if bull else 'bear' if bear else 'mixed_or_broken')
 return out
rows=[];manifest=[]
for sym in SYMS:
 d=load(sym);dc=candles(d);st=structures(d)
 w=d.resample('W-FRI').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna();wc=candles(w);wd=w.index.normalize();ws={}
 for i,t in enumerate(w.index):
  if i>=209:ws[i]=calculate_timeframe_state('weekly',wc[:i+1],[])['state']
 eligible=[i for i,t in enumerate(d.index) if t.year>=2021 and i+5<len(d)]
 for i in eligible[::5]:
  t=d.index[i];wi=wd.searchsorted(t.normalize(),side='right')-1
  if wi<209:continue
  ds=calculate_timeframe_state('daily',dc[:i+1],[])['state'];ww=ws[wi]
  side=1 if ds is not None and ds>=1 and ww>=1 else -1 if ds is not None and ds<=-1 and ww<=-1 else 0
  if not side:continue
  entry=d.open.iloc[i+1];exit=d.close.iloc[i+5];future=d.iloc[i+1:i+6]
  ret=side*(exit/entry-1)*100
  mae=((future.low.min()/entry-1) if side==1 else (1-future.high.max()/entry))*100
  rows.append(dict(symbol=sym,date=str(t.date()),split='development' if t.year<2024 else 'heldout',side=side,structure=st[i],ret_pct=ret,mae_pct=min(0,mae),confirmed=st[i]==('bull' if side==1 else 'bear')))
 manifest.append(dict(symbol=sym,rows=len(d),start=str(d.index[0]),end=str(d.index[-1]),sha256=hashlib.sha256((P/(sym+'.json')).read_bytes()).hexdigest()))
 print(sym,len(rows),flush=True)
r=pd.DataFrame(rows);r.to_csv(P/'observations.csv',index=False);out=[]
for split in ['development','heldout']:
 for side in [0,1,-1]:
  base=r[(r.split==split)&((r.side==side) if side else True)]
  for name,x in [('baseline',base),('confirmed',base[base.confirmed]),('other',base[~base.confirmed])]:
   out.append(dict(split=split,side=side,group=name,n=len(x),retention_pct=100*len(x)/len(base) if len(base) else None,mean_pct=x.ret_pct.mean(),median_pct=x.ret_pct.median(),hit_pct=100*(x.ret_pct>0).mean(),mean_mae_pct=x.mae_pct.mean(),worst_mae_pct=x.mae_pct.min()))
pd.DataFrame(out).to_csv(P/'summary.csv',index=False)
(P/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(pd.DataFrame(out).round(3).to_string(index=False))
