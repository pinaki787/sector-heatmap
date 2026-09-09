#!/usr/bin/env python3
"""Read-only Dhan snapshot for a COALINDIA ATM long-straddle assessment."""
from __future__ import annotations

import json
from pathlib import Path

import requests

SECURITY_ID = "20374"
CACHE = Path("/Users/pinaki/.dhan/access_token.json")


def credentials():
    data = json.loads(CACHE.read_text())
    return (str(data.get("dhanClientId") or data.get("client_id")),
            str(data.get("accessToken") or data.get("access_token")))


def main():
    client, token = credentials()
    headers = {"Accept": "application/json", "Content-Type": "application/json",
               "client-id": client, "access-token": token}
    session = requests.Session()
    quote = session.post("https://api.dhan.co/v2/marketfeed/quote", headers=headers,
        json={"NSE_EQ": [SECURITY_ID]}, timeout=20)
    chain = session.post("https://api.dhan.co/v2/optionchain", headers=headers,
        json={"UnderlyingScrip": SECURITY_ID, "UnderlyingSeg": "NSE_EQ"}, timeout=20)
    print("quote_status", quote.status_code)
    print(json.dumps(quote.json() if quote.ok else {"error": quote.text[:240]}, indent=2))
    print("chain_status", chain.status_code)
    print(json.dumps(chain.json() if chain.ok else {"error": chain.text[:240]}, indent=2))


if __name__ == "__main__":
    main()
