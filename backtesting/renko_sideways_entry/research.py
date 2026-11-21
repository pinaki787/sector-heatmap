"""Research only. Never imported by runtime; no broker or order clients."""
import csv,hashlib,json,math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from strategies.renko_supertrend.signals import Engine
from strategies.renko_supertrend.exit_indicators import reason
ROOT=Path(__file__).resolve().parent
IST=ZoneInfo('Asia/Kolkata')
BASE=Path('.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/source/.private')
def features(rows,cfg):
    engine=Engine(cfg,0.05);result=[];trs=[];directions=[];exit_ema=None
    for i,r in enumerate(rows):
        s=engine.update(r)
        tr=max(r['high']-r['low'],abs(r['high']-rows[i-1]['close']),abs(r['low']-rows[i-1]['close'])) if i else r['high']-r['low']
        trs.append(tr);directions.append(s['pine_direction'])
        span=rows[max(0,i-13):i+1];rng=max(x['high'] for x in span)-min(x['low'] for x in span)
        chop=100*math.log10(sum(trs[i-13:i+1])/rng)/math.log10(14) if i>=13 and rng>0 else None
        start=max(0,i-13);travel=sum(abs(rows[j]['close']-rows[j-1]['close']) for j in range(start+1,i+1))
        er=abs(r['close']-rows[start]['close'])/travel if i>=13 and travel else None
        flips=sum(directions[j]!=directions[j-1] for j in range(max(1,i-7),i+1))
        alpha=2/(cfg.get('ema_exit_length',30)+1)
        exit_ema=r['close'] if exit_ema is None else alpha*r['close']+(1-alpha)*exit_ema
        result.append(dict(s,chop=chop,er=er,flips8=flips,ema_exit=exit_ema))
    return result
def allowed(s,policy):
    if policy=='BASELINE':return True
    if policy.startswith('CHOP'):return s['chop'] is not None and s['chop']<float(policy[4:])
    if policy.startswith('ADX'):return s.get('adx') is not None and s['adx']>float(policy[3:])
    return s['er'] is not None and not(s['flips8']>=3 and s['er']<0.25)
def simulate(rows,signals,cfg,days,policy,bps,quota_mode='UNLIMITED'):
    p=None;pending=None;trades=[];blocked=[];curve=[];realized=0.;rearm=False;last_exit=-1;gaps=0
    def close(price,at,why):
        nonlocal p,realized,rearm,last_exit
        gross=p['side']*(price-p['entry'])
        cost=(price+p['entry'])*bps/10000
        trades.append(dict(p,exit=price,exit_at=at,reason=why,gross=gross,cost=cost,net=gross-cost))
        realized+=gross-cost;p=None;rearm=True;last_exit=at
    used=0;quota_day=None
    ix=[i for i,r in enumerate(rows) if datetime.fromtimestamp(r['timestamp'],IST).date().isoformat() in days]
    for k,i in enumerate(ix):
        r=rows[i];s=signals[i];at=r['timestamp'];clock=datetime.fromtimestamp(at,IST);exited=False
        if quota_mode=='DAILY2' and quota_day!=clock.date():used=0;quota_day=clock.date()
        deadline=clock.replace(hour=int(cfg['session_deadline'][:2]),minute=int(cfg['session_deadline'][3:]),second=0,microsecond=0).timestamp()
        if pending:
            action,side,expected,signal_at=pending;pending=None
            if action=='EXIT' and p:close(r['open'],at,'SIGNAL_EXIT' if at==expected else 'GAP_EXIT');exited=True
            elif action=='ENTRY' and at==expected and at<deadline:
                p=dict(side=side,entry=r['open'],entry_at=at,signal_at=signal_at);rearm=False;used+=1
            else:gaps+=1
        if p and at>=deadline:close(r['open'],at,'SESSION_EXIT');exited=True
        if p:
            adverse=cfg.get('ema_exit_enabled',True) and (r['close']<s['ema_exit'] if p['side']==1 else r['close']>s['ema_exit'])
            sig=dict(s,supertrend_cross_direction=s['raw_supertrend_cross_direction'])
            direction='BULLISH' if p['side']==1 else 'BEARISH'
            if adverse or reason(cfg,sig,direction):pending=('EXIT',0,at+300,at)
        elif not exited and at+300<deadline and (quota_mode=='UNLIMITED' or used<cfg['max_trades']):
            direction=s['entry_direction']
            if rearm and s['entry_qualified'] and at>last_exit:direction=s['direction']
            if direction:
                if allowed(s,policy):pending=('ENTRY',1 if direction=='BULLISH' else -1,at+300,at)
                else:blocked.append(dict(at=at,direction=direction,chop=s['chop'],adx=s['adx'],er=s['er'],flips=s['flips8']))
        curve.append(realized+(p['side']*(r['close']-p['entry'])-(r['close']+p['entry'])*bps/10000 if p else 0))
        if k==len(ix)-1 and p:close(r['close'],at+300,'PERIOD_END');curve[-1]=realized
    peak=0.;dd=0.
    for v in curve:peak=max(peak,v);dd=max(dd,peak-v)
    return dict(trades=trades,blocked=blocked,net_points=round(realized,3),gross_points=round(sum(t['gross'] for t in trades),3),max_drawdown_points=round(dd,3),trades_count=len(trades),win_rate=round(sum(t['net']>0 for t in trades)/len(trades),3) if trades else None,gap_skips=gaps)
