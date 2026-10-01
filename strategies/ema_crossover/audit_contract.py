"""Read-only master, funds and margin-calculator evidence; never submits orders."""
import json
import argparse
import requests
from sector_heatmap.config import load_config
from sector_heatmap.fyers_execution import _current_client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('symbol', help='Exact FYERS master-listed option symbol')
    symbol = parser.parse_args().symbol
    master = 'MCX_COM' if symbol.startswith('MCX:') else symbol.split(':')[0] + '_FO'
    response = requests.get(f'https://public.fyers.in/sym_details/{master}_sym_master.json', timeout=20)
    response.raise_for_status()
    row = response.json()[symbol]
    client = _current_client()
    funds = client.funds()
    quote = client.quotes({'symbols': symbol})
    payload = dict(symbol=symbol, qty=row['minLotSize'], type=2, side=1, productType='MARGIN',
                   limitPrice=0, stopPrice=0, validity='DAY', disclosedQty=0, offlineOrder=False)
    margin = requests.post('https://api-t1.fyers.in/api/v3/multiorder/margin',
                           headers={'Authorization': load_config().get('FYERS_ACCESS_TOKEN', '')},
                           json={'data': [payload]}, timeout=10)
    margin.raise_for_status()
    print(json.dumps(dict(master={k:row.get(k) for k in ('symTicker','minLotSize','qtyMultiplier','lastUpdate')},
                          funds=funds, quote=quote, margin=margin.json(), calculator_payload=payload), indent=2))


if __name__ == '__main__':
    main()
