#!/usr/bin/env python3
"""Read-only, account-scoped FYERS day P&L and option-cost snapshot."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json
import os
import sqlite3
import sys

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workspace",required=True)
    parser.add_argument("--brokerage",type=float,default=15.0)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    registry=root/".private/dashboard-login/registry.sqlite3"
    with sqlite3.connect(registry.as_uri()+"?mode=ro",uri=True) as db:
        row=db.execute("SELECT broker FROM accounts WHERE id=?",(args.workspace,)).fetchone()
    if not row or row[0]!="FYERS":
        raise RuntimeError("The selected workspace is not FYERS.")
    folder=registry.parent/"accounts"/args.workspace
    source=folder/"source"
    sys.path.insert(0,str(source))
    os.environ.update(SECTOR_PULSE_WORKSPACE_REGISTRY=str(registry),SECTOR_PULSE_WORKSPACE_ID=args.workspace,
                      FYERS_TOKEN_FILE=str(folder/"home/.fyers/token.json"))
    from sector_heatmap.config import load_config
    from sector_heatmap.web import ipv4_fyers_client,estimate_fyers_trade_charges
    token=load_config().get("FYERS_ACCESS_TOKEN","")
    if ":" not in token:raise RuntimeError("A reusable FYERS session is unavailable.")
    app_id,access_token=token.split(":",1)
    client=ipv4_fyers_client(client_id=app_id,token=access_token)
    positions=client.positions()
    trades=client.tradebook()
    for name,result in (("positions",positions),("tradebook",trades)):
        if result.get("s")!="ok":raise RuntimeError(name+" unavailable: "+str(result.get("message")))
    rows=trades.get("tradeBook") or trades.get("tradebook") or trades.get("data") or []
    now=datetime.now(ZoneInfo("Asia/Kolkata"))
    fills=[]
    dates=set()
    for item in rows:
        stamp=str(item.get("orderDateTime") or item.get("tradeDateTime") or "")
        if stamp:dates.add(stamp.split(" ")[0])
        fills.append(item)
    net_positions=positions.get("netPositions") or []
    gross=sum(float(r.get("pl") or 0) for r in net_positions)
    realized=sum(float(r.get("realized_profit") or 0) for r in net_positions)
    unrealized=sum(float(r.get("unrealized_profit") or 0) for r in net_positions)
    charge=estimate_fyers_trade_charges(fills)
    # Published FYERS NSE options schedule, checked 18 November 2026.
    # Keep clearing distinct from exchange fees and include SEBI in the GST base.
    from decimal import Decimal
    D=lambda value: Decimal(str(value or 0))
    option_fills=[r for r in fills if str(r.get("symbol","")).startswith("NSE:") and str(r.get("symbol","")).endswith(("CE","PE"))]
    option_turnover=sum((abs(D(r.get("tradeValue"))) for r in option_fills),Decimal(0))
    option_sell=sum((abs(D(r.get("tradeValue"))) for r in option_fills if int(r.get("side") or 0)<0),Decimal(0))
    option_buy=option_turnover-option_sell
    option_orders=len({str(r.get("orderNumber") or r.get("exchangeOrderNo") or "row:"+str(r.get("row"))) for r in option_fills})
    fees={"brokerage":D(args.brokerage)*option_orders,
          "stt":option_sell*D("0.0015"),
          "exchange":option_turnover*D("0.000355299"),
          "clearing":option_turnover*D("0.00009"),
          "sebi":option_turnover*D("0.000001"),
          "ipft":option_turnover*D("0.000000001"),
          "stamp":option_buy*D("0.00003")}
    fees["gst"]=(fees["brokerage"]+fees["exchange"]+fees["clearing"]+fees["sebi"]+fees["ipft"])*D("0.18")
    option_cost=sum(fees.values())
    option_realized=sum((D(r.get("realized_profit")) for r in net_positions if str(r.get("symbol","")).startswith("NSE:") and str(r.get("symbol","")).endswith(("CE","PE"))),Decimal(0))
    precise_options={"realized_gross":round(float(option_realized),2),
                     "brokerage_only_net":round(float(option_realized-fees["brokerage"]),2),
                     "estimated_all_costs_net":round(float(option_realized-option_cost),2),
                     "estimated_costs":round(float(option_cost),2),"executed_orders":option_orders,
                     "turnover":round(float(option_turnover),2),"buy_turnover":round(float(option_buy),2),
                     "sell_turnover":round(float(option_sell),2),"fees":{k:round(float(v),2) for k,v in fees.items()}}
    standard_brokerage=charge["breakdown"]["brokerage"]
    brokerage=args.brokerage*charge["orders"]
    reduction=standard_brokerage-brokerage
    estimated_cost=round(charge["total"]-reduction*1.18,2)
    breakdown=charge["breakdown"]
    breakdown["brokerage"]=round(brokerage,2)
    breakdown["gst"]=round(breakdown["gst"]-reduction*0.18,2)
    unsupported=[r.get("symbol") for r in fills if not (str(r.get("symbol","")).startswith(("NSE:","MCX:")) and str(r.get("symbol","")).endswith(("CE","PE")))]
    out={"as_of_ist":now.isoformat(timespec="seconds"),"nse_options_current_schedule":precise_options,"gross_pnl":round(gross,2),"realized_pnl":round(realized,2),
         "unrealized_pnl":round(unrealized,2),"estimated_charges":estimated_cost,"estimated_net_pnl":round(gross-estimated_cost,2),
         "brokerage_per_executed_order":args.brokerage,"executed_orders":charge["orders"],"fill_count":len(fills),
         "trade_dates":sorted(dates),"charges_breakdown":breakdown,"unsupported_cost_symbols":sorted(set(unsupported)),
         "open_positions":[{k:r.get(k) for k in ("symbol","netQty","pl","realized_profit","unrealized_profit")} for r in net_positions if float(r.get("netQty") or 0)],
         "positions":[{k:r.get(k) for k in ("symbol","netQty","buyQty","sellQty","buyAvg","sellAvg","pl","realized_profit","unrealized_profit")} for r in net_positions],
         "cash_fills":[{k:r.get(k) for k in ("symbol","qty","tradePrice","tradeValue","side","productType")} for r in fills if str(r.get("symbol","")).endswith("-EQ")],
         "estimated":True,"final_costs_source":"broker contract note"}
    print(json.dumps(out,indent=2))

if __name__=="__main__":main()

