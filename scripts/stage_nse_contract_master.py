"""Archive primary NSE daily contract evidence for historical research only."""
import argparse,json
from pathlib import Path
import requests
from strategies.renko_supertrend.nse_contract_lots import archive,source_url
def main():
    p=argparse.ArgumentParser();p.add_argument('--date',required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1]
    url=source_url(a.date);r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=25);r.raise_for_status()
    print(json.dumps(archive(root,a.date,r.content,url),indent=2))
if __name__=='__main__':main()
