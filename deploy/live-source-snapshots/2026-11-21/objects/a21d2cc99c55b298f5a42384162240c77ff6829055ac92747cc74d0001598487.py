"""Isolated FYERS read-only provider for scheduled Handoff analysis."""
from datetime import datetime
from types import SimpleNamespace
import time
from .market_calendar import IST
from .handoff import FyersCmMaster,FyersFoMaster,fetch_fyers_chain,build_long_option_proposals
from .fyers_execution import _current_client,_fresh_depth_quote
from .sector_service import SectorAnalysisService

class Provider:
    broker="FYERS"
    def __init__(self,account,folder):
        self.folder=folder
        self.execution=SimpleNamespace(account=account)
        self.client=_current_client()
        from .config import load_config
        self.sectors=SectorAnalysisService(load_config()["FYERS_ACCESS_TOKEN"],
            state_file=folder/"source/.private/handoff-analysis-history.json")
        self.cash_master=FyersCmMaster();self.option_master=FyersFoMaster()
        self.live=[];self.refreshed=0

    def candidates(self,mode):
        if time.monotonic()-self.refreshed>=300:
            self.sectors.refresh()
            self.refreshed=time.monotonic()
        return self.sectors.alignment_candidates(self.live_sectors(),mode=mode)

    def live_sectors(self):
        """Read constituent attribution directly from the existing broker connection."""
        from .sectors import SECTOR_DEFINITIONS,equity_symbol
        symbols=list(dict.fromkeys([s.symbol for s in SECTOR_DEFINITIONS]+
            [equity_symbol(c.ticker) for s in SECTOR_DEFINITIONS for c in s.constituents]))
        quotes={}
        for offset in range(0,len(symbols),50):
            response=self.client.quotes({"symbols":",".join(symbols[offset:offset+50])})
            if not isinstance(response,dict) or response.get("s")!="ok" or not isinstance(response.get("d"),list):
                raise ValueError("Fresh FYERS constituent quotes unavailable; verify broker authentication.")
            for row in response["d"]:
                if row.get("s")=="ok" and isinstance(row.get("v"),dict):
                    quotes[row.get("n")]=row["v"]
        rows=[]
        for sector in SECTOR_DEFINITIONS:
            drivers=[]
            for c in sector.constituents:
                q=quotes.get(equity_symbol(c.ticker),{})
                change=q.get("chp")
                if not isinstance(change,(int,float)):continue
                drivers.append(dict(ticker=c.ticker,name=c.name,weight=c.weight,
                    price=q.get("lp"),change=change,contribution=c.weight*change/100))
            if sector.constituents and not drivers:
                raise ValueError("FYERS sector constituent evidence unavailable; no automatic entry.")
            rows.append(dict(sector_id=sector.sector_id,change=quotes.get(sector.symbol,{}).get("chp"),drivers=drivers))
        return rows

    def positions(self):
        value=self.client.positions()
        if not isinstance(value,dict) or value.get("s")!="ok" or not isinstance(value.get("netPositions"),list):
            raise ValueError("Fresh FYERS positions unavailable for Handoff.")
        return value["netPositions"]

    def orders(self):
        value=self.client.orderbook()
        if not isinstance(value,dict) or value.get("s")!="ok" or not isinstance(value.get("orderBook"),list):
            raise ValueError("Fresh FYERS order book unavailable for Handoff.")
        return value["orderBook"]

    def quote(self,symbol):
        quote=_fresh_depth_quote(self.client,symbol,datetime.now(IST))
        return quote["ltp"],quote["provider_timestamp"]

    def tick(self,symbol):
        row=self.cash_master.lookup([symbol]).get(symbol)
        if not row:raise ValueError("Exact FYERS cash contract missing from current master.")
        return row["tick_size"]

    def options(self,symbol,direction,risk):
        chain,expiry=fetch_fyers_chain(self.client,symbol)
        symbols=[r.get("symbol") for r in (chain.get("data") or {}).get("optionsChain",[]) if r.get("symbol")]
        return build_long_option_proposals(chain,expiry,self.option_master.lookup(symbols),direction,risk)
