from pathlib import Path
import sys,json,requests
ROOT=Path('/home/trading/sector-heatmap');sys.path.insert(0,str(ROOT))
from sector_heatmap.network_policy import install_ipv4_only
install_ipv4_only()
for aid in ['b0041912d9d6f68d352814cbd24bf6da','fd46b26f73022af571be11b1027c5291','1b0a63fa2d371d3be413763078d21bbc']:
 p=ROOT/'.private/dashboard-login/accounts'/aid/'credentials.json'
 if not p.exists():continue
 c=json.loads(p.read_text())
 try:
  r=requests.get('https://api.dhan.co/v2/profile',headers={'access-token':c.get('DHAN_ACCESS_TOKEN',''),'client-id':c.get('DHAN_CLIENT_ID','')},timeout=10)
  d=r.json();print(json.dumps({'account':aid,'http':r.status_code,'dataPlan':d.get('dataPlan'),'validity':d.get('dataValidity')}))
 except Exception as e:print(aid,type(e).__name__)
