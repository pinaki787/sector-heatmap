"""Read-only smoke check: parses a sample plan, fetches market history, calls OpenAI.
Never submits an order. Run explicitly: .venv/bin/python scripts/check_trade_advisory.py
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from sector_heatmap.trade_advisory import analyze, settings
from sector_heatmap.config import ROOT, load_config

if __name__ == '__main__':
    config = settings()
    response = requests.get('https://api.openai.com/v1/models',
                            headers={'Authorization': 'Bearer ' + config['OPENAI_API_KEY']}, timeout=15)
    print('OpenAI authentication HTTP status:', response.status_code)
    payload = {'text': 'BUY DMART 29-SEP-2026 CE 3800 ABOVE 39 SL 35 TARGETS 45 50 55',
               'entry_mode': 'STOP_LIMIT', 'trigger_price': 39, 'limit_price': 39.05}
    def preview_provider(payload):
        response = requests.post('http://127.0.0.1:8080/api/trade-recommendation/parse', json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    result = analyze(preview_provider, payload, lambda: load_config().get('FYERS_ACCESS_TOKEN', ''), ROOT / '.private/ema-band-masters')
    print(json.dumps(result, indent=2))
