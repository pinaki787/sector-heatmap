"""Screener-only execution scope; no order or activation authority."""
def eligible_rows(rows, report):
    scopes=[x.get("scope",{}).get("screener",{}) for x in report.get("analysis_scopes",[])]
    if not scopes or any(s.get("status")!="COMPLETED" or not s.get("enabled") or not s.get("auto_enabled") for s in scopes):
        raise ValueError("Complete fresh selected Screener analysis is required; no Auto entry.")
    return [r for r in rows if r.get("kind")=="EQUITY" and any(p.get("kind")=="SCREENER" for p in r.get("provenance",[]))]
