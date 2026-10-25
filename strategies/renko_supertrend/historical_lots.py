"""Exact-contract daily FYERS master evidence. No lot defaults or forward-fill."""
import csv,hashlib,io,json,math,os,tempfile
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
IST=ZoneInfo('Asia/Kolkata')
PROVIDER='FYERS_SYMBOL_MASTER'
def digest(blob):return hashlib.sha256(blob).hexdigest()
def atomic(path,blob):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
def archive_master(root,segment,body,observed_at,timestamp_basis='broker-download-completed'):
    if segment not in ('NSE_FO','BSE_FO','MCX_COM'):return None
    root=Path(root);blob=body.encode() if isinstance(body,str) else body;sha=digest(blob)
    clock=datetime.fromtimestamp(observed_at,IST);day=clock.date().isoformat();base=root/'data/backtesting/fyers-contract-masters'
    raw=base/'objects'/(sha+'.csv')
    if not raw.exists():atomic(raw,blob)
    elif digest(raw.read_bytes())!=sha:raise ValueError('Historical master object hash mismatch.')
    record=dict(schema=1,provider=PROVIDER,segment=segment,source_url=f'https://public.fyers.in/sym_details/{segment}.csv',source_file=str(raw.relative_to(root)),source_sha256=sha,observed_at=clock.isoformat(),timestamp_basis=timestamp_basis,as_of_date=day,effective_from=day,effective_to=day,date_policy='Snapshot day only; no projection onto earlier/later trading dates.')
    target=base/'manifests'/day/(segment+'-'+sha+'.json')
    if not target.exists():atomic(target,json.dumps(record,sort_keys=True,indent=2).encode())
    return record
def verified_period(root,manifest,contract,lot):
    """Optional explicit contract-period declaration from broker/exchange raw metadata.

    No period is inferred from file age, last-update date, or today's lot.
    """
    from urllib.parse import urlsplit
    declared=(manifest.get('contract_validity') or {}).get(contract['symbol'])
    if not declared:return manifest['as_of_date'],manifest['as_of_date'],None
    url=declared['source_url'];host=urlsplit(url).hostname
    if urlsplit(url).scheme!='https' or host not in ('public.fyers.in','api-t1.fyers.in','fyers.in','nsearchives.nseindia.com','www.nseindia.com','www.bseindia.com'):raise ValueError('Unrecognized effective-period authority.')
    root=Path(root);path=(root/declared['source_file']).resolve()
    if not path.is_relative_to((root/'data/backtesting/fyers-contract-masters').resolve()):raise ValueError('Effective-period evidence outside archive.')
    blob=path.read_bytes()
    if digest(blob)!=declared['source_sha256']:raise ValueError('Effective-period evidence checksum mismatch.')
    raw=json.loads(blob);record=raw['contracts'][contract['symbol']]
    if record['symbol']!=contract['symbol'] or record['expiry']!=contract['expiry'] or record['lot_size']!=int(lot):raise ValueError('Effective-period contract identity/lot mismatch.')
    first=record['effective_from'];last=record['effective_to']
    if not date.fromisoformat(first)<=date.fromisoformat(last)<=date.fromisoformat(contract['expiry']):raise ValueError('Invalid declared contract validity interval.')
    return first,last,dict(source_url=url,source_file=declared['source_file'],source_sha256=declared['source_sha256'],record=record,basis='Explicit authoritative contract effective-period declaration')
def checked_lot(contract,stamp):
    p=contract.get('lot_size_provenance') or {};lot=contract.get('lot_size');day=datetime.fromtimestamp(stamp,IST).date().isoformat()
    if isinstance(lot,bool) or not isinstance(lot,(int,float)) or not math.isfinite(lot) or int(lot)!=lot or lot<=0:return None
    try:
        if p['provider'] not in (PROVIDER,'NSE_MII_CONTRACT_MASTER') or p['symbol']!=contract['symbol'] or p['expiry']!=contract['expiry'] or p['lot_size']!=lot:return None
        if not p['effective_from']<=day<=p['effective_to']:return None
        if (p['effective_from']!=p['snapshot_as_of'] or p['effective_to']!=p['snapshot_as_of']) and not p.get('validity_evidence'):return None
        if len(p['source_sha256'])!=64:return None
        if p['provider']==PROVIDER and not p['source_url'].startswith('https://public.fyers.in/sym_details/'):return None
        if p['provider']=='NSE_MII_CONTRACT_MASTER':
            from .nse_contract_lots import source_url,HOSTS
            if p['source_url'] not in [source_url(p['snapshot_as_of'],h) for h in HOSTS]:return None
    except (KeyError,TypeError):return None
    return int(lot)
