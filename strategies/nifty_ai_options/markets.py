"""Selected-market metadata and completed source bars. No execution side effects."""
import csv,io,math,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
IST=ZoneInfo('Asia/Kolkata')

class FyersInstrumentMaster:
    def __init__(self,directory):self.directory=Path(directory);self.rows={};self.loaded={}
    def __call__(self,symbol):
        exchange=str(symbol).split(':')[0]
        if exchange not in ('NSE','BSE','MCX'):raise ValueError('Unsupported FYERS exchange')
        segment='MCX_COM' if exchange=='MCX' else exchange+('_FO' if symbol.endswith(('FUT','CE','PE')) else '_CM')
        today=datetime.now(IST).date().isoformat()
        if self.loaded.get(segment)!=today:
            r=requests.get('https://public.fyers.in/sym_details/'+segment+'.csv',timeout=(5,30));r.raise_for_status()
            self.rows.update({x[9]:x for x in csv.reader(io.StringIO(r.text)) if len(x)>16})
            self.directory.mkdir(parents=True,exist_ok=True);(self.directory/(segment+'.csv')).write_text(r.text);self.loaded[segment]=today
        row=self.rows.get(symbol)
        if not row or symbol.endswith('-INDEX'):raise ValueError('Exact tradable stock/future is required, not an index')
        expiry=float(row[8]) if row[8] else None
        product='FUTURE' if row[16]=='XX' and expiry else 'STOCK' if exchange in ('NSE','BSE') and (symbol.endswith('-EQ') or row[2]=='0') else None
        if not product:raise ValueError('Selected master instrument is not a direct stock/future')
        lot=float(row[3]);tick=float(row[4])
        if not math.isfinite(lot) or not lot.is_integer() or lot<1 or not math.isfinite(tick) or tick<=0:raise ValueError('Invalid daily-master lot/tick')
        bounds=str(row[6]).split('|')[0].split('-')
        if len(bounds)!=2 or any(len(x)!=4 or not x.isdigit() for x in bounds):raise ValueError('Verified regular-session bounds unavailable')
        opening,closing=[int(x[:2])*60+int(x[2:]) for x in bounds]
        if not 0<=opening<closing<=1440:raise ValueError('Invalid regular-session bounds')
        return dict(symbol=symbol,lot_size=int(lot),tick_size=tick,product_type=product,expiry_epoch=expiry,
            opening_minutes=opening,closing_minutes=closing,master_regular_session='-'.join(bounds),exchange=exchange,exchange_code=row[10],segment_code=row[11],underlying_asset=row[13])

def margin_reader(raw):
    def calculate(order):
        response=raw._sector_pulse_ipv4_session.post('https://api-t1.fyers.in/api/v3/multiorder/margin',headers={'Authorization':raw.header},json={'data':[order]},timeout=10)
        response.raise_for_status();reply=response.json()
        if reply.get('s')!='ok':raise ValueError('FYERS margin calculation unavailable')
        data=reply.get('data',reply);value=data.get('margin_total')
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<0:raise ValueError('Required margin unknown')
        return value
    return calculate

class SourceBars:
    """Full completed bars, anchored to verified regular session or UTC for crypto."""
    def __init__(self,frame,*,continuous=False,opening_minutes=None,closing_minutes=None,zone=IST,confirmed_closes=False):
        if frame not in (1,5,30):raise ValueError('Source timeframe must be 1/5/30')
        if not continuous and (opening_minutes is None or closing_minutes is None):raise ValueError('Verified regular-session bounds required')
        self.seconds=frame*60;self.continuous=continuous;self.opening=opening_minutes;self.closing=closing_minutes;self.zone=zone
        self.confirmed_closes=confirmed_closes
        self.bucket=self.close=self.last=None;self.complete=False
    def update(self,stamp,price):
        if self.last is not None and stamp<self.last:raise ValueError('Out-of-order provider tick')
        self.last=stamp
        if self.continuous:bucket=int(stamp//self.seconds)*self.seconds
        else:
            dt=datetime.fromtimestamp(stamp,self.zone);minute=dt.hour*60+dt.minute
            if not self.opening<=minute<self.closing:return None
            anchor=dt.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()+self.opening*60
            bucket=anchor+int((stamp-anchor)//self.seconds)*self.seconds
        if bucket==self.bucket:self.close=price;return None
        previous=None
        if self.bucket is not None:
            if bucket-self.bucket!=self.seconds:raise ValueError('Source stream gap; halt and reconcile history')
            if self.complete:previous=(self.bucket,self.close)
        self.complete=(self.confirmed_closes or stamp-bucket<=2) if self.bucket is None else True
        self.bucket,self.close=bucket,price
        return previous
