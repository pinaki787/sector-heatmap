import json
from pathlib import Path
import tempfile
import unittest
from sector_heatmap.straddle_paper import prepare
from tests.test_sensex_straddle import SCRIPT

class StraddleWalletTests(unittest.TestCase):
    def test_isolated_source_full_lifecycle_and_live_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'original.py';source.write_text(SCRIPT)
            runtime=Path(d)/'runtime'
            target=prepare(source,runtime,10000)
            self.assertEqual(source.read_text(),SCRIPT);self.assertNotEqual(source,target)
            state=runtime/'live_position_state.json'
            scope={'__name__':'fixture','__file__':str(target),'save_state':lambda value:state.write_text(json.dumps(value)),'clear_state':lambda:state.unlink()}
            exec(compile(target.read_text(),str(target),'exec'),scope)
            held=scope['enter_position']()
            funds=json.loads((runtime/'paper-capital.json').read_text())
            self.assertEqual(funds['reserved_inr'],2000);self.assertEqual(funds['available_inr'],7990)
            prepare(source,runtime,10000)
            self.assertEqual(json.loads((runtime/'paper-capital.json').read_text()),funds)
            with self.assertRaisesRegex(ValueError,'original capital'):prepare(source,runtime,20000)
            scope['exit_position'](held,'signal')
            funds=json.loads((runtime/'paper-capital.json').read_text())
            self.assertEqual(funds['available_inr'],10179);self.assertEqual(funds['reserved_inr'],0)
            scope['DRY_RUN']=False
            with self.assertRaisesRegex(RuntimeError,'refuses live'):scope['place_order']('CE',20,1)

    def test_insufficient_capital_blocks_before_any_order_or_state(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'original.py';source.write_text(SCRIPT)
            runtime=Path(d)/'runtime';target=prepare(source,runtime,100)
            scope={'__name__':'fixture','__file__':str(target),'save_state':lambda value:self.fail('Entry state must not be recorded')}
            exec(compile(target.read_text(),str(target),'exec'),scope)
            scope['place_order']=lambda *a,**k:self.fail('No order call permitted')
            with self.assertRaisesRegex(ValueError,'Virtual Paper capital insufficient'):scope['enter_position']()
            self.assertEqual(json.loads((runtime/'paper-capital.json').read_text())['available_inr'],100)
