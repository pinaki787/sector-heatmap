import ast
from datetime import datetime,timedelta
from pathlib import Path
import threading,time,unittest

class IsolationTests(unittest.TestCase):
    def test_slow_symbol_does_not_block_another_symbol(self):
        tree=ast.parse(Path('sector_heatmap/web.py').read_text())
        function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='ema_band_candles')
        scope={'__name__':'sector_heatmap.web','__package__':'sector_heatmap','datetime':datetime,'timedelta':timedelta,'time':time,'threading':threading,'ema_history_lock':threading.RLock(),'ema_history_key_locks':{},'ema_history_cache':{}}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'isolated-history','exec'),scope)
        entered=threading.Event();release=threading.Event();second=threading.Event();errors=[]
        class Client:
            def history(self,request):
                if request['symbol']=='SLOW':entered.set();release.wait(3)
                else:second.set()
                return {'s':'error','message':'Simulated provider failure'}
        def fetch(symbol):
            try:scope['ema_band_candles'](Client(),symbol,'1 minute')
            except RuntimeError as error:errors.append(str(error))
        first=threading.Thread(target=fetch,args=('SLOW',));other=threading.Thread(target=fetch,args=('FAST',))
        first.start();self.assertTrue(entered.wait(1));other.start()
        try:self.assertTrue(second.wait(1),'Slow symbol held a global history lock')
        finally:release.set();first.join(2);other.join(2)
        self.assertEqual(len(errors),2)
