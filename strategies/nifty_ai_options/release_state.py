"""Read-only global and route-scoped activation status; never starts a runner."""
import json
from pathlib import Path
REVISION='option-legs-direct-reversal-v1'
PATH=Path('/home/trading/sector-heatmap/.private/nifty-ai-options/release-state.json')
def snapshot(path=PATH):
 try:
  if not path.exists():return dict(ready=True,revision=REVISION)
  value=json.loads(path.read_text())
  if not isinstance(value,dict):raise ValueError('Invalid release status')
  allowed=value.get('allowed_routes')
  if allowed is not None and (not isinstance(allowed,list) or not all(isinstance(r,str) for r in allowed)):raise ValueError('Invalid route status')
  return dict(ready=value.get('ready') is True,revision=REVISION,message=value.get('message') or 'AI execution update validation is in progress.',allowed_routes=allowed,route_notices=value.get('route_notices') if isinstance(value.get('route_notices'),dict) else {})
 except (OSError,ValueError):return dict(ready=False,revision=REVISION,message='AI execution release status is unavailable.')
def require_ready(config):
 if config.get('_managed_resume'):return
 status=snapshot()
 if not status['ready']:raise ValueError(status['message'])
 routes=status.get('allowed_routes')
 if routes is not None:
  key=str(config.get('broker'))+':'+str(config.get('execution_route','OPTIONS'))
  if key not in routes:raise ValueError(status.get('route_notices',{}).get(key) or 'This broker execution route has not completed release verification.')
