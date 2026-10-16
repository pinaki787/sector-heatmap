"""Owner-scoped Dhan API-key consent; no execution or runner operations."""
import hashlib
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .workspaces import private_write

def request_json(path, credentials, query, method="GET"):
    req=Request("https://auth.dhan.co/app/"+path+"?"+urlencode(query),
                headers={"app_id":credentials["DHAN_API_KEY"],"app_secret":credentials["DHAN_API_SECRET"]},
                method=method)
    try:
        with urlopen(req,timeout=20) as response:
            data=json.loads(response.read(65536))
    except Exception:
        raise ValueError("Dhan authorization request failed. Check the API key and secret or retry later.") from None
    if not isinstance(data,dict):
        raise ValueError("Dhan returned an invalid authorization response.")
    return data

def login(store,runtime,user,aid,token_id=None):
    account=store.account(user,aid)
    if account["broker"]!="DHAN":
        raise ValueError("Select a saved Dhan account.")
    # Same-account token renewal is supported by DhanExecutionService._client.
    # API keys, account identity and Live capabilities remain unchanged.
    with runtime.lock:
        folder=store.folder(account)
        path=folder/"credentials.json"
        credentials=json.loads(path.read_text()) if path.exists() else {}
        if not credentials.get("DHAN_API_KEY") or not credentials.get("DHAN_API_SECRET"):
            raise ValueError("Save the Dhan API key and secret first.")
        pending=folder/"dhan-consent.json"
        binding=hashlib.sha256(user["csrf"].encode()).hexdigest()
        if token_id is None:
            data=request_json("generate-consent",credentials,{"client_id":account["account_ref"]},"POST")
            consent=data.get("consentAppId")
            if not isinstance(consent,str) or not consent or data.get("status")!="success":
                raise ValueError("Dhan did not create a login consent.")
            private_write(pending,json.dumps({"binding":binding,"created":time.time()}))
            return {"url":"https://auth.dhan.co/login/consentApp-login?"+urlencode({"consentAppId":consent})}
        state=json.loads(pending.read_text()) if pending.exists() else {}
        if state.get("binding")!=binding or time.time()-state.get("created",0)>900:
            raise ValueError("Dhan login expired or belongs to another session. Start Connect to Dhan again.")
        if not isinstance(token_id,str) or not token_id.strip() or len(token_id)>4096:
            raise ValueError("Missing Dhan callback token.")
        data=request_json("consumeApp-consent",credentials,{"tokenId":token_id})
        if str(data.get("dhanClientId",""))!=account["account_ref"]:
            raise ValueError("Dhan returned a different account. Credentials were not changed.")
        token=data.get("accessToken")
        if not isinstance(token,str) or not token or any(c in token for c in "\r\n\x00"):
            raise ValueError("Dhan did not return an access token.")
        store.configure(user,aid,{"DHAN_ACCESS_TOKEN":token},bool(account["live_enabled"]))
        pending.unlink(missing_ok=True)
        return {"connected":True,"expiry":data.get("expiryTime"),"account_id":aid}
