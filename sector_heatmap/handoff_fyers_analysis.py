"""Isolated FYERS read-only provider for scheduled Handoff analysis."""
from datetime import datetime
from types import SimpleNamespace
import time
import hashlib
from .market_calendar import IST
from .handoff import FyersCmMaster,FyersFoMaster,fetch_fyers_chain,build_long_option_proposals
from .fyers_execution import _current_client,_fresh_depth_quote
from .sector_service import SectorAnalysisService

class Provider:
    broker="FYERS"
    def __init__(self,account,folder,*,state_dir=None):
        from .config import load_config
        token=load_config().get("FYERS_ACCESS_TOKEN", "")
        self._session_digest=hashlib.sha256(token.encode()).digest()
        self.folder=folder
        self.execution=SimpleNamespace(account=account)
        self.screener_state_dir=state_dir
        candle_provider=None
        if state_dir is None:
            self.client=_current_client()
        else:
            from .fyers_transport import client
            from .sector_service import CandleHistoryProvider
            self.client=_current_client(
                lambda client_id,value:client(client_id=client_id,token=value,log_path=str(state_dir)))
            candle_provider=CandleHistoryProvider(self.client)
        from .config import load_config
        self.sectors=SectorAnalysisService(load_config()["FYERS_ACCESS_TOKEN"],
            state_file=folder/"source/.private/handoff-analysis-history.json",provider=candle_provider)
        self.cash_master=FyersCmMaster();self.option_master=FyersFoMaster()
        self.live=[];self.refreshed=0

    def refresh_session(self):
        """Reuse the account's current saved token; invalidate only analysis caches."""
        from .config import load_config
        token=load_config().get("FYERS_ACCESS_TOKEN", "")
        revision=hashlib.sha256(token.encode()).digest()
        if revision == self._session_digest:
            return False
        updated=type(self)(self.execution.account,self.folder,**({"state_dir":self.screener_state_dir} if hasattr(self,"screener_state_dir") else {}))
        self.__dict__.update(updated.__dict__)
        return True

    def candidates(self,mode):
        self.refresh_session()
        if time.monotonic()-self.refreshed>=300:
            self.sectors.refresh()
            self.refreshed=time.monotonic()
        live=self.live_sectors()
        return self.sectors.alignment_candidates(live,mode=mode)

    def live_sectors(self):
        """Read constituent attribution directly from the existing broker connection."""
        self.refresh_session()
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
        self.refresh_session()
        value=self.client.positions()
        if not isinstance(value,dict) or value.get("s")!="ok" or not isinstance(value.get("netPositions"),list):
            raise ValueError("Fresh FYERS positions unavailable for Handoff.")
        return value["netPositions"]

    def orders(self):
        self.refresh_session()
        value=self.client.orderbook()
        if not isinstance(value,dict) or value.get("s")!="ok" or not isinstance(value.get("orderBook"),list):
            raise ValueError("Fresh FYERS order book unavailable for Handoff.")
        return value["orderBook"]

    def quote(self,symbol):
        self.refresh_session()
        quote=_fresh_depth_quote(self.client,symbol,datetime.now(IST))
        return quote["ltp"],quote["provider_timestamp"]

    def tick(self,symbol):
        row=self.cash_master.lookup([symbol]).get(symbol)
        if not row:raise ValueError("Exact FYERS cash contract missing from current master.")
        return row["tick_size"]

    def options(self,symbol,direction,risk):
        self.refresh_session()
        chain,expiry=fetch_fyers_chain(self.client,symbol)
        symbols=[r.get("symbol") for r in (chain.get("data") or {}).get("optionsChain",[]) if r.get("symbol")]
        return build_long_option_proposals(chain,expiry,self.option_master.lookup(symbols),direction,risk)
