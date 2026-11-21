#!/usr/bin/env python3
"""Build unactivated, selective FYERS/Delta chart-order integration candidates."""
import ast,difflib,hashlib,json,sqlite3,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENTRY_FILES=["sector_heatmap/web.py","sector_heatmap/fyers_execution.py",
 "sector_heatmap/parser_lifecycle.py","sector_heatmap/parser_protection_broker.py",
 "strategies/nifty_call_credit_monitor/run.py","strategies/ema_crossover/runner.py",
 "strategies/long_straddle/sensex_straddle.py","strategies/long_straddle/nifty_straddle.py",
 "sector_heatmap/delta_india.py"]
KEYS=("chart_trade_admission","chart_trade_ownership","@serialized_","place_fyers_entry",
      "mark_entry_attempt","ChartOrderNotSent")

def sha(value):return hashlib.sha256(value.encode()).hexdigest()
def entry_changes(original,shared):
    old=original.splitlines(keepends=True);new=shared.splitlines(keepends=True);out=[];chosen=[]
    for kind,i,j,k,l in difflib.SequenceMatcher(None,old,new).get_opcodes():
        replacement="".join(new[k:l]);prior="".join(old[i:j])
        selected=kind!="equal" and (any(key in replacement+prior for key in KEYS)
             or ("/v2/orders/history" in replacement and "allowed=" in replacement)
             or ("fetch_fyers_chain(" in replacement and "now=self.now()" in replacement))
        out.extend(new[k:l] if selected else old[i:j])
        if selected:chosen.append(dict(before=prior,after=replacement))
    return "".join(out),chosen

def once(text,old,new):
    if text.count(old)!=1:raise ValueError("Candidate source anchor differs: "+old[:90])
    return text.replace(old,new,1)

def integrate_web(text):
    old="                self.send_json(200, workspace_guard.context(*self.workspace_identity) if workspace_guard else local_auth.context(self.headers) if local_auth else {'workspace': None}); return"
    new="""                context = workspace_guard.context(*self.workspace_identity) if workspace_guard else local_auth.context(self.headers) if local_auth else {'workspace': None}
                context["chart_trading_available"] = bool(workspace_guard and self.workspace_identity[1]["broker"] in {"FYERS","DELTA_INDIA"})
                context["chart_trading_products"] = ["MARGIN"] if workspace_guard and self.workspace_identity[1]["broker"]=="DELTA_INDIA" else ["INTRADAY","CNC","MARGIN","MTF"]
                self.send_json(200, context)
                return"""
    if old in text:
        text=once(text,old,new)
    else:
        start=text.index("            if self.path.split('?', 1)[0] == '/api/workspace-context':")
        end=text.index("            if workspace_guard and self.path.split('?', 1)[0] == '/workspace-entry':",start)
        block=text[start:end]
        lines='\n'.join(new.splitlines()[1:3])+'\n'
        block=once(block,"                self.send_json(200, context)\n",lines+"                self.send_json(200, context)\n")
        text=text[:start]+block+text[end:]
    old="                if workspace_guard: workspace_guard.validate_action(self.workspace_identity[1], path, payload)\n"
    new=old+"""                if path.startswith("/api/chart-workspace/trading/"):
                    from .chart_trading import handle as handle_chart_trading
                    if handle_chart_trading(self,path,payload,workspace_guard=workspace_guard,
                                            fyers_execution=fyers_execution,delta_execution=delta_india):
                        return
"""
    text=once(text,old,new)
    old='    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)\n'
    text=once(text,old,old+"""    from .chart_trading import resume_existing as resume_chart_orders, close_services as close_chart_orders
    resume_chart_orders(server,workspace_guard,fyers_execution,delta_india)
""")
    old="    finally:\n        if handoff_exit_monitor: handoff_exit_monitor.close()"
    text=once(text,old,"    finally:\n        close_chart_orders(server)\n        if handoff_exit_monitor: handoff_exit_monitor.close()")
    return text

def integrate_guard(text):
    anchor="        if path in ('/api/investment/analyze','/api/investment/seasonality/analyze'):return"
    index=text.index(anchor)
    branch="""        if path.startswith('/api/chart-workspace/trading/'):
            if (account['broker'] not in {'FYERS','DELTA_INDIA'} or path.rsplit('/',1)[-1] not in {'prepare','arm','status'}
                    or payload.get('account_id')!=account['id'] or payload.get('broker')!=account['broker']):
                raise PermissionError('Chart trading must use its exact private account and active broker adapter.')
            return
"""
    if "path.startswith('/api/chart-workspace/trading/')" in text:raise ValueError("Chart guard already exists.")
    return text[:index]+branch+text[index:]


