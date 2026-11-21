"""Verify deployed helper against the saved 205-trade research candidate, offline."""
import sys,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"backtesting/renko_regime_risk"))
import run as risk
import replay
from zones import contexts
from strategies.renko_supertrend import zone_entry
def main():
 risk.initialize();known=contexts(risk.HOSTS);replay.EXITS["Fixed3_1_5"]=dict(hard=3.,target=1.5)
 config={**risk.CONFIG,"calibrated_enabled":True,"calibrated_overlap_pairs":6,"calibrated_overlap_max":.4,"calibrated_stop_atr":3.,"calibrated_target_atr":1.5,"zones_family_enabled":True,"zone_target_enabled":True}
 gate=lambda sig,price:zone_entry.check_known(known[sig["timestamp"]]["after"],dict(zone_entry_enabled=True,zone_entry_min_atr=1.,zone_entry_rearm=True),sig["entry_direction"],price,sig["host_atr"])["allowed"]
 r=replay.simulate(risk.HOSTS,risk.MINUTES,config,"Baseline","Fixed3_1_5",risk.START,entry_filter=gate,recovery=True,rearm=True,zone_context=known,zone_exits=True)
 old=json.loads((HERE/"trials/zone_added_rearm_1ATR.json").read_text())
 keys=("entry_at","entry_price","direction","exit_at","exit_price","gross_points")
 assert [{k:t[k]for k in keys}for t in r["trades"]]==[{k:t[k]for k in keys}for t in old["trades"]]
 result=dict(exact_trade_match=True,trades=len(r["trades"]),summary=r["splits"]["all"]["2"])
 (HERE/"implementation-parity.json").write_text(json.dumps(result,indent=2));print(result)
if __name__=="__main__":main()
