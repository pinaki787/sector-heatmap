"""Last-good account-native MO master data; tokens never cross brokers."""
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import re
import threading
import time
from zoneinfo import ZoneInfo
from .config import _atomic_private_write
from .motilal_api import EXCHANGES,positive
from .motilal_feed import EPOCH_1980


def contract(row,exchange):
    if str(row.get('exchangename') or '').upper()!=exchange:raise ValueError('Native master exchange mismatch.')
    native_token=positive(row.get('scripcode'),'Native scrip code')
    if native_token!=int(native_token) or native_token>=2**31:raise ValueError('Native scrip code must be a supported whole number.')
    token=int(native_token)
    lots=positive(row.get('marketlot'),'Lot size')
    if lots!=int(lots):raise ValueError('Native lot size must be a whole number.')
    tick=positive(row.get('ticksize'),'Tick size')
    expiry=None
    raw=row.get('expirydate')
    if raw not in (None,'',0,'0'):
        try:
            if isinstance(raw,(int,float)) or str(raw).isdigit():
                expiry=datetime.fromtimestamp(float(raw)+EPOCH_1980,ZoneInfo('Asia/Kolkata')).date().isoformat()
            else:
                for fmt in ['%d-%b-%Y','%d/%m/%Y','%d-%m-%Y','%Y-%m-%d']:
                    try:expiry=datetime.strptime(str(raw),fmt).date().isoformat();break
                    except ValueError:pass
                if expiry is None:raise ValueError()
        except Exception:raise ValueError('Native expiry date could not be verified.') from None
        name=str(row.get('scripname') or row.get('scripfullname') or '')
        named=re.search(r'\b(\d{2}-[A-Za-z]{3}-\d{4})\b',name)
        if named and datetime.strptime(named.group(1),'%d-%b-%Y').date().isoformat()!=expiry:
            raise ValueError('Native expiry epoch and contract name disagree.')
    option_type=str(row.get('optiontype') or '').strip().upper()
    return dict(symbol=f'MO:{exchange}:{token}',exchange=exchange,token=token,name=str(row.get('scripfullname') or row.get('scripname') or ''),underlying=str(row.get('scripshortname') or '').strip().upper(),
                isin=str(row.get('scripisinno') or '').strip(),underlying_token=int(row.get('ultoken') or 0),lot_size=int(lots),tick_size=float(tick),instrument=str(row.get('instrumentname') or '').strip(),expiry=expiry,
                strike=float(row.get('strikeprice') or 0),option_type=option_type,
                suspended=str(row.get('issuspended') or '').upper()!='N',banned=str(row.get('isbanscrip') or '').upper()!='N',
                max_quantity=int(row.get('maxqtyperorder') or 0),native_quantity_unit='LOTS',order_quantity_multiplier=int(lots))


class Master:
    def __init__(self,folder,client,clock=time.time):
        self.folder=Path(folder);self.client=client;self.clock=clock;self.lock=threading.RLock();self.cache={}

    def indices(self,exchange):
        if exchange not in {'NSE','BSE'}:raise ValueError('Only native NSE/BSE indices are supported.')
        key='INDEX_'+exchange
        with self.lock:
            cached=self.cache.get(key)
            if cached and 0<=self.clock()-cached['observed_at']<86400:return cached['rows']
            raw=self.client.request('index_master',dict(exchangename=exchange)).get('data')
            if not isinstance(raw,list):raise ValueError('Native index master unavailable.')
            rows=[]
            for row in raw:
                code=positive(row.get('indexcode'),'Native index code')
                if row.get('exchangename')!=exchange or code!=int(code) or code>=2**31:raise ValueError('Invalid native index identity.')
                rows.append(dict(symbol=f'MO:INDEX:{exchange}:{int(code)}',exchange=exchange,token=int(code),name=row['indexname'],underlying=row['indexname'],instrument='INDEX',lot_size=None,tick_size=None))
            if len({r['token'] for r in rows})!=len(rows):raise ValueError('Ambiguous native index codes.')
            self.cache[key]=dict(observed_at=self.clock(),rows=rows)
            return rows

    def rows(self,exchange,refresh=False):
        if exchange not in EXCHANGES:raise ValueError('Unsupported Motilal exchange.')
        with self.lock:
            cached=self.cache.get(exchange)
            if not refresh and cached and cached.get('schema_version')==2 and 0<=self.clock()-cached['observed_at']<86400:return cached['rows']
            path=self.folder/(exchange+'.json')
            if not refresh and path.exists():
                saved=json.loads(path.read_text())
                if saved.get('schema_version')==2 and saved.get('exchange')==exchange and 0<=self.clock()-saved.get('observed_at',0)<86400:
                    self.cache[exchange]=saved;return saved['rows']
            response=self.client.request('instruments',dict(exchangename=exchange))
            raw=response.get('data')
            if not isinstance(raw,list) or not raw:raise ValueError('Motilal returned no native instrument master.')
            rows=[]
            for item in raw:
                try:rows.append(contract(item,exchange))
                except (ValueError,TypeError,KeyError):continue
            if not rows:raise ValueError('Motilal master contained no valid native contracts.')
            tokens=[row['token'] for row in rows]
            if len(tokens)!=len(set(tokens)):raise ValueError('Duplicate native scrip codes prevent master publication.')
            saved=dict(schema_version=2,exchange=exchange,observed_at=self.clock(),rows=rows)
            _atomic_private_write(path,json.dumps(saved,allow_nan=False));self.cache[exchange]=saved
            return rows

    def exact(self,symbol):
        parts=str(symbol).split(':')
        if len(parts)!=3 or parts[0]!='MO' or not parts[2].isdigit():raise ValueError('Select a Motilal-native instrument; another broker’s symbol/token is not accepted.')
        exchange=parts[1];token=int(parts[2])
        matches=[row for row in self.rows(exchange) if row['token']==token]
        if len(matches)!=1:raise ValueError('The exact native Motilal instrument is unavailable.')
        row=matches[0]
        if row['suspended'] or row['banned']:raise ValueError('Motilal marks this contract suspended or banned.')
        if row['expiry'] and row['expiry']<datetime.fromtimestamp(self.clock(),ZoneInfo('Asia/Kolkata')).date().isoformat():raise ValueError('The native contract has expired.')
        return dict(row)

    def search(self,query,exchange):
        text=str(query).strip().upper()
        if len(text)<2:return []
        return [dict(row) for row in self.rows(exchange) if text in row['name'].upper() or text in row['underlying']][:100]
