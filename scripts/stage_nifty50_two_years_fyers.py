"""Resumable, data-only FYERS archive; never calls order or runner APIs."""
import csv,hashlib,json,math,time
from pathlib import Path
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from collections import Counter
from sector_heatmap.fyers_transport import client
ROOT=Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24')
IST=ZoneInfo('Asia/Kolkata')
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(d));temp.replace(p)
def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    token=json.loads(Path('.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/home/.fyers/token.json').read_text())
    app=token.get('app_id') or token.get('client_id');value=token.get('access_token') or token.get('token')
    if ':' in value:
        prefix,value=value.split(':',1)
        if prefix!=app:raise RuntimeError('Application mismatch')
    api=client(client_id=app,token=value)
    manifest=dict(symbol='NSE:NIFTY50-INDEX',provider='FYERS',requested_start='2024-10-25',requested_end='2026-10-24',timezone='Asia/Kolkata',status='running',timeframes={},errors=[],notes=['Direct broker candles for each timeframe; no synthetic filling.','Weekday absences are candidates only: exchange holiday calendar not reconciled.','Index volume is retained as returned; not constituent traded volume.'])
    save(ROOT/'manifest.json',manifest)
    for resolution in [1,5,30]:
        rows={};chunks=[];conflicts=[];duplicates=0;cursor=date(2024,10,25)
        while cursor<=date(2026,10,24):
            end=min(date(2026,10,24),cursor+timedelta(days=89))
            p=ROOT/'raw'/str(resolution)/(str(cursor)+'_'+str(end)+'.json')
            if p.exists():
                response=json.loads(p.read_text())
            else:
                response=api.history(data=dict(symbol=manifest['symbol'],resolution=str(resolution),date_format='1',range_from=str(cursor),range_to=str(end),cont_flag='1'))
                save(p,response);time.sleep(1.4)
            bars=response.get('candles',[])
            summary=dict(start=str(cursor),end=str(end),status=response.get('s'),code=response.get('code'),bars=len(bars),file=str(p.relative_to(ROOT)))
            chunks.append(summary)
            print(json.dumps(dict(resolution=resolution,**summary)),flush=True)
            if response.get('s')!='ok':
                manifest['errors'].append(dict(resolution=resolution,**summary,message=response.get('message')))
                if response.get('code') in [-8,-15,-16,-17,401]:
                    manifest['status']='blocked_auth';save(ROOT/'manifest.json',manifest);return
            for r in bars:
                if r[0] in rows:
                    duplicates+=1
                    if rows[r[0]]!=r:conflicts.append(r[0])
                rows[r[0]]=r
            cursor=end+timedelta(days=1)
        ordered=[rows[k] for k in sorted(rows)]
        invalid=[];daily=Counter();outside=[];gaps=[]
        previous=None
        for r in ordered:
            dt=datetime.fromtimestamp(r[0],IST);daily[str(dt.date())]+=1
            if len(r)<6 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in r[:6]) or not (r[3]<=min(r[1],r[4])<=max(r[1],r[4])<=r[2]):invalid.append(r[0])
            if not (9*60+15<=dt.hour*60+dt.minute<15*60+30):outside.append(r[0])
            if previous and previous.date()==dt.date() and (dt-previous).total_seconds()>resolution*60:gaps.append(dict(after=previous.isoformat(),before=dt.isoformat()))
            previous=dt
        merged=ROOT/('nifty50_'+str(resolution)+'m.json')
        save(merged,dict(symbol=manifest['symbol'],resolution_minutes=resolution,rows=ordered))
        cp=ROOT/('nifty50_'+str(resolution)+'m.csv')
        with cp.open('w') as f:
            w=csv.writer(f);w.writerow(['epoch','timestamp_ist','open','high','low','close','volume'])
            for r in ordered:w.writerow([r[0],datetime.fromtimestamp(r[0],IST).isoformat(),*r[1:6]])
        missing=[];day=date(2024,10,25)
        while day<=date(2026,10,24):
            if day.weekday()<5 and str(day) not in daily:missing.append(str(day))
            day+=timedelta(days=1)
        audit=dict(daily_counts=dict(sorted(daily.items())),weekday_dates_without_data=missing,invalid_ohlc=invalid,conflicting_timestamps=conflicts,outside_regular_session=outside,intraday_gap_candidates=gaps)
        save(ROOT/('audit_'+str(resolution)+'m.json'),audit)
        manifest['timeframes'][str(resolution)]=dict(bars=len(ordered),sessions=len(daily),first_ist=datetime.fromtimestamp(ordered[0][0],IST).isoformat() if ordered else None,last_ist=datetime.fromtimestamp(ordered[-1][0],IST).isoformat() if ordered else None,duplicates=duplicates,invalid_ohlc=len(invalid),conflicts=len(conflicts),gap_candidates=len(gaps),outside_regular_session=len(outside),chunks=chunks,sha256=hashlib.sha256(merged.read_bytes()).hexdigest())
        save(ROOT/'manifest.json',manifest)
    manifest['status']='downloaded_with_errors' if manifest['errors'] else 'downloaded'
    manifest['finished_at']=datetime.now(IST).isoformat()
    manifest['bytes_on_disk']=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
    save(ROOT/'manifest.json',manifest)
    (ROOT/'README.md').write_text('# NIFTY 50 FYERS historical candles\n\nRequested: 25 October 2024 through 24 October 2026 inclusive.\n\nDirect broker OHLCV at 1, 5 and 30 minutes. Raw responses are preserved; merged CSV/JSON files are sorted by timestamp. See manifest.json for actual coverage and checksums and audit files for OHLC checks, session counts and gap candidates. Missing weekday dates include exchange holidays; completeness requires calendar reconciliation. Special sessions are retained and flagged rather than removed. No missing candles are fabricated.\n\nResume: PYTHONPATH=. .venv/bin/python scripts/stage_nifty50_two_years_fyers.py\n')
    print(json.dumps(manifest),flush=True)
if __name__=='__main__':main()
