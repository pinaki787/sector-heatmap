"""Account-owned Dhan Screener research. No execution or shared credentials."""
from datetime import datetime
import math
from .dhan_execution import IST
from .dhan_sector_analysis import DhanSectorAnalysisService
from .analysis import calculate_timeframe_state, mtf_alignment
from .analysis_config import TIMEFRAMES
from .handoff import build_equity_opportunity, evidence_conviction
from .screener_paging import page_request, MAX_SYMBOLS

class DhanScreener:
    def __init__(self, execution):
        self.execution=execution
        self.service=DhanSectorAnalysisService(execution)
        self.service.provider.prepare()

    def quotes(self, symbols):
        mapped={}; errors=[]
        for ticker in dict.fromkeys(symbols):
            try:
                mapped[ticker]=self.service.provider.resolve('NSE:'+ticker+'-EQ')['securityId']
            except ValueError:
                errors.append(ticker)
        data={}
        if mapped:
            raw=self.service.provider._request('/marketfeed/quote',{'NSE_EQ':sorted({int(v) for v in mapped.values()})})
            if raw.get('status') not in (None,'success'):
                raise ValueError('Dhan quote snapshot was unsuccessful.')
            rows=raw.get('data',{}).get('NSE_EQ',{})
            stamp=datetime.now(IST).isoformat()
            for ticker,sid in mapped.items():
                row=rows.get(str(sid),{})
                try:
                    price=float(row['last_price']);previous=float(row['ohlc']['close'])
                    if not all(math.isfinite(v) and v>0 for v in (price,previous)):continue
                    volume=row.get('volume')
                    data[ticker]=dict(last_price=price,day_change=price-previous,day_change_pct=(price/previous-1)*100,
                                      provider_timestamp=stamp,quote_received_at=stamp,volume=volume if isinstance(volume,(int,float)) and math.isfinite(volume) and volume>=0 else None)
                except (KeyError,TypeError,ValueError):continue
        result=dict(market_data_schema=1,market_data=data,market_data_as_of=max((r['provider_timestamp'] for r in data.values()),default=None),
                    market_data_provider='DHAN_READ_ONLY',market_data_available=len(data),broker='DHAN',account_id=self.execution.account['id'])
        missing=len(set(symbols))-len(data)
        if missing:result['market_data_error']=f'Dhan quote or native mapping unavailable for {missing} candidate(s).'
        return result

    def refresh(self, payload, fetch_source, sectors):
        result=fetch_source(payload.get('url'))
        result.update(broker='DHAN',account_id=self.execution.account['id'],read_only=True)
        if result.get('status')=='READY':
            result.update(sectors(result.get('candidates',[]),result.get('source_sectors')))
            try:result.update(self.quotes(result.get('candidates',[])))
            except Exception:
                result.update(market_data_schema=1,market_data={},market_data_available=0,market_data_as_of=None,
                              market_data_provider='DHAN_READ_ONLY',market_data_error='Dhan quote enrichment unavailable. Membership retained; no alternate broker was used.')
        return result

    def analyze(self, payload):
        symbols,offset,limit,page,_,_=page_request(payload)
        service=self.service
        prices = self.quotes(page)['market_data']
        prices = {symbol: row['last_price'] for symbol,row in prices.items()}
        benchmark = service._timeframe_candles("NSE:NIFTY50-INDEX")
        rows = []
        with service.candidate_scan_lock:
            for ticker in page:
                from .persistent_jobs import checkpoint
                checkpoint("Analyzing "+ticker+" with selected Dhan evidence.", dict(status='PARTIAL',broker='DHAN',account_id=self.execution.account['id'],read_only=True,
                    results=list(rows),analyzed=len(rows),offset=offset,limit=limit,total=len(symbols),has_more=True,
                    operational_limits=dict(batch_size=12,maximum_symbols=MAX_SYMBOLS)))
                symbol = f"NSE:{ticker}-EQ"
                try:
                    if ticker not in prices:raise ValueError('Fresh selected-account Dhan quote unavailable.')
                    candles = service._timeframe_candles(symbol)
                    states = {timeframe: calculate_timeframe_state(timeframe, candles.get(timeframe, []), benchmark.get(timeframe, []), service._quality(timeframe, candles.get(timeframe, []))) for timeframe in TIMEFRAMES}
                    alignment = mtf_alignment(states)
                    qualities = [str(item.get("data_quality") or "UNAVAILABLE").upper() for item in states.values()]
                    stripped = {name: {key: value for key, value in item.items() if key != "series"} for name, item in states.items()}
                    if any(value in {"STALE", "UNAVAILABLE", "INSUFFICIENT DATA"} for value in qualities):
                        rows.append({"symbol": ticker, "decision": "REJECT", "reason": "Completed-candle evidence is stale, unavailable, or insufficient.", "alignment": alignment, "timeframe_states": stripped}); continue
                    if alignment not in {"FULL BULLISH ALIGNMENT", "FULL BEARISH ALIGNMENT"}:
                        rows.append({"symbol": ticker, "decision": "WATCHLIST", "reason": f"Requires full 15m, 1h, Daily and Weekly agreement; current state is {alignment}.", "alignment": alignment, "timeframe_states": stripped}); continue
                    direction = "BULLISH" if "BULLISH" in alignment else "BEARISH"
                    candidate = {"key": f"screener:{ticker}", "kind": "stock", "ticker": ticker, "name": ticker, "symbol": symbol, "direction": direction, "mtf_alignment": alignment,
                                 "data_quality": "READY", "price": prices.get(ticker), "timeframe_states": stripped}
                    opportunity = build_equity_opportunity(candidate, {"minimum_reward_to_risk": 2.0})
                    if opportunity.get("status") == "EXCLUDED":
                        rows.append({"symbol": ticker, "decision": "REJECT", "reason": opportunity.get("reason"), "alignment": alignment, "timeframe_states": stripped}); continue
                    stop = (opportunity.get("recommended_invalidation") or {}).get("price")
                    entry = opportunity.get("entry")
                    target = entry + 2 * (entry - stop) if direction == "BULLISH" and entry and stop else entry - 2 * (stop - entry) if entry and stop else None
                    opportunity["target"] = target if target else None
                    conviction = evidence_conviction(candidate, opportunity)
                    rows.append({"symbol": ticker, "decision": "PASS", "reason": opportunity.get("thesis"), "alignment": alignment, "direction": direction,
                                 "entry": entry, "stop": stop, "target": opportunity.get("target"), "reward_to_risk": 2.0, "conviction": conviction, "timeframe_states": stripped})
                except Exception as error:
                    rows.append({"symbol": ticker, "decision": "REJECT", "reason": str(error), "alignment": "UNAVAILABLE", "timeframe_states": {}})
        rank = {"PASS": 0, "WATCHLIST": 1, "REJECT": 2}
        rows.sort(key=lambda row: (rank[row["decision"]], -(row.get("conviction") or {}).get("score", 0), row["symbol"]))
        result = {"status": "READY", "broker":"DHAN", "account_id":self.execution.account["id"], "read_only":True, "offset": offset, "limit": limit, "total": len(symbols), "analyzed": len(page), "has_more": offset + len(page) < len(symbols), "results": rows,
                  "operational_limits": {"maximum_symbols": MAX_SYMBOLS, "batch_size": 12, "cache_seconds": 0, "background_polling": True},
                  "safeguards": "Decision support only. No candidate selection, packet, ticket, order, or broker mutation is created."}
        return result
