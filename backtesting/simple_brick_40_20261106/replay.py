"""Offline causal sampled-price replay of production Simple Brick rules."""
from pathlib import Path
import sys,json,csv,math,datetime,collections,time,hashlib
from zoneinfo import ZoneInfo
ROOT=Path('/home/trading/sector-heatmap');OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from strategies.renko_supertrend import session_auto,manual_brick,price_basis,loss_range
from strategies.renko_supertrend.signals import Engine
from strategies.renko_supertrend.entry_qualification import check
from strategies.renko_supertrend.costs import fee
IST=ZoneInfo('Asia/Kolkata');LOT=65;CAPITAL=100000.;SLIP=.05
def day(ts):return datetime.datetime.fromtimestamp(ts,IST).date().isoformat()
def clock(ts):return datetime.datetime.fromtimestamp(ts,IST).isoformat()
def minute(ts):
 t=datetime.datetime.fromtimestamp(ts,IST);return t.hour*60+t.minute
def load_underlying():
 source=ROOT/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.csv';rows={}
 with source.open() as f:
  for r in csv.DictReader(f):
   if r['timestamp_ist'][:10]<'2026-09-01':continue
   t=int(r['epoch']);rows[t]=dict(timestamp=t,**{k:float(r[k]) for k in ('open','high','low','close','volume')})
 conflicts=[]
 for a in json.loads((OUT/'recent_1m.json').read_text())['response']['candles']:
  r=dict(zip(('timestamp','open','high','low','close','volume'),a[:6]));t=int(r['timestamp'])
  if t in rows and rows[t]!=r:conflicts.append(t)
  rows[t]=r
 if conflicts:raise ValueError('Conflicting underlying rows: '+str(len(conflicts)))
 rows=sorted((r for r in rows.values() if 555<=minute(r['timestamp'])<930),key=lambda r:r['timestamp'])
 byday=collections.defaultdict(list)
 for r in rows:byday[day(r['timestamp'])].append(r)
 incomplete={d:len(rs) for d,rs in byday.items() if len(rs)!=375 or any(r['timestamp']!=rs[0]['timestamp']+i*60 for i,r in enumerate(rs))}
 days=sorted(d for d in byday if d not in incomplete)[-30:]
 return rows,days,incomplete
