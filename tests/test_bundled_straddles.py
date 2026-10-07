"""No imports of script bodies, authentication, subprocess runner or market access."""
import ast
import tempfile
import unittest
from pathlib import Path
from sector_heatmap.straddle_paper import prepare

ROOT=Path(__file__).resolve().parents[1]

class BundledStraddleTests(unittest.TestCase):
    def test_bundled_sources_remain_fail_closed_and_support_isolated_paper(self):
        for name in ('nifty','sensex'):
            source=ROOT/'strategies/long_straddle'/f'{name}_straddle.py'
            tree=ast.parse(source.read_text())
            defaults=[n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DRY_RUN' for t in n.targets)]
            self.assertEqual(defaults,[True])
            with tempfile.TemporaryDirectory() as folder:
                patched=prepare(source,Path(folder),100000,1)
                text=patched.read_text()
                self.assertIn('Isolated Paper source refuses live execution.',text)
                compile(text,str(patched),'exec')
                self.assertIn(name.upper()+'_STRADDLE_RUNTIME_DIR',text)
