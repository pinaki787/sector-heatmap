"Notification-free OAuth routing; worker validates the full one-time state."
import re
def account_from_state(value):
 if not isinstance(value,str):return None
 match=re.fullmatch(r'([a-f0-9]{32})\.([A-Za-z0-9_-]{32,128})',value)
 return match.group(1) if match else None
