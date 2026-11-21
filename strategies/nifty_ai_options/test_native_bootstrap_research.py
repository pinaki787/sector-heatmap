import unittest
from native_bootstrap_research import BootstrapContext,CachedATRBootstrap
def context(owner='owner-a',symbol='TEST'):
    return BootstrapContext(owner,'TEST_BROKER',symbol,360,2,'regular',.05,1)
def bar(t,price,spread=1):
    return dict(time=t,open=price,high=price+spread,low=price-spread,close=price)
class BootstrapResearchTests(unittest.TestCase):
    def test_first_true_range_is_missing_and_first_valid_atr_is_frozen(self):
        c=CachedATRBootstrap(context())
        self.assertEqual(c.update(bar(1,100),closed=True),[])
        c.update(bar(2,102),closed=True);self.assertIsNone(c.box)
        c.update(bar(3,104),closed=True)
        self.assertEqual(c.seed_atr,3);self.assertEqual(c.box,3)
        c.update(bar(4,150,20),closed=True)
        self.assertEqual(c.box,3)
        self.assertFalse(c.snapshot()['eligible_for_strategy'])
    def test_forming_updates_do_not_seed_and_contexts_remain_isolated(self):
        a=CachedATRBootstrap(context());b=CachedATRBootstrap(context('owner-b'))
        a.update(bar(1,100),closed=False);self.assertEqual(a.bars,0)
        for t in range(1,4):
            a.update(bar(t,100+t),closed=True)
            b.update(bar(t,100+t*10),closed=True)
        self.assertNotEqual(a.box,b.box)
        self.assertNotEqual(a.snapshot()['context_sha256'],b.snapshot()['context_sha256'])
    def test_canonical_start_and_closed_source_revisions_are_enforced(self):
        c=CachedATRBootstrap(context())
        with self.assertRaisesRegex(ValueError,'source start'):c.update(bar(2,100),closed=True)
        c.update(bar(1,100),closed=True)
        self.assertEqual(c.update(bar(1,100),closed=True),[])
        with self.assertRaisesRegex(ValueError,'revised'):c.update(bar(1,101),closed=True)
