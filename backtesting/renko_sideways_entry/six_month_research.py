"""Six-month extension: research only; no runtime imports or broker mutations."""
import csv,hashlib,json
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from research import features,simulate,allowed
ROOT=Path(__file__).resolve().parent;IST=ZoneInfo('Asia/Kolkata')
POLICIES=['BASELINE','CHOP55','CHOP61.8','ADX20','ADX25','REVERSALS_LOW_PROGRESS']
def main():
    original=json.load(open(ROOT/'results.json'));cfg=original['config']
    raw=json.load(open(ROOT/'six_month_candles.json'));rows=[];excluded=[]
    for r in raw['rows']:
        t=datetime.fromtimestamp(r[0],IST)
        if not (t.hour*60+t.minute>=555 and t.hour*60+t.minute<930):
            excluded.append(dict(timestamp=r[0],time=t.isoformat(),reason='OUTSIDE_REGULAR_SESSION'));continue
        if not(r[3]<=min(r[1],r[4])<=max(r[1],r[4])<=r[2]):raise ValueError('Malformed OHLC')
        rows.append(dict(zip(('timestamp','open','high','low','close','volume'),r)))
    counts=Counter(datetime.fromtimestamp(r['timestamp'],IST).date().isoformat() for r in rows)
    gaps=[]
    for day in sorted(counts):
        actual={r['timestamp'] for r in rows if datetime.fromtimestamp(r['timestamp'],IST).date().isoformat()==day}
        start=datetime.fromisoformat(day+'T09:15:00').replace(tzinfo=IST).timestamp()
        for j in range(75):
            if int(start+j*300) not in actual:gaps.append(dict(day=day,missing_open=int(start+j*300)))
    signals=features(rows,cfg)
    for cut in [100,1000,len(rows)//2]:
        assert features(rows[:cut],cfg)[-1]==signals[cut-1]
    target=[d for d in sorted(counts) if '2026-04-12'<=d<='2026-10-11']
    warm=[d for d in sorted(counts) if d<target[0]]
    n=len(target);a=n//3;b=2*n//3
    periods={'DEVELOPMENT':target[:a],'VALIDATION':target[a:b],'HOLDOUT':target[b:]}
    monthly=defaultdict(list)
    for d in target:monthly[d[:7]].append(d)
    out=dict(scope='Underlying-price proxy ONLY; not executable options returns.',config=cfg,config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),data_sha256=hashlib.sha256((ROOT/'six_month_candles.json').read_bytes()).hexdigest(),source_hash=hashlib.sha256(Path('strategies/renko_supertrend/signals.py').read_bytes()).hexdigest(),coverage=dict(requested_from='2026-04-12',requested_to='2026-10-11',actual_from=target[0],actual_to=target[-1],sessions=n,bars=sum(counts[d] for d in target),warmup_sessions=len(warm),warmup_start=warm[0],missing_within_returned_sessions=gaps,excluded_offsession=excluded,absent_weekdays=[ ],duplicates=raw['duplicates'],revisions=raw['revisions']),results={},monthly={})
    # Absent weekdays are listed without assuming holiday versus outage.
    from datetime import date,timedelta
    day=date.fromisoformat(target[0]);end=date.fromisoformat(target[-1])
    while day<=end:
        if day.weekday()<5 and str(day) not in counts:out['coverage']['absent_weekdays'].append(str(day))
        day+=timedelta(days=1)
    for name,ds in periods.items():
        runs={}
        for quota in ['UNLIMITED','DAILY2','RUN2']:
            for bps in [0,2,5]:
                baseline=simulate(rows,signals,cfg,set(ds),'BASELINE',bps,quota)
                for policy in POLICIES:
                    r=baseline if policy=='BASELINE' else simulate(rows,signals,cfg,set(ds),policy,bps,quota)
                    entries={t['entry_at'] for t in r['trades']}
                    omitted=[t for t in baseline['trades'] if t['entry_at'] not in entries]
                    r['omitted_baseline_losers']=sum(t['net']<0 for t in omitted)
                    r['omitted_baseline_winners']=sum(t['net']>0 for t in omitted)
                    r['omitted_baseline_net_points']=sum(t['net'] for t in omitted)
                    delays=[]
                    for t in omitted:
                        later=[v for v in r['trades'] if v['side']==t['side'] and t['entry_at']<v['entry_at']<t['exit_at']]
                        if later:delays.append((min(v['entry_at'] for v in later)-t['entry_at'])/60)
                    r['matched_delays_count']=len(delays);r['mean_delay_minutes']=sum(delays)/len(delays) if delays else None
                    runs[f'{quota}/{policy}@{bps}']=r
        out['results'][name]=dict(start=ds[0],end=ds[-1],sessions=len(ds),runs=runs)
    # Attribute continuous target-period trades to ENTRY month, not independently reset monthly portfolios.
    for quota in ['UNLIMITED','DAILY2']:
        for policy in POLICIES:
            r=simulate(rows,signals,cfg,set(target),policy,2,quota)
            for month in monthly:
                trades=[t for t in r['trades'] if datetime.fromtimestamp(t['entry_at'],IST).strftime('%Y-%m')==month]
                out['monthly'][f'{quota}/{policy}/{month}']=dict(trades=len(trades),net_points=round(sum(t['net'] for t in trades),3))
    (ROOT/'six_month_results.json').write_text(json.dumps(out,indent=2))
    lines=['# Six-month NIFTY sideways-filter research','',out['scope'],'',json.dumps(out['coverage'],indent=2),'','Fixed saved baseline: five-minute Auto bricks, ATR5, factor3 with existing regime adjustment; EMA10/30 widening2; RSI14 slope; EMA30 exit;15:10 cutoff. No higher timeframe or RSI level filter. Same Engine formulas, completed ordinary candles, next contiguous open, preserved exits, three chronological splits with prior-history warmup. No threshold search. Final holdout was not used to select parameters; some dates were previously examined in other research, so this is not globally unseen data.','', 'Quota audit: production max_trades=2 counts accepted entry submissions per runner run, may be consumed even if broker rejects. RUN2 models two successful simulated entries per evaluation period and then no more (optimistic absent reject evidence). DAILY2 assumes a fresh run each session, which is NOT automatic production behavior. UNLIMITED is continuous signal research. Actual historical user restart times are unavailable.','', 'Costs:0/2/5bp PER SIDE on underlying are sensitivity assumptions, not verified option commissions/spread/slippage. No historical option executable quotes, contract selection or broker rejection simulation. No production or account state changed.','', '| Period | Quota | Filter | Trades | Gross pts | Net2bp | DD pts | Absent losers | Missed winners | Mean matched delay min |','|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,p in out['results'].items():
        for quota in ['UNLIMITED','DAILY2','RUN2']:
            for policy in POLICIES:
                r=p['runs'][f'{quota}/{policy}@2']
                delay=round(r['mean_delay_minutes'],2) if r['mean_delay_minutes'] is not None else '—'
                lines.append(f"| {name} {p['start']}–{p['end']} | {quota} | {policy} | {r['trades_count']} | {r['gross_points']} | {r['net_points']} | {r['max_drawdown_points']} | {r['omitted_baseline_losers']} | {r['omitted_baseline_winners']} | {delay} |")
    lines+=['','## Monthly stability at2bp/side, continuous trades grouped by entry month','','| Month | Quota | Baseline | CHOP55 | CHOP61.8 | ADX20 | ADX25 | Reversals/low progress |','|---|---|---:|---:|---:|---:|---:|---:|']
    for month in monthly:
        for quota in ['UNLIMITED','DAILY2']:
            vals=[str(out['monthly'][f'{quota}/{p}/{month}']['net_points']) for p in POLICIES]
            lines.append('| '+month+' | '+quota+' | '+' | '.join(vals)+' |')
    lines+=['','Absent baseline entries describe changed execution paths, not guaranteed saved money. Drawdown is mark-to-market underlying points; net figures are additive points, not percentage portfolio returns. No overnight underlying position carried. Four pre-open FYERS bars excluded consistently; missing weekdays require official holiday reconciliation before labeling an outage.','', 'Validation: prefix invariance at100/1000/half-history, chronological unique OHLC/session checks. Warmup has no trades/quota use. Candidate uses no later data. Full trades and blocked assessments retained in JSON.']
    (ROOT/'six_month_report.md').write_text('\n'.join(lines))
    print('Coverage',out['coverage']['actual_from'],out['coverage']['actual_to'],n,'sessions','bars',out['coverage']['bars'],'gaps',len(gaps))
    for name,p in out['results'].items():
        for quota in ['UNLIMITED','DAILY2','RUN2']:
            print(name,quota,[(policy,p['runs'][f'{quota}/{policy}@2']['net_points'],p['runs'][f'{quota}/{policy}@2']['trades_count']) for policy in POLICIES])
if __name__=='__main__':main()

