"""Load staged publication modules in this isolated test process only."""
import importlib.util
import os
from pathlib import Path
import runpy
import sys

folder = Path(sys.argv[1]).resolve()
target = sys.argv[2]
sys.argv = sys.argv[2:]
for short in ('confirmed_feed', 'price_basis'):
    name = 'strategies.renko_supertrend.'+short
    prefix='fyers-' if short=='price_basis' and os.environ.get('PRICE_PUBLICATION_OWNER')=='fyers' else ''
    path = Path('strategies/renko_supertrend')/(short+'.py') if short=='confirmed_feed' and os.environ.get('PRICE_PUBLICATION_LEGACY_FEED')=='1' else folder/(prefix+short+'.candidate.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
runpy.run_path(target, run_name='__main__')
