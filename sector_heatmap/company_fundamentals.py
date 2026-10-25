"""Bounded, cached public NSE filing evidence. No technical-to-fundamental inference."""
from datetime import datetime,date,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import hashlib,json,math,os,re,sqlite3,time
import requests
class Rows(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None;self.depth=0
 def handle_starttag(self,t,a):
  if t=='tr' and self.row is None:self.row=[]
  if t in ('td','th') and self.row is not None:
   if self.cell is None:self.cell=[];self.depth=1
   else:self.depth+=1
 def handle_data(self,d):
  if self.cell is not None:self.cell.append(d)
 def handle_endtag(self,t):
  if t in ('td','th') and self.cell is not None:
   self.depth-=1
   if self.depth==0:self.row.append(' '.join(' '.join(self.cell).split()));self.cell=None
  if t=='tr' and self.row is not None and self.cell is None:self.rows.append(self.row);self.row=None
def norm(s):return re.sub('[^a-z0-9]','',str(s).lower())
def numeric(s):
 try:
  s=str(s).replace(',','').replace(' ','');negative=s.startswith('(') and s.endswith(')');v=float(s.strip('()'))*(-1 if negative else 1)
  return v if math.isfinite(v) else None
 except (ValueError,TypeError):return None
def parse_filing(html,symbol,period):
 p=Rows();p.feed(html);rows=p.rows
 def field(label):
  for row in rows:
   for i,c in enumerate(row):
    if norm(c)==norm(label):return next((v for v in row[i+1:] if v.strip()),None)
  return None
 if field('NSE Symbol')!=symbol:raise ValueError('NSE filing company identity mismatch.')
 units=field('Level of rounding used in financial results');currency=field('Description of presentation currency')
 if currency!='INR' or norm(units) not in ('lakhs','crores','rupees','millions'):raise ValueError('Exact filing currency/scale unavailable.')
 end=field('Date of end of reporting period')
 if not end or datetime.strptime(end,'%d-%m-%Y').date().isoformat()!=period:raise ValueError('Filing reporting period mismatch.')
 scale={'lakhs':.01,'crores':1.,'rupees':1e-7,'millions':.1}[norm(units)]
 names={'revenue_crore':'Revenue from operations','profit_crore':'Total profit (loss) for period','finance_cost_crore':'Finance costs','eps_inr':'Basic earnings (loss) per share from continuing and discontinued operations','debt_equity':'Debt equity ratio'}
 values={}
 for key,label in names.items():
  value=numeric(field(label))
  values[key]=None if value is None else round(value if key in ('eps_inr','debt_equity') else value*scale,4)
 if values.get('revenue_crore') and values.get('profit_crore') is not None:values['reported_profit_margin_pct']=round(values['profit_crore']/values['revenue_crore']*100,4)
 return dict(metrics=values,scope=field('Nature of report standalone or consolidated'),source_units=units,currency=currency)

class Provider:
 def __init__(self,workspace,clock=time.time,get=None):
  self.clock=clock;self.get=get or self.download
  registry=os.getenv('SECTOR_PULSE_WORKSPACE_REGISTRY');folder=Path(registry).parent if registry else Path(workspace)/'.private'
  folder.mkdir(parents=True,exist_ok=True);self.path=folder/'public-company-fundamentals.sqlite3'
  with self.db() as d:d.execute('CREATE TABLE IF NOT EXISTS evidence(symbol TEXT PRIMARY KEY,at REAL,body TEXT)')
 def db(self):return sqlite3.connect(self.path,timeout=10)
 @staticmethod
 def download(url):
  u=urlparse(url)
  if u.scheme!='https' or u.hostname not in ('www.nseindia.com','nsearchives.nseindia.com') or u.username or u.password:raise ValueError('Unapproved public filing host.')
  with requests.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/html','Referer':'https://www.nseindia.com/'},timeout=(3,6),allow_redirects=False,stream=True) as r:
   if r.status_code!=200:raise ValueError('Public exchange source returned HTTP '+str(r.status_code)+'.')
   chunks=[];size=0
   for part in r.iter_content(16384):
    size+=len(part)
    if size>1500000:raise ValueError('Public filing response exceeds bounded size.')
    chunks.append(part)
   return b''.join(chunks).decode('utf-8')
 def evidence(self,underlying):
  if not isinstance(underlying,str) or not re.fullmatch(r'NSE:[A-Z0-9&_-]+-EQ',underlying):
   return dict(status='NOT_APPLICABLE' if underlying and any(x in underlying for x in ('INDEX','MCX:','USD','BTC')) else 'UNAVAILABLE',symbol=underlying,reason='No verified NSE company identity; indices, commodities and derivatives are not assigned company ratios.',metrics={},relationship='INSUFFICIENT_EVIDENCE')
  symbol=underlying[4:-3]
  with self.db() as d:r=d.execute('SELECT at,body FROM evidence WHERE symbol=?',(symbol,)).fetchone()
  if r and 0<=self.clock()-r[0]<(86400 if json.loads(r[1]).get('status') in ('AVAILABLE','PARTIAL') else 21600):return json.loads(r[1])
  now=datetime.fromtimestamp(self.clock(),timezone.utc);out=dict(schema='company-fundamentals/v1',symbol=underlying,as_of=now.isoformat(),provider='NSE company Integrated Filing',status='UNAVAILABLE',metrics={},sources=[],missing=['Growth comparison','Valuation/TTM P/E','Cash flow','Balance-sheet debt/equity'],relationship='INSUFFICIENT_EVIDENCE')
  try:
   url='https://www.nseindia.com/api/integrated-filing-results?index=equities&symbol='+symbol
   response=json.loads(self.get(url));rows=response.get('data',[]) if isinstance(response,dict) else []
   eligible=[]
   for row in rows:
    if row.get('symbol')!=symbol or row.get('type')!='Integrated Filing- Financials' or not row.get('ixbrl'):continue
    try:day=datetime.strptime(row['qe_Date'],'%d-%b-%Y').date()
    except (KeyError,ValueError):continue
    if day<=now.date():eligible.append((day,row.get('consolidated')=='Consolidated',row))
   if not eligible:raise ValueError('No dated company financial filing returned by the current NSE endpoint.')
   day,_,row=max(eligible,key=lambda v:(v[0],v[1],str(v[2].get('broadcast_Date') or '')))
   source=row['ixbrl'];u=urlparse(source)
   if u.hostname!='nsearchives.nseindia.com' or not u.path.startswith('/corporate/ixbrl/INTEGRATED_FILING_') or not u.path.lower().endswith('.html'):raise ValueError('Unsupported exchange filing reference.')
   out.update(period_end=day.isoformat(),filing_at=row.get('broadcast_Date'),company_name=row.get('cmName') or row.get('smName'),scope=row.get('consolidated'),audited=row.get('audited'),sources=[dict(title='NSE Integrated Filing — '+str(row.get('consolidated')),url=source),dict(title='NSE filing metadata',url=url)])
   html=self.get(source);parsed=parse_filing(html,symbol,day.isoformat());out.update(parsed,source_sha256=hashlib.sha256(html.encode()).hexdigest())
   out['status']='STALE' if (now.date()-day).days>180 else 'PARTIAL' if any(v is None for v in parsed['metrics'].values()) or out['missing'] else 'AVAILABLE'
   out['reason']='Latest returned filing is older than 180 days.' if out['status']=='STALE' else 'Reported profitability is available; growth comparison, full solvency and valuation are incomplete. No cheap/expensive or financial-health conclusion is inferred from technical prices.'
  except Exception as e:out['reason']=str(e) if isinstance(e,ValueError) else 'Public exchange filing data unavailable; no figures were fabricated.'
  with self.db() as d:d.execute('INSERT OR REPLACE INTO evidence VALUES(?,?,?)',(symbol,self.clock(),json.dumps(out,allow_nan=False)))
  return out
