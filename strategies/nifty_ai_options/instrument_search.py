"""Read-only exact-symbol AI search, isolated from legacy preferences."""
import csv,io,time,os,secrets
from pathlib import Path
from datetime import datetime
import requests
from zoneinfo import ZoneInfo
IST=ZoneInfo('Asia/Kolkata')
MARKETS={'NSE_INDEX':('NSE_CM',),'BSE_INDEX':('BSE_CM',),'NSE_EQUITY':('NSE_CM',),'BSE_EQUITY':('BSE_CM',),'NSE_STOCK':('NSE_CM','NSE_FO'),'BSE_STOCK':('BSE_CM','BSE_FO'),'NSE_FUTURE':('NSE_FO',),'BSE_FUTURE':('BSE_FO',),'MCX':('MCX_COM',),'ALL':('NSE_CM','BSE_CM','NSE_FO','BSE_FO','MCX_COM')}
def master_rows(folder,segment):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);path=folder/(segment+'.csv');today=datetime.now(IST).date()
    if not path.exists() or datetime.fromtimestamp(path.stat().st_mtime,IST).date()!=today:
        response=requests.get('https://public.fyers.in/sym_details/'+segment+'.csv',timeout=(5,30));response.raise_for_status()
        temp=path.with_name(path.name+'.'+str(os.getpid())+'-'+secrets.token_hex(6)+'.tmp')
        try:temp.write_text(response.text);temp.replace(path)
        finally:temp.unlink(missing_ok=True)
    return [r for r in csv.reader(io.StringIO(path.read_text())) if len(r)>16]
def search_fyers(folder,query,market,route='OPTIONS',now=None):
    if market not in MARKETS:raise ValueError('Choose a supported market')
    query=str(query or '').strip().upper();now=time.time() if now is None else now
    if market=='ALL' and len(query)<2:return dict(matches=[],message='Choose a market or enter at least two search characters.')
    segments={segment:master_rows(folder,segment) for segment in MARKETS[market]}
    option_assets={r[13] for segment,rows in segments.items() if segment.endswith('_FO') for r in rows if r[16] in ('CE','PE') and r[8] and float(r[8])>now}
    matches={}
    for segment,rows in segments.items():
        for r in rows:
            symbol=r[9];index=symbol.endswith('-INDEX');cash=segment.endswith('_CM') and not index
            future=segment.endswith(('_FO','_COM')) and r[16]=='XX' and r[8] and float(r[8])>now
            if market.endswith('_INDEX') and not index:continue
            if market.endswith('_EQUITY') and not cash:continue
            if market.endswith('_STOCK') and (not cash or r[13] not in option_assets):continue
            if market.endswith('_FUTURE') and not future:continue
            if market=='MCX' and not future:continue
            if market=='ALL' and not (index or cash or future):continue
            if query and not all(word in ' '.join((symbol,r[1],r[13])).upper() for word in query.split()):continue
            exchange=symbol.split(':')[0];asset='GOLD' if exchange=='MCX' and r[13] in ('GOLD','GOLDM','GOLDGUINEA','GOLDPETAL') else None
            parent=22 if asset=='GOLD' else 14 if exchange=='MCX' else 6
            matches[symbol]=dict(symbol=symbol,underlying=r[13] or symbol,description=r[1],product_type='FUTURE' if future else 'INDEX' if index else 'STOCK',market=exchange,asset=asset,parent_hours=parent,expiry=float(r[8]) if future else None)
    result=sorted(matches.values(),key=lambda r:(r['symbol']!=query,r.get('expiry') or 0,r['symbol']))[:80]
    return dict(matches=result,message='Current FYERS master · exact selected symbol · no trading action')
