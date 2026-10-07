"""Prepare an isolated Paper copy of the external straddle source.

Live continues to execute the original file. Refuse unknown entry/exit shapes.
"""
import ast
from pathlib import Path
from .paper_wallet import capital

def prepare(source,runtime,initial,lots=1):
    initial=capital(initial);source=Path(source);runtime=Path(runtime)
    text=source.read_text();tree=ast.parse(text)
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    entry=functions.get('enter_position');exit=functions.get('exit_position');place=functions.get('place_order')
    if not entry or not exit or not place:raise ValueError('Verified straddle Paper entry/exit functions required.')
    quantity='quantity' if any(isinstance(n,ast.Name) and n.id=='quantity' for n in ast.walk(entry)) else 'QUANTITY'
    entry_anchor='    ce_order = place_order(ce_symbol, '+quantity+', side=1)'
    lines=text.splitlines(keepends=True)
    entry_text=''.join(lines[entry.lineno-1:entry.end_lineno])
    exit_text=''.join(lines[exit.lineno-1:exit.end_lineno])
    if entry_text.count(entry_anchor)!=1 or exit_text.count('    clear_state()\n')!=1 or entry_text.count('    save_state(state)\n')!=1:raise ValueError('Straddle source changed; Paper wallet integration requires review.')
    helper=f'''
import sys as _paper_sys
_paper_sys.path.insert(0,{str(Path(__file__).resolve().parent.parent)!r})
from sector_heatmap.paper_wallet import wallet as _wallet, reserve as _reserve, release as _release
from pathlib import Path as _PaperPath
_paper_wallet_path=_PaperPath({str(runtime/'paper-capital.json')!r})
def _paper_load():
    return json.loads(_paper_wallet_path.read_text())
def _paper_save(value):
    value['configured_lots']=NUM_LOTS
    temp=_paper_wallet_path.with_suffix('.tmp');temp.write_text(json.dumps(value,allow_nan=False));temp.replace(_paper_wallet_path)
def _paper_check(value):
    if not DRY_RUN:raise RuntimeError('Isolated Paper source refuses live execution.')
    return _reserve(_paper_load(),value)
def _paper_close(value,pnl):
    if not DRY_RUN:raise RuntimeError('Isolated Paper source refuses live execution.')
    _paper_save(_release(_paper_load(),value,pnl))
'''
    # Inject only into simulation lifecycle accounting; signal/quantity/exit logic is unchanged.
    patched_entry=entry_text.replace(entry_anchor,'    _paper_next=_paper_check(premium_entry*'+quantity+')\n'+entry_anchor).replace('    save_state(state)\n','    save_state(state)\n    _paper_save(_paper_next)\n')
    patched_exit=exit_text.replace('    clear_state()\n','    _paper_close(premium_exit*'+quantity+',pnl_rupees)\n    clear_state()\n')
    place_text=''.join(lines[place.lineno-1:place.end_lineno]);place_lines=place_text.splitlines(keepends=True)
    # Block all order paths in this isolated source if a live flag is ever supplied.
    first_body=place.body[0].lineno-place.lineno
    place_lines.insert(first_body,'    if not DRY_RUN:raise RuntimeError("Isolated Paper source refuses live execution.")\n')
    text=text.replace(entry_text,patched_entry,1).replace(exit_text,patched_exit,1).replace(place_text,''.join(place_lines),1)
    # Helpers must be defined before the script main guard; imports require no market access.
    marker='if __name__ == "__main__":'
    if text.count(marker)!=1:raise ValueError('Verified straddle main guard required.')
    text=text.replace(marker,helper+'\n'+marker)
    compile(text,str(source),'exec')
    runtime.mkdir(parents=True,exist_ok=True)
    state=runtime/'live_position_state.json'
    held=state.exists() and state.read_text().strip() not in ('','null','{}')
    import json
    if held:
        try:funds=json.loads((runtime/'paper-capital.json').read_text())
        except (OSError,ValueError):raise ValueError('Verified virtual wallet required to resume existing Paper straddle exposure.') from None
        if funds.get('initial_inr')!=initial or funds.get('configured_lots')!=lots:raise ValueError('Resume existing Paper straddle exposure with its original capital and lots.')
    target=runtime/("paper-"+source.name);target.write_text(text)
    import json
    if not held:(runtime/'paper-capital.json').write_text(json.dumps(dict(initial_inr=initial,realized_gross_inr=0,fee_provision_inr=0,reserved_inr=0,available_inr=initial,basis='Per-run virtual INR capital; 0.5% fee provision per filled side; no leverage or live balance.')))
    return target
