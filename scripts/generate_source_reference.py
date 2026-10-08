"""Generate a secret-free module/settings map from source without imports or execution."""
import ast
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'docs/source-reference.md'


def source_files():
    paths=list(ROOT.glob('*.py'))
    for folder in ('sector_heatmap','strategies','backtesting','scripts'):
        paths.extend((ROOT/folder).rglob('*.py'))
    return sorted(p for p in set(paths) if not any(part in ('__pycache__','cache') for part in p.parts) and not p.name.startswith('test_'))


def render():
    out=['# Generated source and settings reference','Generated from source on 8 October 2026 without importing modules or reading credential/runtime files. This is a coverage map of all Python application, strategy, helper and research sources and root JavaScript. It complements the [technical guide](technical-guide.md), [user guide](user-functional-guide.md), and [deployment guide](deployment-guide.md). Function signatures list exact defaults; payload-setting entries list literal fallbacks. Defaults in wrappers can override helper defaults. Research modules remain research-only. Source links own full branches, formulas, validation and rounding; the catalog does not execute them.']
    for p in source_files():
        rel=p.relative_to(ROOT).as_posix();tree=ast.parse(p.read_text())
        out += ['## '+rel,'[Owning source](../'+rel+')']
        if ast.get_docstring(tree):out.append(ast.get_docstring(tree).split('\n')[0])
        entries=[]
        def walk(body,prefix=''):
            for n in body:
                if isinstance(n,ast.ClassDef):walk(n.body,prefix+n.name+'.')
                elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    entries.append('- `'+prefix+n.name+'('+ast.unparse(n.args)+')`')
        walk(tree.body)
        if entries:out.append('### Callables and explicit defaults\n\n'+'\n'.join(entries))
        defaults=set()
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('get','getenv') and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str):
                key=n.args[0].value
                if any(x in key.lower() for x in ('secret','token','password','api_key','credential')):continue
                if len(n.args)>1:
                    try:ast.literal_eval(n.args[1]);fallback=ast.unparse(n.args[1])
                    except (ValueError,TypeError):continue
                    if '\n' not in fallback and len(fallback)<160:defaults.add((key,fallback))
        if defaults:out.append('### Literal payload and lookup fallbacks\n\n'+'\n'.join('- `'+k+'` → `'+v+'`' for k,v in sorted(defaults)))
        literals=[]
        for n in tree.body:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
                key=n.targets[0].id
                if key in ('DEFAULTS','TIMEFRAMES','RESOLUTIONS','INTERVALS','RATES','TREND_WEIGHTS','MOMENTUM_WEIGHTS','SECTOR_SCORE_WEIGHTS','MTF_MODES','ROTATION'):
                    value=ast.unparse(n.value)
                    if len(value)<5000:literals.append('- `'+key+' = '+value+'`')
        if literals:out.append('### Configuration literals\n\n'+'\n'.join(literals))
    for p in sorted(ROOT.glob('*.js')):
        rel=p.relative_to(ROOT).as_posix();text=p.read_text()
        out += ['## '+rel,'[Owning source](../'+rel+')']
        funcs=sorted(set(re.findall(r'function\s+(\w+)\s*\(',text)))
        if funcs:out.append('### Named functions\n\n'+', '.join('`'+name+'`' for name in funcs))
        fields=sorted(set(re.findall(r'(?:id|data-toggle)=["\']([A-Za-z0-9_-]+)',text)))
        if fields:out.append('### UI field and toggle identifiers\n\n'+', '.join('`'+name+'`' for name in fields))
    TARGET.write_text('\n\n'.join(out)+'\n')
    print('Wrote source catalog:',len(source_files()),'Python modules')

if __name__=='__main__':render()
