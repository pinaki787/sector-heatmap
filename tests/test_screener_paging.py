import unittest
from sector_heatmap.screener_paging import page_request, MAX_SYMBOLS

class ScreenerPagingTests(unittest.TestCase):
    def test_all_65_symbols_have_a_page(self):
        symbols=[f"STOCK{i}" for i in range(65)]
        seen=[]
        for offset in range(0,65,12):
            total,_,_,page,_,_=page_request(dict(symbols=symbols,offset=offset))
            self.assertEqual(len(total),65)
            seen.extend(page)
        self.assertEqual(seen,symbols)
    def test_excess_is_rejected_not_truncated(self):
        with self.assertRaisesRegex(ValueError,"at most"):
            page_request(dict(symbols=[str(i) for i in range(MAX_SYMBOLS+1)]))
    def test_cache_does_not_reuse_different_scan_metadata_or_prices(self):
        first=page_request(dict(symbols=["ABC"],prices={"ABC":10}))[-1]
        longer=page_request(dict(symbols=["ABC","DEF"],limit=1,prices={"ABC":10}))[-1]
        changed=page_request(dict(symbols=["ABC"],prices={"ABC":11}))[-1]
        self.assertNotEqual(first,longer)
        self.assertNotEqual(first,changed)
    def test_normalization_and_bounded_page(self):
        symbols,_,limit,page,_,_=page_request(dict(symbols=[" abc ","ABC",""],limit=99))
        self.assertEqual(symbols,["ABC"])
        self.assertEqual(page,["ABC"])
        self.assertEqual(limit,12)
