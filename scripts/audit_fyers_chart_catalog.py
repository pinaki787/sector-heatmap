"""Read-only audit of an exact workspace's cached native chart catalog. No network."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Exact owner source directory beneath repository')
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    source = (repository / args.source).resolve()
    if not source.is_relative_to(repository) or not (source / 'sector_heatmap/chart_workspace.py').is_file():
        parser.error('Choose a source directory beneath this repository.')
    sys.path.insert(0, str(source))
    from sector_heatmap.chart_workspace import search_cached_fyers_chart_symbols, FYERS_CHART_SYMBOL
    folder = source / '.private/ema-band-masters'
    segments = ('NSE_CM', 'BSE_CM', 'NSE_FO', 'BSE_FO', 'MCX_COM', 'NSE_CD', 'NSE_COM')
    results = []
    paths = []
    for segment in segments:
        path = folder / (segment + '.csv')
        if not path.is_file():
            results.append({'segment': segment, 'status': 'MISSING'})
            continue
        paths.append(path)
        with path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.reader(stream))
        native = {row[9] for row in rows if len(row) > 9}
        first = search_cached_fyers_chart_symbols([path], limit=1)
        last = search_cached_fyers_chart_symbols([path], offset=max(0, first['total'] - 1), limit=1)
        rejected = sorted(symbol for symbol in native if not FYERS_CHART_SYMBOL.fullmatch(symbol))
        results.append({'segment': segment, 'status': 'AUDITED', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'native_unique': len(native), 'search_total': first['total'],
                        'rejected_count': len(rejected), 'rejected_examples': rejected[:10],
                        'first_and_last_reachable': len(first['symbols']) == len(last['symbols']) == 1,
                        'age_hours': round((time.time() - path.stat().st_mtime) / 3600, 2)})
    combined = search_cached_fyers_chart_symbols(paths, limit=1) if paths else None
    print(json.dumps({'read_only': True, 'network_requests': 0, 'source': str(source.relative_to(repository)),
                      'checked_at': int(time.time()), 'segments': results,
                      'combined_search_total': combined['total'] if combined else None,
                      'scope': 'Cached native catalog parsing and sampled pagination; not OHLC entitlement or symbol-by-symbol feed validation.'}, indent=2))


if __name__ == '__main__':
    main()