def main():
    cfg=json.load(open(BASE/'renko-instances/9abcfe9c2d417c1e7efe/state.json'))['config']
    candidates=[]
    for p in (BASE/'renko-chart-history').glob('*.json'):
        d=json.load(open(p));raw=d['rows']
        if len(raw)>2 and raw[1][0]-raw[0][0]==300:candidates.append((p,raw))
    path,raw=max(candidates,key=lambda x:len(x[1]))
    # Exclude current incomplete session: final holdout contains completed prior sessions only.
    today=datetime.now(IST).date().isoformat()
    rows=[dict(zip(('timestamp','open','high','low','close','volume'),x)) for x in raw if datetime.fromtimestamp(x[0],IST).date().isoformat()<today]
    assert all(rows[i]['timestamp']<rows[i+1]['timestamp'] for i in range(len(rows)-1))
    signals=features(rows,cfg)
    for cut in (50,200,len(rows)//2):
        prefix=features(rows[:cut],cfg)
        assert prefix[-1]==signals[cut-1],'Future leakage in indicator features'
    days=sorted(set(datetime.fromtimestamp(x['timestamp'],IST).date().isoformat() for x in rows))
    usable=days[3:];n=len(usable);a=n//3;b=2*n//3
    splits={'DEVELOPMENT':usable[:a],'VALIDATION':usable[a:b],'HOLDOUT':usable[b:]}
    policies=['BASELINE','CHOP55','CHOP61.8','ADX20','ADX25','REVERSALS_LOW_PROGRESS']
    output=dict(scope='Underlying directional research proxy, NOT option execution or option net profitability.',config=cfg,source=str(path),data_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(Path('strategies/renko_supertrend/signals.py').read_bytes()).hexdigest(),warmup_sessions=days[:3],rules='Completed native host candles; own Engine indicator formulas; next contiguous open fills; exits preserved; no intrabar paths; same-bar reentry forbidden. Re-arm after exit mirrors qualified subsequent candle. Final period forces close. Operational max_trades is per runner lifetime and intentionally omitted: continuous signal research, not production lifecycle replay. No option preflight, spread, quote, expiry, funds or fill model.',filters='CHOP14 on host true ranges, strict below threshold; ADX14/14 strict above; reversal gate blocks >=3 synthetic-direction flips in8 host bars AND14-bar efficiency<0.25. Alternatives only, no stacked selection.',costs='0,2,5 basis points per side are sensitivity assumptions on underlying, NOT broker option charges.',results={})
    for name,ds in splits.items():
        output['results'][name]=dict(start=ds[0],end=ds[-1],sessions=len(ds),runs={})
        for bps in (0,2,5):
            baseline=simulate(rows,signals,cfg,set(ds),'BASELINE',bps)
            base_entries={t['entry_at']:t for t in baseline['trades']}
            for policy in policies:
                r=baseline if policy=='BASELINE' else simulate(rows,signals,cfg,set(ds),policy,bps)
                selected={t['entry_at'] for t in r['trades']}
                omitted=[t for at,t in base_entries.items() if at not in selected]
                # Attribution describes absent baseline entries, not causal P&L contribution.
                r['avoided_baseline_losses']=sum(t['net']<0 for t in omitted)
                r['missed_baseline_winners']=sum(t['net']>0 for t in omitted)
                r['omitted_baseline_net_points']=round(sum(t['net'] for t in omitted),3)
                delays=[]
                for t in omitted:
                    later=[x for x in r['trades'] if x['side']==t['side'] and t['entry_at']<x['entry_at']<t['exit_at']]
                    if later:delays.append((min(x['entry_at'] for x in later)-t['entry_at'])/60)
                r['matched_later_entries']=len(delays);r['mean_delay_minutes']=sum(delays)/len(delays) if delays else None
                output['results'][name]['runs'][f'{policy}@{bps}']=r
    ROOT.mkdir(parents=True,exist_ok=True);(ROOT/'results.json').write_text(json.dumps(output,indent=2))
    lines=['# NIFTY sideways-entry assessment','',output['scope'],'',output['rules'],'',output['costs'],'','| Period | Filter | Trades | Gross points | Net at 2bp/side | Max drawdown points | Avoided baseline losses | Missed baseline winners |','|---|---|---:|---:|---:|---:|---:|---:|']
    for name,period in output['results'].items():
        for policy in policies:
            r=period['runs'][policy+'@2']
            lines.append(f"| {name} {period['start']} to {period['end']} | {policy} | {r['trades_count']} | {r['gross_points']} | {r['net_points']} | {r['max_drawdown_points']} | {r['avoided_baseline_losses']} | {r['missed_baseline_winners']} |")
    lines+=['','The final third is chronological holdout. Thresholds were fixed before running; no search or threshold selection used. Earlier user research has seen some of these dates: this is a withheld split for this experiment, not globally unseen market data. No executable historical option quotes were available. Omitted baseline trades include changed-path effects, not guaranteed saved money. Auto brick sizing uses each historical host ATR causally. No production files, settings or services changed.']
    (ROOT/'report.md').write_text('\n'.join(lines))
    print('\n'.join(lines))
if __name__=='__main__':main()