class HistoricalLots:
    def __init__(self,root):self.root=Path(root);self.cache={};self.last_gap=None
    def resolve(self,contract,stamp):
        day=datetime.fromtimestamp(stamp,IST).date().isoformat();segment='MCX_COM' if contract['symbol'].startswith('MCX:') else contract['symbol'].split(':')[0]+'_FO';matches=[];available=[];invalid=[]
        for manifest in sorted((self.root/'data/backtesting/fyers-contract-masters/manifests').glob('*/'+segment+'-*.json')):
            try:
                m=json.loads(manifest.read_text());asof=m['as_of_date']
                if m['schema']!=1 or m['provider']!=PROVIDER or m['segment']!=segment or m['source_url']!=f'https://public.fyers.in/sym_details/{segment}.csv':raise ValueError('Invalid master provenance.')
                path=(self.root/m['source_file']).resolve()
                if not path.is_relative_to((self.root/'data/backtesting/fyers-contract-masters/objects').resolve()):raise ValueError('Master source outside immutable archive.')
                key=(str(path),m['source_sha256'])
                if key not in self.cache:
                    blob=path.read_bytes()
                    if digest(blob)!=m['source_sha256']:raise ValueError('Master checksum mismatch.')
                    index={}
                    for number,row in enumerate(csv.reader(io.StringIO(blob.decode('utf-8-sig'))),1):
                        if len(row)>16:index.setdefault(row[9],[]).append((number,row))
                    self.cache[key]=index
                for number,row in self.cache[key].get(contract['symbol'],[]):
                    lot=float(row[3]);expiry=datetime.fromtimestamp(float(row[8]),IST).date().isoformat()
                    if not math.isfinite(lot) or lot<=0 or not lot.is_integer() or expiry!=contract['expiry'] or row[16]!=contract['option_type'] or float(row[15])!=float(contract['strike']):raise ValueError('Exact-contract master fields conflict.')
                    available.append(dict(snapshot_as_of=asof,lot_size=int(lot),source_sha256=m['source_sha256'],source_row=number))
                    first,last,period_proof=verified_period(self.root,m,contract,lot)
                    if not first<=day<=last:continue
                    if row[7] and date.fromisoformat(row[7])>date.fromisoformat(day):raise ValueError('Master row is future-dated.')
                    p=dict(provider=PROVIDER,symbol=contract['symbol'],expiry=expiry,lot_size=int(lot),snapshot_as_of=asof,effective_from=first,effective_to=last,validity_evidence=period_proof,source_url=m['source_url'],source_file=m['source_file'],source_sha256=m['source_sha256'],source_row=number,row_last_update=row[7],observed_at=m['observed_at'],timestamp_basis=m['timestamp_basis'],manifest_sha256=digest(manifest.read_bytes()))
                    matches.append(p)
            except (OSError,ValueError,KeyError,TypeError) as error:invalid.append(dict(manifest=str(manifest.relative_to(self.root)),reason=str(error)))
        from .nse_contract_lots import resolve as nse_resolve
        nse_matches,nse_invalid=nse_resolve(self.root,contract,day,self.cache)
        matches.extend(nse_matches);invalid.extend(nse_invalid)
        if matches and len({p['lot_size'] for p in matches})==1 and not invalid:
            p=matches[-1];self.last_gap=None
            return dict(lot_size=p['lot_size'],lot_size_source=f"{p['provider']} · {day} · row {p['source_row']} · SHA256 {p['source_sha256'][:12]}",lot_size_provenance=p)
        self.last_gap=dict(requested_date=day,contract=contract['symbol'],available_exact_contract_snapshots=available,invalid_sources=invalid,reason='Conflicting/invalid metadata' if invalid or matches else 'No exact-contract dated master or verified effective-period declaration covers the historical trade date; no earlier/later lot is substituted.')
        return dict(lot_size=None,lot_size_source='Missing date-applicable broker/exchange contract-master evidence',lot_size_provenance=None,lot_size_gap=self.last_gap)
