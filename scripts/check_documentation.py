"""Check canonical guide local links, catalog coverage and credential-pattern exclusions."""
import re
from pathlib import Path
from generate_source_reference import ROOT, source_files
FILES=[ROOT/'README.md']+[ROOT/'docs'/name for name in ('technical-guide.md','user-functional-guide.md','deployment-guide.md','source-reference.md')]
errors=[]
for p in FILES:
    text=p.read_text()
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
        if target.startswith(('http:','https:','#','mailto:')):continue
        local=target.split('#',1)[0]
        if local and not (p.parent/local).exists():errors.append(str(p.relative_to(ROOT))+': missing '+target)
    if re.search(r'(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN .*PRIVATE KEY)',text):errors.append(str(p)+': credential pattern')
catalog=(ROOT/'docs/source-reference.md').read_text()
for p in source_files():
    if '## '+p.relative_to(ROOT).as_posix()+'\n' not in catalog:errors.append('Uncovered source: '+str(p.relative_to(ROOT)))
for p in ROOT.glob('*.js'):
    if '## '+p.name+'\n' not in catalog:errors.append('Uncovered JavaScript: '+p.name)
if errors:
    print('\n'.join(errors));raise SystemExit(1)
print('Canonical links, credential-pattern scan and complete module catalog coverage passed.')
