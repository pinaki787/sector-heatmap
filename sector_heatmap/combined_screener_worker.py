"""Account-isolated, rate-paced completed-candle screener; never trades."""
import argparse,json,os,time
from datetime import datetime
from pathlib import Path

from .sector_service import SectorAnalysisService,CandleHistoryProvider
from .fyers_transport import client as fyers_client
from .combined_screener_analysis import analyze
from .workspaces import private_write
from .market_calendar import IST
def owned_token(request):
 source=Path(__file__).resolve().parents[1];folder=source.parent
 if folder.name!=request["account_id"] or source.name!="source":raise ValueError("Incorrect isolated source")
 token_file=folder/"home/.fyers/token.json"
 if Path(os.environ.get("FYERS_TOKEN_FILE","")).resolve()!=token_file.resolve():raise ValueError("Token is not account scoped")
 profile=json.loads((folder/"credentials.json").read_text());cached=json.loads(token_file.read_text())
 app=profile.get("FYERS_APP_ID");cached_app=cached.get("app_id") or cached.get("client_id")
 if not app or app!=cached_app:raise ValueError("Broker app identity mismatch")
 token=cached.get("access_token") or cached.get("token")
 if not token:raise ValueError("Account token unavailable")
 return token if ":" in token else str(app)+":"+token
def build_service(token,output_path):
 app,value=token.split(":",1)
 logs=Path(output_path).parent/"sdk-logs";logs.mkdir(parents=True,exist_ok=True,mode=0o700)
 client=fyers_client(client_id=app,token=value,log_path=str(logs))
 return SectorAnalysisService("",state_file=Path(output_path).with_suffix(".history.json"),provider=CandleHistoryProvider(client))
def run(request_path,output_path,pace=3):
 request=json.loads(Path(request_path).read_text())
 if request["account_id"]!=os.environ.get("SECTOR_PULSE_WORKSPACE_ID") or request["broker"]!="FYERS":
  raise ValueError("Screener account mismatch")
 symbols=request["symbols"]
 if not 0<len(symbols)<=150 or len(symbols)!=len(set(symbols)):raise ValueError("Invalid saved screener universe")
 service=build_service(owned_token(request),output_path)
 started=datetime.now(IST).isoformat();rows=[];unavailable=0
 for offset,symbol in enumerate(symbols):
  cycle_started=time.monotonic()
  value=analyze({"symbols":[symbol],"limit":1,"prices":{}},service)
  rows.extend(value["results"])
  latest=value["results"][0] if value["results"] else {}
  unavailable=unavailable+1 if not latest.get("timeframe_states") or all(r.get("data_quality")=="UNAVAILABLE" for r in latest.get("timeframe_states",{}).values()) else 0
  result=dict(account_id=request["account_id"],broker="FYERS",status="UNAVAILABLE" if unavailable>=3 else "RUNNING" if offset+1<len(symbols) else "COMPLETED",
      started_at=started,generated_at=datetime.now(IST).isoformat(),analyzed=offset+1,total=len(symbols),
      universe_asof=request["universe_asof"],universe_basis="Last explicitly submitted screener universe; membership is not refreshed from Chartink",
      results=rows,decision_support_only=True,order_authority="NONE")
  private_write(output_path,json.dumps(result,allow_nan=False))
  if unavailable>=3:break
  if offset+1<len(symbols):time.sleep(max(0,pace-(time.monotonic()-cycle_started)))
def main():
 p=argparse.ArgumentParser();p.add_argument("--request",required=True);p.add_argument("--output",required=True);a=p.parse_args()
 try:run(a.request,a.output)
 except Exception as error:
  import traceback
  frames=[{"file":Path(f.filename).name,"line":f.lineno,"function":f.name} for f in traceback.extract_tb(error.__traceback__)]
  # Never persist provider exceptions, credentials, or private account context.
  from .workspaces import private_write
  private_write(a.output,json.dumps({"status":"UNAVAILABLE","generated_at":datetime.now(IST).isoformat(),"message":"Fresh screener analysis could not complete; check broker evidence.","error_type":type(error).__name__,"diagnostic_frames":frames}))
if __name__=="__main__":main()
