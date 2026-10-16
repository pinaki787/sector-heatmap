"""Explicit owner-bound FYERS history; never an execution or native capture source."""
import csv,hashlib,json,math,threading,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from .config import _atomic_private_write
from .fyers_history import history
IST=ZoneInfo('Asia/Kolkata')

def source_settings(payload):
    enabled=payload.get('fyers_history_enabled',False)
    if not isinstance(enabled,bool):raise ValueError('FYERS history must be explicitly ON or OFF.')
    aid=str(payload.get('fyers_history_account_id') or '')
    if (enabled or aid) and (len(aid)!=32 or any(c not in '0123456789abcdef' for c in aid)):
        raise ValueError('Select your FYERS history account when enabling historical candles.')
    return dict(fyers_history_enabled=enabled,fyers_history_account_id=aid)

def exact_history_symbol(native,rows):
    exchange=native['exchange']
    if exchange=='MCX':
        matches=[r for r in rows if len(r)>16 and r[13]==native['underlying'] and r[16]=='XX'
                 and datetime.fromtimestamp(float(r[8]),IST).date().isoformat()==native['expiry']]
    else:
        symbol=native.get('history_symbol')
        matches=[r for r in rows if len(r)>16 and r[9]==symbol]
        if not matches and exchange=='BSE' and native.get('isin'):
            matches=[r for r in rows if len(r)>16 and r[9].startswith('BSE:') and r[12]==str(native['token']) and r[13]==native['underlying'] and r[5]==native['isin']]
    if len(matches)!=1:raise ValueError('Exact FYERS historical underlying is missing or ambiguous; no substituted contract.')
    return matches[0][9]

def verified_minutes(raw,now,rejected=None):
    result={};conflicts=set()
    for row in raw:
        if not isinstance(row,list) or len(row)<6:raise ValueError('FYERS historical candle format is invalid.')
        stamp=int(row[0]);prices=[float(v) for v in row[1:5]];volume=float(row[5])
        if stamp!=row[0] or stamp%60 or any(not math.isfinite(v) or v<=0 for v in prices) or not math.isfinite(volume) or volume<0:
            raise ValueError('FYERS historical candle contains invalid prices or time.')
        o,h,l,c=prices
        if h<max(o,l,c) or l>min(o,h,c):
            if rejected is None:raise ValueError('FYERS historical OHLC is inconsistent; history source blocked.')
            rejected.append(dict(timestamp=stamp,raw=row,reason='Inconsistent OHLC'));continue
        if stamp+60>now:continue
        value=dict(timestamp=stamp,open=o,high=h,low=l,close=c,volume=volume,volume_available=True,source='FYERS_EXPLICIT_HISTORY',is_forming=False)
        if stamp in conflicts:continue
        if stamp in result and result[stamp]!=value:
            previous=result[stamp]
            if all(previous[k]==value[k] for k in ('open','high','low','close')):
                previous.update(volume=None,volume_available=False);continue
            if rejected is None:raise ValueError('FYERS history contains conflicting duplicate candles.')
            rejected.append(dict(timestamp=stamp,raw=[previous,row],reason='Conflicting duplicate OHLC'));result.pop(stamp);conflicts.add(stamp);continue
        result[stamp]=value
    return sorted(result.values(),key=lambda r:r['timestamp'])

def aggregate(minutes,interval,session_open,now):
    hour,minute=map(int,session_open.split(':'));groups={}
    for row in minutes:
        stamp=datetime.fromtimestamp(row['timestamp'],IST);anchor=int(stamp.replace(hour=hour,minute=minute,second=0,microsecond=0).timestamp())
        if row['timestamp']<anchor:continue
        opening=anchor+(row['timestamp']-anchor)//interval*interval;groups.setdefault(opening,[]).append(row)
    result=[]
    for opening,parts in sorted(groups.items()):
        if opening+interval>now or [r['timestamp'] for r in parts]!=list(range(opening,opening+interval,60)):continue
        result.append(dict(timestamp=opening,open=parts[0]['open'],high=max(r['high'] for r in parts),low=min(r['low'] for r in parts),close=parts[-1]['close'],volume=sum(r['volume'] for r in parts) if all(r.get('volume_available') for r in parts) else None,source='FYERS_EXPLICIT_HISTORY',is_forming=False,volume_available=all(r.get('volume_available') for r in parts)))
    return result