def load_options(first,last):
 directories=[ROOT/'backtesting/nifty_renko_30sessions_20261019/options',OUT/'options']
 quotes={};conflicts=set();invalid=0;files=[]
 for directory in directories:
  for path in sorted(directory.glob('*.json')):
   obj=json.loads(path.read_text());req=obj.get('request') or {};data=obj.get('data')
   if not isinstance(data,dict) or req.get('interval')!='1':continue
   side=req['drvOptionType'];fields=('open','high','low','close','volume','strike')
   if any(len(data.get(k,[]))!=len(data.get('timestamp',[])) for k in fields):raise ValueError('Option array mismatch')
   files.append({'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
   for i,t in enumerate(data['timestamp']):
    if not first<=day(t)<=last or not 555<=minute(t)<930:continue
    q=tuple(data[k][i] for k in fields)
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in q) or min(q[:4])<=0 or q[5]<=0 or not q[2]<=min(q[0],q[3])<=max(q[0],q[3])<=q[1]:invalid+=1;continue
    key=(int(t),side,float(q[5]))
    if key in quotes and any(abs(a-b)>.051 for a,b in zip(quotes[key][:4],q[:4])):conflicts.add(key)
    else:quotes.setdefault(key,q)
 for k in conflicts:quotes.pop(k,None)
 # Exact fixed-contract supplemental history overrides that contract's rolling bars.
 for path in sorted((OUT/'fyers-options').glob('hist-*.json')):
  obj=json.loads(path.read_text());meta=obj.get('request') or {};symbol=meta.get('symbol','')
  import re
  match=re.search(r'(\d{5})(CE|PE)$',symbol)
  if not match:continue
  strike=float(match.group(1));side='CALL' if match.group(2)=='CE' else 'PUT'
  for row in obj.get('response',{}).get('candles',[]):
   t=int(row[0])
   if not first<=day(t)<=last or not 555<=minute(t)<930:continue
   q=tuple(row[1:6])+ (strike,)
   if len(q)==6 and min(q[:4])>0:quotes[(t,side,strike)]=q
 surface=collections.defaultdict(list)
 for (t,side,strike),q in quotes.items():
  if q[4]>0:surface[(t,side)].append((strike,q))
 return quotes,surface,dict(files=files,unique_quotes=len(quotes),conflicts=len(conflicts),invalid=invalid)
def refs(days):
 native=json.loads((OUT/'daily.json').read_text())['response']['candles']
 policy={'master_regular_session':'0915-1530','session_source':'FYERS master regular session'};spec=session_auto.session_spec('NSE:NIFTY50-INDEX','FYERS',policy)
 manual_spec=manual_brick.rule('NSE:NIFTY50-INDEX',policy,atr_length=5)
 bars=[]
 for r in native:
  dt=datetime.datetime.fromtimestamp(r[0],datetime.timezone.utc).date()
  opening=datetime.datetime.combine(dt,datetime.time(9,15),IST).timestamp()
  bars.append(dict(timestamp=opening,completed_at=opening+22500,open=r[1],high=r[2],low=r[3],close=r[4]))
 unique={r['timestamp']:r for r in bars};bars=sorted(unique.values(),key=lambda r:r['timestamp']);result={}
 for d in days:
  start=datetime.datetime.combine(datetime.date.fromisoformat(d),datetime.time(9,15),IST).timestamp()
  ref=session_auto.reference([r for r in bars if r['completed_at']<=start],length=5,factor=3,available_at=start,input_basis='COMPLETED_FULL_SESSION_OHLC')
  ref.update(spec,session_start=start,session_end=start+22500)
  scaled=session_auto.scale(ref,300,spec,.05)
  man=manual_brick.calculate_sessions(native,manual_spec,start)
  result[d]={'auto':scaled['box'],'manual':man['manual_brick'],'reference_atr':ref['reference_atr'],'reference_available_at':ref['available_at']}
 return result
def simulate(mode,rows,days,sizing,quotes,surface):
 cfg=dict(strategy_mode='SIMPLE_BRICK',strategy_basis='RENKO',brick_mode='Manual',timeframe='5 minutes',swing_breakout_enabled=False,session_deadline='15:10',renko_loss_range_enabled=True,renko_loss_range_buffer=0,underlying='NSE:NIFTY50-INDEX',ema_exit_enabled=False,supertrend_exit_enabled=False,renko_brick_exit_enabled=True)
 trades=[];curve=[];audit=[];locks=[];realized=0.;lock=None;p=None;missing_marks=0;current=None;export=None;used=0;last_exit=-1
 def finish(at,sig,why):
  nonlocal p,realized,lock,last_exit
  q=quotes.get((at,p['side'],p['strike']))
  if q is None:
   audit.append(dict(type='MISSING_EXIT_PRICE',at=at,side=p['side'],strike=p['strike']));return False
  sell=max(.05,q[0]-SLIP);exitfee=fee(sell*LOT,'SELL',exchange_rate=.000355299)['total'];gross=(sell-p['buy'])*LOT;net=gross-p['entry_fee']-exitfee
  trade={**p,'exit_at':at,'exit_time':clock(at),'exit_premium':sell,'exit_raw_open':q[0],'gross':gross,'fees':p['entry_fee']+exitfee,'net':net,'reason':why}
  trade.pop('renko_brick_range',None);trades.append(trade);realized+=net
  frozen=loss_range.freeze(p,sig,cfg,net,at,300,'research',str(len(trades)))
  if frozen:lock=frozen;locks.append({'event':'LOCK','at':at,**frozen})
  p=None;last_exit=at;return True
 selected=[r for r in rows if day(r['timestamp']) in days]
 for index,r in enumerate(selected):
  if (OUT/'STOP').exists():raise InterruptedError('Research stopped by operator')
  at=r['timestamp']+60;d=day(r['timestamp'])
  if d!=current:
   if p:raise ValueError('Unclosed prior session')
   current=d;used=0;box=sizing[d][mode];cfg['manual_brick']=box
   # Daily rearm: no overnight gap path or pre-Start brick replay.
   export={'state':{'brick_box':box},'last':{'box':box},'rows':[]};cfg.update(_run_id=d,_stream_session=d)
   price_basis.observe(export,cfg,.05,dict(ltp=r['open'],exch_feed_time=r['timestamp']),r['timestamp'],1)
  events=price_basis.observe(export,cfg,.05,dict(ltp=r['close'],exch_feed_time=at),at,1)
  exited=False
  for sig in events:
   if p:
    loss_range.observe(p,sig,cfg,at,300)
    if sig['brick_direction']!=p['direction']:
     if not finish(at,sig,'FIRST_COMPLETED_OPPOSITE_BRICK'):
      return {'mode':mode,'status':'INCOMPLETE','trades':trades,'curve':curve,'audit':audit,'locks':locks}
     exited=True
   if lock and loss_range.breakout(lock,sig,sig['brick_direction'],at,300):
    locks.append({'event':'RELEASE','at':at,'high':lock['high'],'low':lock['low']});lock=None
   if p or exited or at<=last_exit or minute(at)>=910 or used>=5 or lock:continue
   direction=sig['brick_direction']
   if not check(cfg,sig,direction)['allowed']:continue
   side='CALL' if direction=='BULLISH' else 'PUT';candidates=surface.get((at-60,side),[])
   if not candidates:audit.append({'type':'MISSING_ENTRY_SURFACE','at':at,'side':side});continue
   strike,q=min(candidates,key=lambda item:(abs(item[1][3]-40),item[0]))
   fill=quotes.get((at,side,strike))
   if fill is None:audit.append({'type':'MISSING_SELECTED_ENTRY','at':at,'side':side,'strike':strike});continue
   bracket=min(x[1][3] for x in candidates)<=40<=max(x[1][3] for x in candidates)
   if not bracket:audit.append({'type':'TARGET_OUTSIDE_AVAILABLE_SURFACE','at':at,'side':side,'selected_close':q[3],'candidate_count':len(candidates)})
   buy=fill[0]+SLIP;entryfee=fee(buy*LOT,'BUY',exchange_rate=.000355299)['total']
   if buy*LOT+entryfee>CAPITAL+realized:audit.append({'type':'CAPITAL_LIMIT','at':at});continue
   p=dict(entry_at=at,entry_time=clock(at),side=side,strike=strike,direction=direction,buy=buy,entry_raw_open=fill[0],entry_fee=entryfee,selection_prior_close=q[3],selection_error=abs(q[3]-40),candidate_count=len(candidates),target_bracketed=bracket,quantity=LOT,box=box,day=d,opened_at=at)
   loss_range.observe(p,sig,cfg,at,300,seed=True);used+=1
  if p and minute(at)>=910:
   sig=events[-1] if events else {'timestamp':at,'has_completed_brick':False}
   if not finish(at,sig,'SESSION_CUTOFF'):return {'mode':mode,'status':'INCOMPLETE','trades':trades,'curve':curve,'audit':audit,'locks':locks}
  mark=realized
  if p:
   q=quotes.get((at,p['side'],p['strike']))
   if q is None:
    missing_marks+=1;audit.append({'type':'MISSING_MARK','at':at,'side':p['side'],'strike':p['strike']})
   else:
    sell=max(.05,q[0]-SLIP);mark+=(sell-p['buy'])*LOT-p['entry_fee']-fee(sell*LOT,'SELL',exchange_rate=.000355299)['total']
  curve.append({'at':at,'equity':CAPITAL+mark,'realized':realized,'mark_available':not p or q is not None})
 if p:audit.append({'type':'OPEN_FINAL_POSITION'})
 values=[t['net'] for t in trades];wins=[v for v in values if v>0];losses=[-v for v in values if v<0];peak=CAPITAL;dd=0.;ddpercent=0.
 for mark in curve:
  if not mark['mark_available']:continue
  peak=max(peak,mark['equity']);dd=max(dd,peak-mark['equity']);ddpercent=max(ddpercent,100*(peak-mark['equity'])/peak)
 metrics=dict(trades=len(trades),calls=sum(t['side']=='CALL' for t in trades),puts=sum(t['side']=='PUT' for t in trades),gross=sum(t['gross'] for t in trades),fees=sum(t['fees'] for t in trades),net=sum(values),return_percent=100*sum(values)/CAPITAL,win_rate=100*len(wins)/len(values) if values else None,profit_factor=sum(wins)/sum(losses) if losses else None,max_drawdown=dd,max_drawdown_percent=ddpercent,average_trade=sum(values)/len(values) if values else None,best_trade=max(values,default=None),worst_trade=min(values,default=None),selection_error_average=sum(t['selection_error'] for t in trades)/len(trades) if trades else None,entry_raw_premium_min=min((t['entry_raw_open'] for t in trades),default=None),entry_raw_premium_max=max((t['entry_raw_open'] for t in trades),default=None),missing_marks=missing_marks)
 return dict(mode=mode,status='COMPLETE' if not p and not any(a['type'].startswith('MISSING_') or a['type']=='TARGET_OUTSIDE_AVAILABLE_SURFACE' for a in audit) else 'LIMITED',metrics=metrics,trades=trades,curve=curve,audit=audit,locks=locks)
def main():
 rows,days,incomplete=load_underlying();sizing=refs(days);quotes,surface,coverage=load_options(days[0],days[-1])
 results=[]
 for mode in ('auto','manual'):
  print('Replay',mode,'quotes',len(quotes),flush=True);result=simulate(mode,rows,days,sizing,quotes,surface);results.append(result)
  (OUT/(mode+'.json')).write_text(json.dumps(result,indent=2))
  if result['trades']:
   with (OUT/(mode+'-trades.csv')).open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(result['trades'][0]));writer.writeheader();writer.writerows(result['trades'])
  print(mode,result.get('metrics'),flush=True)
 benchmark=[r for r in rows if day(r['timestamp']) in days];benchmark_return=100*(benchmark[-1]['close']/benchmark[0]['open']-1)
 report=dict(benchmark={'name':'NIFTY 50 underlying buy and hold, no fees','return_percent':benchmark_return},sessions=days,incomplete_underlying=incomplete,sizing=sizing,coverage=coverage,results=[{k:v for k,v in r.items() if k not in ('trades','curve','locks')} for r in results],assumptions={'capital':CAPITAL,'lot':LOT,'max_trades_per_session':5,'target_premium':40,'selection':'Closest prior completed one-minute option CLOSE across returned nearest-week strikes; next minute OPEN fill. No historical ask data. Strike fixed until exit.','slippage_points_per_side':SLIP,'session':'09:15-15:10 IST','sizing':'Recalculated before each session from prior completed native FYERS full-session OHLC, ATR5. Auto: ATR*3*5/375; Manual: rounded ATR/(375/30).','confirmation':'Production price_basis.observe and final qualification on ordered one-minute close samples; intraminute tick path unavailable. Daily first price baseline.','locks':'Production loss_range.observe/freeze/breakout, zero buffer, carried across sessions; same observed exit timestamp blocks reversal.','expiry':'Dhan nearest WEEK series expiryCode1; intraday fixed strike; absolute historical expiry inferred/not broker certified.','drawdown':'Net equity marked at each minute boundary using held fixed-strike option OPEN; missing marks disclosed, not zero-filled. Intraminute extremes unavailable.','fees':'Existing FYERS options fee estimator; not broker-billed costs.','limits':'30 most recent complete underlying sessions; incomplete history never substituted. Candidate coverage limited to provider ATM±10. No signals inferred from intrabar high/low.'})
 (OUT/'results.json').write_text(json.dumps(report,indent=2))
 print('Saved results',flush=True)
if __name__=='__main__':main()
