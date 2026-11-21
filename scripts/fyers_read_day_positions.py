"""Read-only current FYERS identity and day positions."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from sector_heatmap.fyers_execution import _current_client
c = _current_client()
p = c.get_profile()
d = p.get("data") or {}
print(json.dumps({"checked_at":datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),"profile_status":p.get("s"),"account_name":d.get("name"),"account_id":d.get("fy_id"),"positions":c.positions()},default=str))
