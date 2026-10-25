"""Read-only, checksum-retained NSE daily MII contract evidence for research.

Exact StockNm, expiry, strike and option side must agree. No current-lot
fallback or validity extrapolation is made from a daily file.
"""
import csv,gzip,io,json,re
from datetime import date,datetime,timedelta
from pathlib import Path
from decimal import Decimal
from .historical_lots import atomic,digest,IST
PROVIDER='NSE_MII_CONTRACT_MASTER'
BASE='data/backtesting/nse-contract-masters'
HOSTS=('archives.nseindia.com','nsearchives.nseindia.com')
def source_url(day,host='nsearchives.nseindia.com'):
    return 'https://'+host+'/content/fo/NSE_FO_contract_'+date.fromisoformat(day).strftime('%d%m%Y')+'.csv.gz'
def contract_date(value):
    # NSE FO legacy timestamp: seconds since 1 January 1980; use calendar date.
    return (datetime(1980,1,1)+timedelta(seconds=int(value))).date().isoformat()
def archive(root,day,blob,url):
    if url not in [source_url(day,h) for h in HOSTS]:raise ValueError('NSE source URL/date mismatch.')
    rows=csv.DictReader(io.StringIO(gzip.decompress(blob).decode('utf-8-sig')))
    required={'StockNm','FinInstrmId','FinInstrmNm','TckrSymb','XpryDt','StrkPric','OptnTp','MinLot','NewBrdLotQty'}
    if not required.issubset(rows.fieldnames or []):raise ValueError('Not an NSE MII contract file.')
    root=Path(root);sha=digest(blob);raw=root/BASE/'objects'/(sha+'.csv.gz')
    if not raw.exists():atomic(raw,blob)
    elif digest(raw.read_bytes())!=sha:raise ValueError('NSE object checksum mismatch.')
    m=dict(schema=1,provider=PROVIDER,as_of_date=day,effective_from=day,effective_to=day,source_url=url,source_file=str(raw.relative_to(root)),source_sha256=sha,observed_at=datetime.now(IST).isoformat(),timestamp_basis='NSE dated daily MII contract filename',date_policy='Daily applicability; no forward/backward substitution')
    target=root/BASE/'manifests'/day/(sha+'.json')
    if not target.exists():atomic(target,json.dumps(m,sort_keys=True,indent=2).encode())
    return m
def resolve(root,contract,day,cache):
    matches=[];invalid=[];root=Path(root)
    if not contract['symbol'].startswith('NSE:'):return matches,invalid
    for path in sorted((root/BASE/'manifests'/day).glob('*.json')):
        try:
            m=json.loads(path.read_text())
            if m['schema']!=1 or m['provider']!=PROVIDER or m['as_of_date']!=day or m['effective_from']!=day or m['effective_to']!=day or m['source_url'] not in [source_url(day,h) for h in HOSTS]:raise ValueError('NSE dated source identity mismatch.')
            raw=(root/m['source_file']).resolve()
            if not raw.is_relative_to((root/BASE/'objects').resolve()):raise ValueError('NSE evidence outside archive.')
            key=('NSE',str(raw),m['source_sha256'])
            if key not in cache:
                blob=raw.read_bytes()
                if digest(blob)!=m['source_sha256']:raise ValueError('NSE contract object checksum mismatch.')
                rows=csv.DictReader(io.StringIO(gzip.decompress(blob).decode('utf-8-sig')));index={}
                for number,row in enumerate(rows,2):index.setdefault('NSE:'+row['StockNm'],[]).append((number,row))
                cache[key]=index
            for number,row in cache[key].get(contract['symbol'],[]):
                expiry=contract_date(row['XpryDt']);lot=Decimal(row['NewBrdLotQty'])
                if row['FinInstrmNm'] not in ('OPTIDX','OPTSTK') or expiry!=contract['expiry'] or row['OptnTp']!=contract['option_type'] or Decimal(row['StrkPric'])/100!=Decimal(str(contract['strike'])):raise ValueError('NSE exact-contract identity mismatch.')
                if not lot.is_finite() or lot<=0 or lot!=lot.to_integral_value() or Decimal(row['MinLot'])!=lot:raise ValueError('NSE lot fields missing, invalid or conflicting.')
                if day>expiry or (row.get('StartDt') and contract_date(row['StartDt'])>day):raise ValueError('NSE contract not valid on requested date.')
                matches.append(dict(m,symbol=contract['symbol'],expiry=expiry,lot_size=int(lot),snapshot_as_of=day,source_row=number,exchange_token=row['FinInstrmId'],exchange_underlying=row['TckrSymb'],raw_fields={k:row[k] for k in ('StockNm','FinInstrmId','TckrSymb','XpryDt','StrkPric','OptnTp','MinLot','NewBrdLotQty','StartDt')},encoding='NSE seconds since 1980-01-01; strike price in paise; exact StockNm match',manifest_sha256=digest(path.read_bytes()),validity_evidence=None))
        except (OSError,ValueError,KeyError,TypeError,ArithmeticError) as error:invalid.append(dict(manifest=str(path.relative_to(root)),reason=str(error)))
    return matches,invalid
