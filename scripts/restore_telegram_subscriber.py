"""Restore a verified legacy reader into exactly one owner's Delta workspace; never starts."""
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sector_heatmap.telegram_migration import migration_plan,restore
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--owner",required=True);p.add_argument("--account",required=True);p.add_argument("--apply",action="store_true");p.add_argument("--legacy-stopped-confirmed",action="store_true");a=p.parse_args()
 plan=migration_plan(Path(__file__).resolve().parents[1],a.owner,a.account)
 if not a.apply:print(json.dumps(dict(eligible=True,identity_and_access_verification_required=True,credentials_copied=False)));return
 print(json.dumps(asyncio.run(restore(plan,a.legacy_stopped_confirmed))))
if __name__=="__main__":
 try:main()
 except Exception as e:raise SystemExit(str(e) if isinstance(e,ValueError) else "Reader restoration failed; secrets suppressed. Nothing armed.")
