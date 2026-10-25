"""Maintain public FYERS symbol masters without starting or stopping runners."""
from pathlib import Path
import csv,io,json,time,os,tempfile,fcntl
import requests
SOURCES={s:f'https://public.fyers.in/sym_details/{s}.csv' for s in ('NSE_CM','BSE_CM','NSE_FO','BSE_FO','MCX_COM')}
REFRESH_AFTER=12*3600

def validate(text,segment):
    rows=list(csv.reader(io.StringIO(text)))
    if len(rows)<100 or sum(len(r)>16 and ':' in r[9] for r in rows)<100:
        raise ValueError('Invalid or incomplete symbol-master response: '+segment)
    return text

def atomic(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def maintain(roots,fetch,now=None):
    now=time.time() if now is None else now
    statuses={}
    for root in roots:
        cache=root/'.private/ema-band-masters'
        try:old=json.loads((cache/'maintenance-status.json').read_text())
        except (OSError,ValueError):old={}
        statuses[root]=dict(revision='proactive-master-cache-v1',checked_at=now,refresh_after_hours=12,retry_seconds=60,segments=old.get('segments',{}))
    for segment,url in SOURCES.items():
        due=[r for r in roots if not (r/'.private/ema-band-masters'/f'{segment}.csv').exists() or now-(r/'.private/ema-band-masters'/f'{segment}.csv').stat().st_mtime>=REFRESH_AFTER]
        if not due:continue
        try:
            body=validate(fetch(url),segment)
        except Exception as error:
            for r in due:statuses[r]['segments'][segment]=dict(status='REFRESH_FAILED',attempted_at=now,error=str(error)[:300],last_success_at=statuses[r]['segments'].get(segment,{}).get('last_success_at'))
            continue
        for r in due:
            try:
                atomic(r/'.private/ema-band-masters'/f'{segment}.csv',body)
                statuses[r]['segments'][segment]=dict(status='FRESH',attempted_at=now,last_success_at=now,error=None)
            except OSError as error:
                statuses[r]['segments'][segment]=dict(status='REFRESH_FAILED',attempted_at=now,error=str(error)[:300])
        # Archival failures must not prevent the existing live-master refresh.
        if roots and segment in ('NSE_FO','BSE_FO','MCX_COM'):
            try:
                from strategies.renko_supertrend.historical_lots import archive_master
                archived=archive_master(roots[0],segment,body,now)
                statuses[roots[0]].setdefault('historical_archive',{})[segment]=dict(status='SAVED',as_of_date=archived['as_of_date'],sha256=archived['source_sha256'])
            except Exception:
                statuses[roots[0]].setdefault('historical_archive',{})[segment]=dict(status='FAILED',message='Live master refreshed; dated research archive unavailable. Historical sizing will remain withheld.')
    for r,status in statuses.items():
        status['healthy']=not any(x.get('status')=='REFRESH_FAILED' for x in status['segments'].values())
        atomic(r/'.private/ema-band-masters/maintenance-status.json',json.dumps(status))
    return statuses

def main():
    import socket,sector_heatmap
    assert getattr(socket.getaddrinfo,'_sector_pulse_ipv4_only',False),'IPv4 policy required'
    root=Path(__file__).resolve().parents[1]
    lock=root/'.private/master-cache-maintenance.lock';lock.parent.mkdir(exist_ok=True)
    with lock.open('a') as fd:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        session=requests.Session();session.trust_env=False
        def fetch(url):
            response=session.get(url,timeout=(10,30));response.raise_for_status();return response.text
        roots=[root]+list((root/'.private/dashboard-login/accounts').glob('*/source'))
        statuses=maintain(roots,fetch)
        failed=[str(r) for r,s in statuses.items() if not s['healthy']]
        print(f'Master maintenance: {len(roots)} source copies; {len(failed)} with refresh failures',flush=True)
        if failed:raise SystemExit(1)
if __name__=='__main__':main()
