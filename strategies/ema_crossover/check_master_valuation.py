"""Read-only validation of all current option valuation metadata and examples."""
import csv
import io
import json
import time
from pathlib import Path
import requests
from strategies.ema_crossover.broker import FyersBroker


def main():
    root = Path(__file__).resolve().parents[2]
    broker = FyersBroker(root / '.private/ema-band-masters', None, None)
    examples = {'CRUDEOILM','CRUDEOIL','GOLD','GOLDM','SILVER','SILVERM','NATURALGAS','NATGASMINI','NIFTY','BANKNIFTY','SENSEX'}
    for segment in ('MCX_COM','NSE_FO','BSE_FO'):
        response = requests.get(f'https://public.fyers.in/sym_details/{segment}_sym_master.json',timeout=30)
        response.raise_for_status()
        broker.instrument_masters[segment] = (time.time(), response.json())
        csv_response = requests.get(f'https://public.fyers.in/sym_details/{segment}.csv', timeout=30)
        csv_response.raise_for_status()
        rows = list(csv.reader(io.StringIO(csv_response.text)))
        options = [r for r in rows if len(r)>16 and r[16] in ('CE','PE') and float(r[8])>time.time()]
        failures=[];shown=set()
        for row in options:
            broker.rows=lambda segment, r=row:[r]
            try:
                contract=broker.contract(row[9])
                if row[13] in examples and row[13] not in shown:
                    print(json.dumps(contract));shown.add(row[13])
            except ValueError as error:
                failures.append({'symbol':row[9],'error':str(error)})
        print(json.dumps(dict(segment=segment,checked=len(options),failures=len(failures),failure_examples=failures[:3])))


if __name__ == '__main__':main()
