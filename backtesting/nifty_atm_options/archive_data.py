"""Create a credential-free, version-preserving market-data archive."""
import argparse,datetime,hashlib,json,shutil
from pathlib import Path
from zoneinfo import ZoneInfo
Z=ZoneInfo('Asia/Kolkata')
ALLOWED={'exchangeSegment','interval','securityId','instrument','expiryFlag','expiryCode','strike','drvOptionType','requiredData','fromDate','toDate'}
def archive(folder,destination):
 folder=Path(folder);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);records=[]
 old_path=destination/'catalog.json';old=json.loads(old_path.read_text()) if old_path.exists() else {}
 for label,directory in [('main',folder/'cache'),('revisions',folder/'cache/revisions'),('pilot',folder.parent/'nifty_atm_option_review/pilot-cache'),('extended_partial',folder.parent/'nifty_atm_option_review/surface-cache')]:
  target=destination/'raw'/label;target.mkdir(parents=True,exist_ok=True)
  for source in sorted(directory.glob('*.json')):
   obj=json.loads(source.read_text())
   if not isinstance(obj.get('request'),dict) or not isinstance(obj.get('data'),dict):continue
   if not set(obj)<={'request','data','received_at'} or not set(obj['data'])<={'open','high','low','close','iv','volume','strike','spot','oi','timestamp'}:raise ValueError('Unexpected provider fields; refuse unsafe archive: '+source.name)
   if not set(obj['request'])<=ALLOWED:raise ValueError('Unexpected request fields; refuse unsafe archive: '+source.name)
   ts=obj['data'].get('timestamp',[])
   if not ts:continue
   content=source.read_bytes();digest=hashlib.sha256(content).hexdigest();out=target/source.name
   if out.exists() and hashlib.sha256(out.read_bytes()).hexdigest()!=digest:out=target/(source.stem+'-'+digest[:12]+'.json')
   if not out.exists():shutil.copy2(source,out)
   clocks=[datetime.datetime.fromtimestamp(t,Z) for t in ts];regular=sum(555<=t.hour*60+t.minute<930 for t in clocks)
   records.append(dict(file=str(out.relative_to(destination)),source_file=source.name,sha256=digest,bytes=len(content),provider='Dhan',underlying='NIFTY50',segment='NSE_FNO',option_side=obj['request']['drvOptionType'],relative_strike=obj['request']['strike'],expiry_series='WEEK/1',interval_minutes=5,requested_from=obj['request']['fromDate'],requested_to_exclusive=obj['request']['toDate'],raw_bars=len(ts),regular_session_bars=regular,first_timestamp_ist=clocks[0].isoformat(),last_timestamp_ist=clocks[-1].isoformat()))
 underlying_records=[]
 for name in ('underlying.json','fresh_underlying.json'):
  source=folder/'inputs'/name
  if not source.exists():continue
  obj=json.loads(source.read_text());clean={k:obj[k] for k in ('symbol','resolution_minutes','rows','request','requested_start','requested_end','retrieved_at') if k in obj}
  if 'request' in clean and any(any(word in k.lower() for word in ('token','secret','password')) for k in clean['request']):raise ValueError('Refuse credential-bearing underlying request')
  out=destination/'underlying'/name;out.parent.mkdir(exist_ok=True);content=json.dumps(clean).encode();digest=hashlib.sha256(content).hexdigest()
  if out.exists() and hashlib.sha256(out.read_bytes()).hexdigest()!=digest:out=out.with_name(out.stem+'-'+digest[:12]+'.json')
  if not out.exists():out.write_bytes(content)
  seen={};duplicates=0;conflicts=set();invalid=0
  for row in clean.get('rows',[]):
   timestamp=int(row[0])
   if timestamp in seen:
    duplicates+=1
    if row[1:]!=seen[timestamp][1:]:conflicts.add(timestamp)
   seen[timestamp]=row
   if not row[3]<=min(row[1],row[4])<=max(row[1],row[4])<=row[2]:invalid+=1
  conflicting_days=sorted({datetime.datetime.fromtimestamp(t,Z).date().isoformat() for t in conflicts})
  underlying_records.append(dict(file=str(out.relative_to(destination)),source_file=source.name,sha256=digest,bytes=len(content),provider='FYERS',underlying='NIFTY50',raw_bars=len(clean.get('rows',[])),duplicate_timestamps=duplicates,conflicting_timestamps=len(conflicts),invalid_ohlc=invalid,exclude_days_until_reconciled=conflicting_days))
 current={(r['file'],r['sha256']) for r in records}
 records.extend(r for r in old.get('option_files',[]) if (r['file'],r['sha256']) not in current and (destination/r['file']).exists())
 previous={(r['file'],r['sha256']) for r in underlying_records}
 underlying_records.extend(r for r in old.get('underlying_files',[]) if (r['file'],r['sha256']) not in previous and (destination/r['file']).exists())
 manifest_path=folder/'cache/manifest.json';manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {};complete=manifest.get('completed')==manifest.get('planned') and not manifest.get('failures') and {r['file'] for r in manifest.get('responses',[])}<={r.get('source_file',Path(r['file']).name) for r in records if r['file'].startswith('raw/main/')}
 catalog=dict(schema_version=1,dataset='NIFTY underlying and nearest-week ATM-relative option history',status='COMPLETE_REQUESTS' if complete else 'PARTIAL_DOWNLOAD',updated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),session_timezone='Asia/Kolkata',raw_option_files=len(records),underlying_files=underlying_records,source_request_progress={k:manifest.get(k) for k in ('planned','completed','cached','failures','offsets','underlying_sha256')},option_files=records,limitations=['Rolling ATM-relative series; reconstruct held fixed strike, never hold a changing ATM label.','Weekly ordinal expiry is provided; absolute historical expiry dates are not supplied.','Raw data retains provider off-session rows; filter and validate sessions before replay.','Historical OHLC and volume are not executable bid/ask quotes.','Download completion is not the same as candle/contract completeness.','No broker credentials, access tokens, account configuration or live state are archived.'])
 temp=destination/'catalog.tmp';temp.write_text(json.dumps(catalog,indent=2));temp.replace(destination/'catalog.json')
 (destination/'.gitignore').write_text('*\n!.gitignore\n!README.md\n')
 (destination/'README.md').write_text('''# Reusable NIFTY backtesting data

This is a durable local/hosted market-data archive. `catalog.json` indexes raw option responses and underlying history by provider, date, call/put side, relative strike, interval and SHA-256 checksum. Check its download status before using the dataset.

`raw/main/` contains one-session Dhan rolling-option responses. `raw/pilot/` preserves the two-session method-validation sample. `raw/extended_partial/` retains the successful portions of the earlier larger requests. `underlying/` contains FYERS underlying candles. Previous contents are retained under a checksum suffix when a source changes.

For reuse, validate candles and timezone, exclude off-session data, and join by timestamp, option side and the **fixed strike selected at entry**. Do not concatenate a rolling ATM label as if it were one held option contract. The raw expiry identifier is the nearest-week series ordinal, not an absolute contract expiry date. OHLC prices do not prove executable fills or bid/ask liquidity.

Underlying catalog entries flag duplicate timestamps, conflicting values and invalid OHLC. Exclude dates listed under `exclude_days_until_reconciled`; raw responses are preserved for audit rather than silently corrected.

The archive contains no broker tokens, credentials, strategy account settings or runner state. Raw data and the generated catalog are ignored by Git. No data is published automatically.
''')
 print(json.dumps(dict(destination=str(destination),status=catalog['status'],option_files=len(records),underlying_files=len(underlying_records))))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--folder',default='backtesting/nifty_atm_options');p.add_argument('--destination',required=True);a=p.parse_args();archive(a.folder,a.destination)
