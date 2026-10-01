"""Bounded read-only stream probe. No runner, orders or settings changes."""
import json
import time
from pathlib import Path
from strategies.ema_crossover.broker import FyersBroker

if __name__ == '__main__':
    broker = FyersBroker(Path(__file__).resolve().parents[1]/'.private/ema-band-masters', None, None)
    symbol = 'BSE:SENSEX-INDEX'
    broker.underlying(symbol)
    broker.symbols.add(symbol)
    broker.start()
    result = {'verified':False,'symbol':symbol}
    try:
        deadline = time.monotonic()+12
        while time.monotonic()<deadline:
            try:
                tick=broker.tick(symbol)
                result={'verified':True,'symbol':symbol,'ltp':tick.get('ltp'),'exchange_timestamp':tick.get('exch_feed_time',tick.get('last_traded_time')),'stream':broker.stream_status()}
                break
            except ValueError as error:
                result['reason']=str(error)
            time.sleep(.5)
        result['stream']=broker.stream_status()
        print(json.dumps(result))
    finally:
        broker.stop()
