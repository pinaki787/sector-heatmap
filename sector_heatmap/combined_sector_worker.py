"""Read-only sector MTF collector using dashboard calculations; no execution imports."""
import argparse,json,os
from datetime import datetime
from pathlib import Path
from .combined_screener_worker import owned_token,build_service
from .analysis import calculate_timeframe_state,mtf_alignment
from .analysis_config import TIMEFRAMES
from .sectors import SECTOR_DEFINITIONS,BENCHMARK_SYMBOL
from .market_calendar import IST
from .workspaces import private_write

def collect(service):
 benchmark=service._timeframe_candles(BENCHMARK_SYMBOL);rows=[]
 for sector in SECTOR_DEFINITIONS:
  try:candles=service._timeframe_candles(sector.symbol)
  except Exception:candles={}
  frames={}
  for tf in TIMEFRAMES:
   value=calculate_timeframe_state(tf,candles.get(tf,[]),benchmark.get(tf,[]),service._quality(tf,candles.get(tf,[])))
   frames[tf]={k:value.get(k) for k in ("state","label","data_quality","last_updated","missing_components")}
  rows.append(dict(sector_id=sector.sector_id,timeframe_states=frames,mtf_alignment=mtf_alignment(frames)))
 return dict(status="COMPLETED",generated_at=datetime.now(IST).isoformat(),source="FYERS completed candles / dashboard sector calculations",timeframes=list(TIMEFRAMES),sectors=rows,order_authority="NONE")
def run(request_path,output_path):
 request=json.loads(Path(request_path).read_text())
 if request.get("account_id")!=os.environ.get("SECTOR_PULSE_WORKSPACE_ID") or request.get("broker")!="FYERS":raise ValueError("Sector report account mismatch")
 service=build_service(owned_token(request),output_path)
 private_write(output_path,json.dumps(collect(service),allow_nan=False))
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--request",required=True);parser.add_argument("--output",required=True);a=parser.parse_args()
 try:run(a.request,a.output)
 except Exception:private_write(a.output,json.dumps(dict(status="UNAVAILABLE",generated_at=datetime.now(IST).isoformat(),sectors=[],order_authority="NONE")))
if __name__=="__main__":main()
