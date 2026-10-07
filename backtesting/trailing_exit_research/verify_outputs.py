import csv,json,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
r=list(csv.DictReader((OUT/'results_final.csv').open()));assert len(r)==8928
counts={}
for x in r:
 key=(x['arm'],x['slippage'],x['split'])
 counts.setdefault(key,int(x['trades']));assert counts[key]==int(x['trades'])
d=list(csv.DictReader((OUT/'trade_details_final.csv').open()));entries={}
for x in d:
 key=x['at'];record=(x['symbol'],x['paid'])
 entries.setdefault(key,record);assert entries[key]==record
 assert int(x['exit_i'])<=int(x['baseline_end'])
sample=json.loads((OUT/'sample_final.json').read_text());assert len(entries)==sample['eligible']==1783
assert len(list((OUT/'selected_history').glob('*.json')))==185
report=(OUT/'report.html').read_text();assert report.startswith('<!doctype html>') and report.endswith('</body></html>');assert 'Interpretation of the heldout result' in report
manifest={str(p.relative_to(OUT)):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.csv','.html','.md') and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('Verified',len(r),'summary rows,',len(entries),'fixed paired entries, 185 contract histories; manifest saved.')
