import unittest
from unittest.mock import patch
from instrument_search import search_fyers

def row(symbol,asset,kind='XX',expiry='',segment='10'):
    r=['']*21;r[9]=symbol;r[1]=asset+' description';r[13]=asset;r[16]=kind;r[8]=expiry;r[11]=segment
    return r
class InstrumentSearchTests(unittest.TestCase):
    def test_futures_and_stock_options_are_different_current_masters(self):
        rows={'NSE_CM':[row('NSE:RELIANCE-EQ','RELIANCE'),row('NSE:UNLISTED-EQ','UNLISTED'),row('NSE:NIFTY50-INDEX','NIFTY')],
              'NSE_FO':[row('NSE:RELIANCE26NOVFUT','RELIANCE',expiry='200'),row('NSE:RELIANCE26NOV300CE','RELIANCE','CE','200'),row('NSE:OLD26NOVFUT','OLD',expiry='99')]}
        with patch('instrument_search.master_rows',side_effect=lambda folder,segment:rows[segment]):
            result=search_fyers('/unused','','NSE_FUTURE',now=100)
            self.assertEqual([r['symbol'] for r in result['matches']],['NSE:RELIANCE26NOVFUT'])
            result=search_fyers('/unused','','NSE_STOCK',now=100)
            self.assertEqual([r['symbol'] for r in result['matches']],['NSE:RELIANCE-EQ'])
    def test_gold_and_other_commodity_have_distinct_parent_mapping(self):
        rows=[row('MCX:GOLD26DECFUT','GOLD',expiry='200'),row('MCX:SILVER26DECFUT','SILVER',expiry='200')]
        with patch('instrument_search.master_rows',return_value=rows):
            result=search_fyers('/unused','','MCX',now=100)
        self.assertEqual({r['symbol']:r['parent_hours'] for r in result['matches']},{'MCX:GOLD26DECFUT':22,'MCX:SILVER26DECFUT':14})