class Seed:
    def __init__(self,store,user,target,clock=time.time,client_factory=None):
        self.store=store;self.user=dict(id=user['id']);self.target=target;self.clock=clock;self.client_factory=client_factory;self.lock=threading.RLock();self.evidence={}
    def account_id(self,selected=''):
        accounts=[a for a in self.store.accounts(self.user) if a['broker']=='FYERS']
        if selected:
            account=self.store.account(self.user,selected)
            if account['broker']!='FYERS':raise PermissionError('Historical source must be your own FYERS account.')
            return account['id']
        if len(accounts)!=1:raise ValueError('Exactly one FYERS account must be configured for this user before enabling historical candles.')
        return accounts[0]['id']
    def candles(self,config,native,interval,session_open):
        settings=source_settings(config)
        if not settings['fyers_history_enabled']:raise ValueError('FYERS history is OFF; no historical request permitted.')
        aid=settings['fyers_history_account_id'];account=self.store.account(self.user,aid)
        if account['broker']!='FYERS':raise PermissionError('Historical source must be your own FYERS account.')
        folder=self.store.folder(account);segment='MCX_COM' if native['exchange']=='MCX' else native['exchange']+'_CM'
        master=folder/'source/.private/ema-band-masters'/(segment+'.csv')
        if not master.exists() or not 0<=self.clock()-master.stat().st_mtime<86400:raise ValueError('Refresh this FYERS account’s instrument master before using historical candles.')
        with master.open() as handle:symbol=exact_history_symbol(native,list(csv.reader(handle)))
        key=hashlib.sha256((aid+'|'+native['symbol']+'|'+symbol).encode()).hexdigest()
        path=self.store.folder(self.target)/'motilal-history-seeds'/(key+'.json')
        with self.lock:
            saved=json.loads(path.read_text()) if path.exists() else None
            if saved and (saved.get('source_account_id')!=aid or saved.get('native_symbol')!=native['symbol'] or saved.get('fyers_symbol')!=symbol):raise ValueError('Historical archive identity mismatch.')
            if not saved or not 0<=self.clock()-saved['downloaded_at']<60:
                token_path=folder/'home/.fyers/token.json'
                if not token_path.exists():raise ValueError('Connect the selected FYERS history account first.')
                token=json.loads(token_path.read_text());app_id=token.get('app_id');access=token.get('access_token')
                if not app_id or not access:raise ValueError('FYERS history account has no usable session.')
                if self.client_factory:client=self.client_factory(app_id,access)
                else:
                    from fyers_apiv3.fyersModel import FyersModel
                    client=FyersModel(client_id=app_id,token=access,log_path='')
                now=self.clock();response=history(client,dict(symbol=symbol,resolution='1',date_format='0',range_from=str(int(now-12*86400)),range_to=str(int(now)),cont_flag='0'))
                if response.get('s')!='ok':raise ValueError('Selected FYERS history request failed; no silent native fallback while ON.')
                rejected=[]
                minutes=verified_minutes(response.get('candles') or [],now,rejected)
                original_rejections=list(rejected)
                repair_attempts=[];by_time={r['timestamp']:r for r in minutes}
                for stamp in sorted({r['timestamp'] for r in rejected})[-12:]:
                    repaired=False
                    try:
                        reply=history(client,dict(symbol=symbol,resolution='1',date_format='0',range_from=str(stamp),range_to=str(stamp+59),cont_flag='0'))
                        if reply.get('s')=='ok':
                            candidates=[r for r in verified_minutes(reply.get('candles') or [],now) if r['timestamp']==stamp]
                            if len(candidates)==1:by_time[stamp]=candidates[0];repaired=True
                    except (ValueError,RuntimeError):pass
                    repair_attempts.append(dict(timestamp=stamp,repaired=repaired))
                    if repaired:rejected=[r for r in rejected if r['timestamp']!=stamp]
                minutes=sorted(by_time.values(),key=lambda r:r['timestamp'])
                dates=sorted({datetime.fromtimestamp(r['timestamp'],IST).date().isoformat() for r in minutes})[-5:]
                minutes=[r for r in minutes if datetime.fromtimestamp(r['timestamp'],IST).date().isoformat() in dates]
                if not minutes:raise ValueError('FYERS returned no completed historical candles for this exact contract.')
                saved=dict(schema_version=1,source='FYERS_EXPLICIT_HISTORY',source_account_id=aid,native_symbol=native['symbol'],fyers_symbol=symbol,native_expiry=native.get('expiry'),downloaded_at=now,session_dates=dates,candles=minutes,rejected_candles=rejected,original_rejected_candles=original_rejections,repair_attempts=repair_attempts)
                saved['candles_sha256']=hashlib.sha256(json.dumps(minutes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                _atomic_private_write(path,json.dumps(saved,allow_nan=False))
            expected=hashlib.sha256(json.dumps(saved['candles'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if saved.get('candles_sha256')!=expected:raise ValueError('Historical archive checksum failed.')
            rejected=saved.get('rejected_candles',[])
            boundary=max((r['timestamp'] for r in rejected),default=0)
            usable=[r for r in saved['candles'] if r['timestamp']>boundary]
            self.evidence[(aid,native['symbol'])]=dict(archived_minutes=len(saved['candles']),unknown_volume_candles=sum(not r.get('volume_available') for r in saved['candles']),rejected_candles=len(rejected),usable_after=boundary or None,session_dates=saved['session_dates'])
            return aggregate(usable,interval,session_open,self.clock())