def add_frontend(candidate,accounts,manifest):
    def page(text):
        if any(asset in text for asset in ("chart-trade-ticket.js","chart-trading.js","chart-trade-ticket.css")):
            raise ValueError("Order assets are already included; review the existing page.")
        text=once(text,'<link rel="stylesheet" href="/chart-workspace.css?v=301">',
                  '    <link rel="stylesheet" href="/chart-workspace.css?v=301">\n    <link rel="stylesheet" href="/chart-trade-ticket.css?v=1">\n')
        return once(text,'<script defer src="/chart-workspace.js?v=1931"></script>',
             '    <script defer src="/chart-trade-ticket.js?v=1"></script>\n'
             '    <script defer src="/chart-trading.js?v=1"></script>\n'
             '    <script defer src="/chart-workspace.js?v=1932"></script>')
    def save(owner,name,original,updated):
        path=candidate/owner/"source"/name
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(updated)
        manifest["files"].append(dict(workspace=owner,path=name,original_sha256=sha(original),
            candidate_sha256=sha(updated),changed=original!=updated))
    shared=(ROOT/"chart-workspace.js").read_text()
    for account in accounts:
        source=ROOT/".private/dashboard-login/accounts"/account["id"]/"source"
        original=(source/"chart-workspace.js").read_text()
        old=original.splitlines(keepends=True);new=shared.splitlines(keepends=True)
        differences=[(tag,i,j,k,l) for tag,i,j,k,l in difflib.SequenceMatcher(None,old,new).get_opcodes() if tag!="equal"]
        if len(differences)!=7 or any(tag!="insert" or "chartTrading" not in "".join(new[k:l])
                                      for tag,i,j,k,l in differences):
            raise ValueError("Unreviewed chart workspace differences need selective integration.")
        save(account["id"],"chart-workspace.js",original,shared)
        original=(source/"index.html").read_text();save(account["id"],"index.html",original,page(original))
    original=(ROOT/"index.html").read_text();save("main","index.html",original,page(original))
    for owner in [a["id"] for a in accounts]+["main"]:
        active=ROOT if owner=="main" else ROOT/".private/dashboard-login/accounts"/owner/"source"
        for name in ("chart-trade-ticket.js","chart-trade-ticket.css","chart-trading.js"):
            original=(active/name).read_text();updated=(ROOT/name).read_text()
            if original!=updated:raise ValueError("Staged order asset drift: "+name)
            save(owner,name,original,updated)



def main():
    registry=ROOT/".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
        accounts=[dict(zip(("id","broker"),row)) for row in db.execute("SELECT id,broker FROM accounts WHERE broker IN ('FYERS','DELTA_INDIA')")]
    parent=ROOT/".private/chart-order-rollouts";parent.mkdir(parents=True,exist_ok=True)
    candidate=Path(tempfile.mkdtemp(prefix="candidate-",dir=parent))
    manifest=dict(status="CANDIDATE_ONLY",active_sources_changed=False,files=[],accounts=accounts,
        limitations=["Entry-guard coverage and integration acceptance pending; not ready for reload.",
                     "No index inclusion, live flags, worker reload or broker actions."])
    for account in accounts:
        source=registry.parent/"accounts"/account["id"]/"source"
        output=candidate/account["id"]/"source"
        for name in ENTRY_FILES+["sector_heatmap/workspace_guard.py"]:
            original=(source/name).read_text()
            if name=="sector_heatmap/workspace_guard.py":updated=integrate_guard(original);hunks=[]
            else:
                updated,hunks=entry_changes(original,(ROOT/name).read_text())
                if name=="sector_heatmap/web.py":updated=integrate_web(updated)
            ast.parse(updated,filename=name)
            target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(updated)
            manifest["files"].append(dict(workspace=account["id"],path=name,
                original_sha256=sha(original),candidate_sha256=sha(updated),entry_hunks=len(hunks),
                changed=original!=updated))
    add_frontend(candidate,accounts,manifest)
    (candidate/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(dict(candidate=str(candidate),files=len(manifest["files"]),status=manifest["status"])))
if __name__=="__main__":main()
