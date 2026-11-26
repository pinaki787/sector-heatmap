import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from release_state import snapshot,require_ready
class ReleaseRoutes(unittest.TestCase):
 def test_verified_routes_are_independent_of_an_unreleased_broker_route(self):
  state=dict(ready=True,allowed_routes=['FYERS:DIRECT','FYERS:OPTIONS','DHAN:DIRECT','DHAN:OPTIONS','DELTA_INDIA:DIRECT','MOTILAL_OSWAL:OPTIONS'],route_notices={'MOTILAL_OSWAL:DIRECT':'Motilal direct order type requires a decision.'})
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'release.json';path.write_text(json.dumps(state));actual=snapshot(path)
   with patch('release_state.snapshot',return_value=actual):
    for route in state['allowed_routes']:
     broker,execution_route=route.split(':');require_ready(dict(broker=broker,execution_route=execution_route))
    with self.assertRaisesRegex(ValueError,'order type requires'):require_ready(dict(broker='MOTILAL_OSWAL',execution_route='DIRECT'))
    with self.assertRaises(ValueError):require_ready(dict(broker='DELTA_INDIA',execution_route='OPTIONS'))
 def test_global_hold_and_malformed_state_still_block(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'release.json'
   for content in ['[]','{','{"ready":true,"allowed_routes":"all"}','{"ready":false,"message":"Validation hold"}']:
    path.write_text(content)
    with patch('release_state.snapshot',return_value=snapshot(path)):
     with self.assertRaises(ValueError):require_ready(dict(broker='FYERS',execution_route='DIRECT'))
