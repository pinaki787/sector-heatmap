from pathlib import Path
import json, hashlib, re
root=Path(__file__).resolve().parent.parent
canonical=(root/'sector-pulse-v1.pine').read_text()
owners=['.']+[f'.private/dashboard-login/accounts/{x}/source' for x in ['fd46b26f73022af571be11b1027c5291','1b0a63fa2d371d3be413763078d21bbc','b0041912d9d6f68d352814cbd24bf6da','08823c4c2082f03de07634a51e39f9fb','bf46fc364b610a0dfd338419e133cb41','a6ef4c9bcecd21d54c4a07e2b9b137a7']]
for owner in owners:
    source=(root/owner/'chart-workspace.js').read_text()
    match=re.search(r'function sharedSectorPulseV1\(\) \{\s*return (.*?);\n  \}',source)
    assert match, f'{owner}: shared catalog missing'
    entry=json.loads(match[1])
    assert entry['catalogId']=='pine-sector-pulse-v1'
    assert entry['source']==canonical, f'{owner}: stale shared V1'
    assert entry['sha256']==hashlib.sha256(canonical.encode()).hexdigest()
print(f'PASS: shared V1 canonical revision across {len(owners)} sources')

central=json.loads((root/'chart-shared-indicators.json').read_text())
assert central['indicators'][0]['source']==canonical
assert central['indicators'][0]['sha256']==hashlib.sha256(canonical.encode()).hexdigest()
