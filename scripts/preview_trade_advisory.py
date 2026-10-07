"""Isolated UI fixture preview. GET-only server; no broker or OpenAI calls."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
fields = ('price_action', 'support_resistance', 'supply_demand', 'breakout_volume', 'entry',
          'targets_partial_profits', 'initial_stop', 'trailing_stop', 'reward_risk',
          'volume_vwap_momentum', 'relative_strength_sector')
fixture = {'status': 'READY', 'advisory_only': True, 'message': 'TEST FIXTURE — color and layout verification only. No market verdict or broker request.',
           'intraday': {'verdict': 'PASS', 'reasons': ['Fixture: completed price structure supports the example plan.'], 'missing_evidence': [],
                        **{f: 'Fixture only: conditional analysis appears here.' for f in fields}},
           'swing': {'verdict': 'FAIL', 'reasons': ['Fixture: the example contract expires before the proposed holding period.'], 'missing_evidence': [],
                     **{f: 'Fixture only: conditional analysis appears here.' for f in fields}}}
page = '''<!doctype html><html><head><meta charset="utf-8"><title>Trade Parser advisory verification</title><style>
body{background:#0b121c;color:#e2e8f0;font:16px system-ui;margin:32px auto;max-width:1050px;padding:0 20px}p{line-height:1.5}h3{margin:8px 0}summary{cursor:pointer}button{padding:10px;margin:8px;border-radius:8px}
</style></head><body><h1>Trade Parser · advisory feedback</h1><p>Isolated UI verification — no order routes</p><div id="result"></div><div id="unavailable"></div><script src="/trade-parser-advisory.js"></script><script>
SectorPulseTradeAdvisory.render(document.getElementById('result'), FIXTURE);
SectorPulseTradeAdvisory.render(document.getElementById('unavailable'), {advisory_only:true,message:'AI feedback skipped: AI is not connected.'});
</script></body></html>'''.replace('FIXTURE);', json.dumps(fixture) + ');')
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            body, kind = page.encode(), 'text/html'
        elif self.path == '/trade-parser-advisory.js':
            body, kind = (ROOT / 'trade-parser-advisory.js').read_bytes(), 'text/javascript'
        else:
            self.send_error(404)
            return
        self.send_response(200); self.send_header('Content-Type', kind); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass
if __name__ == '__main__':
    HTTPServer(('127.0.0.1', 8097), Handler).serve_forever()
