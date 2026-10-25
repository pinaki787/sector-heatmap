"""Read-only reuse of dashboard screener analysis; no ticket or execution paths."""
from .analysis import calculate_timeframe_state,mtf_alignment
from .analysis_config import TIMEFRAMES
from .handoff import build_equity_opportunity,evidence_conviction
def analyze(payload,service):
    """Bounded advisory analysis of explicit Chartink members; never creates order authority."""
    from .screener_paging import page_request, MAX_SYMBOLS
    symbols, offset, limit, page, prices, cache_key = page_request(payload)
    if not service.provider:
        raise RuntimeError("FYERS authentication is required for completed-candle screener analysis.")
    import time as time_module
    benchmark = service._timeframe_candles("NSE:NIFTY50-INDEX")
    rows = []
    with service.candidate_scan_lock:
        for ticker in page:
            from .persistent_jobs import checkpoint
            checkpoint("Analyzing "+ticker+" with selected-broker evidence.")
            symbol = f"NSE:{ticker}-EQ"
            try:
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
                opportunity["target"] = round(target, 2) if target else None
                conviction = evidence_conviction(candidate, opportunity)
                rows.append({"symbol": ticker, "decision": "PASS", "reason": opportunity.get("thesis"), "alignment": alignment, "direction": direction,
                             "entry": entry, "stop": stop, "target": opportunity.get("target"), "reward_to_risk": 2.0, "conviction": conviction, "timeframe_states": stripped})
            except Exception as error:
                rows.append({"symbol": ticker, "decision": "REJECT", "reason": str(error), "alignment": "UNAVAILABLE", "timeframe_states": {}})
    rank = {"PASS": 0, "WATCHLIST": 1, "REJECT": 2}
    rows.sort(key=lambda row: (rank[row["decision"]], -(row.get("conviction") or {}).get("score", 0), row["symbol"]))
    result = {"status": "READY", "offset": offset, "limit": limit, "total": len(symbols), "analyzed": len(page), "has_more": offset + len(page) < len(symbols), "results": rows,
              "operational_limits": {"maximum_symbols": MAX_SYMBOLS, "batch_size": 12, "cache_seconds": 300, "background_polling": True},
              "safeguards": "Decision support only. No candidate selection, packet, ticket, order, or broker mutation is created."}
    return result

