"""Read-only verification of Delta India's fixed settlement conversion policy."""
import html
import json
import math
from pathlib import Path
import re
import threading
import time
import requests
SOURCE='https://www.delta.exchange/support/solutions?articleId=80001200076&categoryId=80000463147&folderId=80000717765'
LOCK=threading.Lock()
ATTEMPTS={}

def policy(path,now=None,fetch=None):
    fetch=fetch or requests.get
    now=time.time() if now is None else now
    path=Path(path)
    with LOCK:
        try:
            p=json.loads(path.read_text())
            if p.get('source')==SOURCE and p.get('native_currency')=='USD' and p.get('equivalent_currency')=='INR' and type(p.get('rate')) in (int,float) and math.isfinite(p['rate']) and p['rate']>0 and 0<=now-p['verified_at']<=86400:return p
        except (OSError,ValueError,KeyError,TypeError):pass
        if now-ATTEMPTS.get(str(path),float('-inf'))<900:return None
        ATTEMPTS[str(path)]=now
        try:
            response=fetch(SOURCE,timeout=8);response.raise_for_status()
            if response.url.split('/')[2]!='www.delta.exchange':raise ValueError('Unexpected policy source')
            text=html.unescape(re.sub('<[^>]+>',' ',response.text))
            match=re.search(r'USD-INR rate on the platform is fixed at\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*i\.e\.\s*1 USD\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*INR',text)
            if not match or match[1]!=match[2]:return None
            rate=float(match[1])
            if not math.isfinite(rate) or rate<=0:return None
            p=dict(rate=rate,native_currency='USD',equivalent_currency='INR',basis='Delta India fixed platform settlement conversion; not market FX',source=SOURCE,verified_at=now,valid_for_seconds=86400)
            path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(p));temp.replace(path)
            return p
        except (requests.RequestException,OSError,ValueError,AttributeError):return None
