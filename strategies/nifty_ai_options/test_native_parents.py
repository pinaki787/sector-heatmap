import unittest
from compare_native_parents import compare
class ParentComparisonTests(unittest.TestCase):
    def tv(self):
        labels=['Parent open timestamp','Standard parent close timestamp','Parent open','Parent high','Parent low','Parent close','Ordinary parent ATR5']
        return dict(metainfo=dict(plots=[dict(id=str(i),title=name) for i,name in enumerate(labels)]),
            values=[dict(plots=dict(zip(map(str,range(7)),[0,900000,10,12,9,11,3])))])
    def test_identical_duplicates_do_not_invalidate_complete_window(self):
        row=[0,10,12,9,11,1]
        out=compare([row,row],self.tv())
        self.assertEqual(out['duplicate_identical_rows'],1)
        self.assertEqual(out['complete_compared'],1)
        self.assertEqual(out['exact_ohlc_matches'],1)
    def test_conflicting_duplicate_is_not_silently_selected(self):
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            compare([[0,10,12,9,11,1],[0,10,12,9,10,1]],self.tv())
