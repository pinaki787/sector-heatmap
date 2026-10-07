"""Read-only module readiness. Never constructs runners or contacts a broker."""
import importlib.util
import json
import platform
import shutil
from pathlib import Path
from zoneinfo import ZoneInfo


def readiness():
    root = Path(__file__).resolve().parents[1]
    modules = {name: importlib.util.find_spec(name) is not None for name in
               ('fyers_apiv3', 'requests', 'websocket', 'openpyxl')}
    ZoneInfo('Asia/Kolkata')
    return {'runtime_modules': modules, 'timezone': True,
            'whatsapp': {'supported': platform.system() == 'Darwin',
                         'compiler': bool(shutil.which('swiftc')),
                         'helper_built': (root / '.private/whatsapp-reader').is_file(),
                         'permissions': 'Grant macOS Accessibility/Screen Recording manually; polling remains stopped.'},
            'research': {name: importlib.util.find_spec(name) is not None for name in
                         ('numpy', 'pandas', 'vectorbt', 'openalgo', 'plotly', 'matplotlib', 'tqdm', 'dotenv')}}


if __name__ == '__main__':
    result = readiness()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(result['runtime_modules'].values()) else 1)
