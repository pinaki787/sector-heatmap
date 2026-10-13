import unittest
from strategies.renko_supertrend.manual_brick import rule,calculate

class ManualReferenceBrickTests(unittest.TestCase):
    def test_all_indian_instrument_classes_share_exchange_rule(self):
        for symbol in ('NSE:NIFTY50-INDEX','BSE:SENSEX-INDEX','NSE:RELIANCE-EQ','NSE:TEST-CE','BSE:TEST-PE'):
            self.assertEqual(rule(symbol)['atr_length'],5)
            self.assertEqual(rule(symbol)['reference_seconds'],21600)
            self.assertAlmostEqual(250/rule(symbol)['divisor'],20.8333333333333)
    def test_crypto_reference(self):
        r=rule('ETHUSD',{'session_exchange':'CRYPTO'})
        self.assertEqual((r['reference_seconds'],r['atr_length']),(82800,7))
        self.assertEqual(1500/r['divisor'],1500/46)
    def test_mcx_exact_session_duration(self):
        self.assertEqual(rule('MCX:GOLD',{'master_regular_session':'0900-2330'})['divisor'],29)
        self.assertAlmostEqual(rule('MCX:GOLD',{'master_regular_session':'0900-2355'})['divisor'],895/30)
        with self.assertRaises(ValueError):rule('MCX:GOLD')
    def test_completed_reference_coverage_and_wilder_result(self):
        spec=rule('ETHUSD',{'session_exchange':'CRYPTO'})
        span=spec['reference_seconds'];rows=[]
        for n in range(9):
            for stamp in range(n*span,(n+1)*span,300):
                rows.append(dict(timestamp=stamp,open=2000,high=2750,low=1250,close=2000))
        result=calculate(rows,spec,300,9*span)
        self.assertEqual(result['manual_brick'],32.61)
        self.assertEqual(result['reference_bars'],9)
        conflicting=rows+[dict(rows[0],high=3000)]
        with self.assertRaises(ValueError):calculate(conflicting,spec,300,9*span)
        # Removing bars cannot manufacture complete history.
        incomplete=[r for r in rows if r['timestamp']%span!=0]
        with self.assertRaises(ValueError):calculate(incomplete,spec,300,9*span)
        with self.assertRaises(ValueError):calculate(rows,spec,300,7*span)


class ReferencePersistenceTests(unittest.TestCase):
    def test_reference_survives_saved_timeframe_change(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        import json
        from strategies.renko_supertrend.preferences import write,read
        reference=dict(symbol='NSE:NIFTY50-INDEX',manual_brick=250/12)
        with TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            draft={'symbol':reference['symbol'],'brick-mode':'Manual','manual-brick':250/12,
                   'manual-brick-reference':json.dumps(reference),'timeframe':'1 minute'}
            write(path,{'settings':draft},1)
            draft=read(path)['settings']
            draft['timeframe']='15 minutes'
            write(path,{'settings':draft},2)
            result=read(path)['settings']
            self.assertEqual(result['manual-brick'],250/12)
            self.assertEqual(json.loads(result['manual-brick-reference']),reference)
