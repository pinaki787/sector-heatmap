"""Isolated Delta India market data, paper ledger and explicitly started live execution."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode,quote
import hashlib,hmac,json,math,os,re,secrets,shlex,threading,time
import requests
from strategies.ema_crossover.signals import rsi_sma_series
from . import delta_trailing

BASE='https://api.india.delta.exchange'
RESOLUTIONS={'1m':60,'3m':180,'5m':300,'15m':900,'30m':1800,'1h':3600,'2h':7200,'4h':14400,'6h':21600,'1d':86400,'1w':604800}
SUPPORTED={'perpetual_futures','futures','call_options','put_options'}

class DeltaIndia:
    def __init__(self,state_path,credentials=lambda:{},requester=None,clock=time.time):
        self.path=Path(state_path);self.credentials=credentials;self.requester=requester or requests;self.clock=clock
        self.lock=threading.RLock();self.cache={};self.previews={};self.auth_state='NOT_CHECKED';self.paper={'schema':1,'position':None,'trades':[]}
        self.auth_at=0;self.auth_identity=None;self.live_path=self.path.with_name('delta-india-live.json');self.key_path=self.path.with_name('delta-india-credentials.json')
        self.live={'schema':1,'orders':{},'runner_position':None};self.runner={'running':False,'message':'Stopped','last_candle':None};self.stop_event=threading.Event()
        self.corrupt=False
        if self.live_path.exists():
            try:
                self.live=json.loads(self.live_path.read_text());assert self.live['schema']==1 and isinstance(self.live['orders'],dict)
            except Exception:self.corrupt=True
        if self.live.get('runner_config'):
            self.runner.update(config=self.live['runner_config'],pending=self.live.get('runner_pending'),action=self.live.get('runner_action'))
        if self.path.exists():
            try:
                state=json.loads(self.path.read_text());assert state.get('schema')==1 and isinstance(state.get('trades'),list);self.paper=state
            except Exception:self.corrupt=True
    def _get(self,path,params=None,private=False):
        if private:return self._private('GET',path,params=params)
        if path not in ('/v2/products','/v2/history/candles','/v2/wallet/balances') and not re.fullmatch(r'/v2/(products|tickers)/[A-Z0-9][A-Z0-9_-]{0,79}',path):raise ValueError('Unsupported Delta India read-only endpoint.')
        query='?'+urlencode(params) if params else '';headers={'Accept':'application/json','User-Agent':'SectorPulse-DeltaIndia/1.0'}
        try:
            response=self.requester.get(BASE+path+query,headers=headers,timeout=15,allow_redirects=False)
            if response.status_code!=200:raise ValueError('Delta India read request failed (HTTP '+str(response.status_code)+').')
            data=response.json()
        except ValueError:raise
        except Exception:raise ValueError('Delta India read request unavailable; retry later.') from None
        if not isinstance(data,dict) or data.get('success') is not True:raise ValueError('Delta India rejected the read request; verify service availability or configured credentials.')
        return data
    def _credentials(self):
        local={}
        shared=Path.home()/'.delta-exchange-mcp/config.env'
        if shared.exists():
            values={}
            for line in shared.read_text().splitlines():
                name,sep,raw=line.partition('=')
                if not sep or name.strip() not in ('DELTA_API_KEY','DELTA_API_SECRET','DELTA_MCP_ENV'):continue
                try:parts=shlex.split(raw,comments=True);values[name.strip()]=parts[0] if len(parts)==1 else ''
                except ValueError:continue
            if values.get('DELTA_MCP_ENV','india_prod')=='india_prod':
                local={target:values.get(source) for source,target in [('DELTA_API_KEY','DELTA_INDIA_API_KEY'),('DELTA_API_SECRET','DELTA_INDIA_API_SECRET')] if values.get(source)}
        if self.key_path.exists():
            try:local=json.loads(self.key_path.read_text())
            except Exception:pass
        return {**local,**self.credentials(),**{k:v for k,v in os.environ.items() if k in ('DELTA_INDIA_API_KEY','DELTA_INDIA_API_SECRET','DELTA_INDIA_ENABLE_LIVE_ORDERS')}}
    def _identity(self):
        c=self._credentials();return hashlib.sha256((str(c.get('DELTA_INDIA_API_KEY',''))+'|'+str(c.get('DELTA_INDIA_API_SECRET',''))).encode()).hexdigest()
    def _gate(self):
        return str(self._credentials().get('DELTA_INDIA_ENABLE_LIVE_ORDERS','1')).lower() in ('1','true','yes')
    def status(self):
        c=self._credentials();configured=bool(c.get('DELTA_INDIA_API_KEY') and c.get('DELTA_INDIA_API_SECRET'))
        verified=configured and self.auth_identity==self._identity() and self.auth_state=='VERIFIED_READ_ONLY'
        fresh=verified and 0<=self.clock()-self.auth_at<=60
        return dict(broker='DELTA_INDIA',environment='INDIA_PRODUCTION',base_url=BASE,mode='READ_ONLY / PAPER / LIVE',running=self.runner['running'],live_capability=True,live_gate_enabled=self._gate(),live_available=bool(verified and self._gate() and not self.corrupt),authentication_fresh=bool(fresh),authentication_verified_at=self.auth_at if verified else None,credentials='CONFIGURED' if configured else 'MISSING',authentication=self.auth_state if verified else ('MISSING' if not configured else 'RECHECK_ON_ACTION'),forex_supported=False,message='LIVE Submit and Start perform fresh authentication and validation. Broker enforces Trading permission and margin. No automatic activation.',paper=deepcopy(self.paper),paper_state_available=not self.corrupt,orders=deepcopy(list(self.live['orders'].values())),runner=deepcopy(self.runner),runner_position=deepcopy(self.live['runner_position']))
    def configure(self,payload):
        with self.lock:
            if self.runner['running'] or self.live['runner_position'] or any(o['status'] in ('SUBMITTING','UNKNOWN','open','pending','CANCEL_UNKNOWN') for o in self.live['orders'].values()):raise ValueError('Stop runner and reconcile outstanding owned orders before changing credentials.')
            key=payload.get('api_key');secret=payload.get('api_secret')
            if not isinstance(key,str) or not isinstance(secret,str) or not 8<=len(key)<=512 or not 8<=len(secret)<=512 or any(c.isspace() for c in key+secret):raise ValueError('Enter the India API key and secret in local Connection settings.')
            self._private('GET','/v2/wallet/balances',credentials={'DELTA_INDIA_API_KEY':key,'DELTA_INDIA_API_SECRET':secret})
            self._write(self.key_path,{'DELTA_INDIA_API_KEY':key,'DELTA_INDIA_API_SECRET':secret,'DELTA_INDIA_ENABLE_LIVE_ORDERS':'1'})
            self.verify_auth()
            mcp_path=self.path.with_name('delta-india-mcp.env');mcp_path.parent.mkdir(parents=True,exist_ok=True);tmp=mcp_path.with_suffix('.tmp')
            with tmp.open('w') as f:
                os.chmod(tmp,0o600);f.write('DELTA_MCP_ENV=india_prod\nDELTA_API_KEY='+json.dumps(key)+'\nDELTA_API_SECRET='+json.dumps(secret)+'\n');f.flush();os.fsync(f.fileno())
            os.replace(tmp,mcp_path);return self.status()
    def _private(self,method,path,params=None,body=None,credentials=None):
        allowed=(method=='GET' and (path in ('/v2/wallet/balances','/v2/positions','/v2/positions/margined','/v2/fills') or re.fullmatch(r'/v2/orders/client_order_id/[a-zA-Z0-9_-]{1,32}',path))) or (method in ('POST','DELETE') and path=='/v2/orders')
        if not allowed:raise ValueError('Unsupported Delta India authenticated endpoint.')
        c=credentials or self._credentials();key,secret=c.get('DELTA_INDIA_API_KEY'),c.get('DELTA_INDIA_API_SECRET')
        if not key or not secret:raise PermissionError('Delta India is not connected. Enter India API key and secret in Connection settings.')
        query='?'+urlencode(params) if params else '';encoded=json.dumps(body,separators=(',',':'),allow_nan=False) if body is not None else '';stamp=str(int(self.clock()))
        signature=hmac.new(secret.encode(),(method+stamp+path+query+encoded).encode(),hashlib.sha256).hexdigest()
        headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'SectorPulse-DeltaIndia/1.0','api-key':key,'timestamp':stamp,'signature':signature}
        try:
            kwargs=dict(headers=headers,timeout=15,allow_redirects=False)
            if body is not None:kwargs['data']=encoded
            response=getattr(self.requester,method.lower())(BASE+path+query,**kwargs)
            data=response.json()
        except Exception:raise ConnectionError('Delta India request outcome unavailable; reconcile before any new submission.') from None
        if response.status_code not in (200,201) or not isinstance(data,dict) or data.get('success') is not True:
            code=((data.get('error') or {}).get('code') if isinstance(data,dict) else None)
            safe=code if isinstance(code,str) and re.fullmatch(r'[a-zA-Z0-9_]{1,80}',code) else 'request_rejected'
            if response.status_code in (401,403):self.auth_state='FAILED';self.auth_at=0
            if method!='GET' and response.status_code>=500:raise ConnectionError('Delta India mutation outcome unknown; reconcile before retrying.')
            raise ValueError('Delta India '+safe+' (HTTP '+str(response.status_code)+').')
        return data
    def verify_auth(self):
        try:
            data=self._private('GET','/v2/wallet/balances');assert isinstance(data['result'],list)
            self.auth_state='VERIFIED_READ_ONLY';self.auth_at=self.clock();self.auth_identity=self._identity()
        except Exception:self.auth_state='FAILED';self.auth_at=0;raise
        return self.status()
    def account(self,payload=None):
        wallets=self._private('GET','/v2/wallet/balances')['result']
        positions=self._private('GET','/v2/positions/margined')['result']
        return {'funds':[ {k:r.get(k) for k in ('asset_symbol','balance','available_balance','blocked_margin')} for r in wallets], 'positions':[ {k:r.get(k) for k in ('product_id','product_symbol','size','entry_price')} for r in positions], 'basis':'Broker-reported native asset values; no conversion or estimated margin. Margined position snapshot may lag fills; execution uses real-time product positions.'}
    def _write(self,path,data):
        path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
        with tmp.open('w') as f:os.chmod(tmp,0o600);json.dump(data,f,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    def _save_live(self):self._write(self.live_path,self.live)
    def catalog(self):
        with self.lock:
            cached=self.cache.get('catalog')
            if cached and self.clock()-cached[0]<300:return deepcopy(cached[1])
            rows=[];cursor=None;seen=set();total=None
            for _ in range(20):
                params={'page_size':1000}
                if cursor:params['after']=cursor
                data=self._get('/v2/products',params);batch=data.get('result')
                if not isinstance(batch,list):raise ValueError('Invalid Delta India instrument catalog.')
                rows.extend(batch);meta=data.get('meta') or {};total=meta.get('total_count',total);cursor=meta.get('after')
                if not cursor:break
                if cursor in seen:raise ValueError('Delta India catalog pagination repeated; no incomplete catalog accepted.')
                seen.add(cursor)
            else:raise ValueError('Delta India catalog exceeded safe pagination limit.')
            unique={r['id']:r for r in rows if isinstance(r,dict) and r.get('id') is not None}
            if isinstance(total,int) and len(unique)!=total:raise ValueError('Incomplete Delta India catalog; refresh before selecting a contract.')
            instruments=[self._metadata(r) for r in unique.values() if r.get('state')=='live' and r.get('trading_status')=='operational' and r.get('contract_type') in SUPPORTED]
            instruments.sort(key=lambda r:(r['contract_type']!='perpetual_futures',r['symbol']))
            result=dict(broker='DELTA_INDIA',complete=True,available_types=sorted({r['contract_type'] for r in instruments}),instruments=instruments,listed_count=len(unique),supported_live_count=len(instruments),fetched_at=self.clock(),forex_supported=False,forex_message='Only listed supported India crypto derivatives are selectable. This integration provides no forex pair routing.')
            self.cache['catalog']=(self.clock(),result);return deepcopy(result)
    def _metadata(self,r):
        return {k:r.get(k) for k in ('id','symbol','description','contract_type','contract_value','contract_unit_currency','notional_type','is_quanto','tick_size','state','trading_status','settlement_time','strike_price')}|{'underlying':(r.get('underlying_asset') or {}).get('symbol'),'quoting_currency':(r.get('quoting_asset') or {}).get('symbol'),'settlement_currency':(r.get('settling_asset') or {}).get('symbol')}
    def product(self,symbol):
        if not isinstance(symbol,str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,79}',symbol):raise ValueError('Select an exact listed Delta India symbol.')
        cached=self.cache.get(('product',symbol))
        if cached and self.clock()-cached[0]<60:return deepcopy(cached[1])
        r=self._get('/v2/products/'+quote(symbol,safe=''))['result']
        if r.get('symbol')!=symbol or r.get('contract_type') not in SUPPORTED or r.get('state')!='live' or r.get('trading_status')!='operational':raise ValueError('Delta India contract is not currently supported and operational.')
        result=self._metadata(r);self.cache[('product',symbol)]=(self.clock(),result);return deepcopy(result)
    def ticker(self,symbol):
        self.product(symbol);r=self._get('/v2/tickers/'+symbol)['result'];q=r.get('quotes') or {}
        try:bid,ask=float(q['best_bid']),float(q['best_ask']);stamp=float(r['timestamp'])/1e6
        except (KeyError,TypeError,ValueError):raise ValueError('Executable Delta India bid/ask timestamp unavailable.') from None
        if r.get('symbol')!=symbol or not all(math.isfinite(v) for v in (bid,ask,stamp)) or not 0<bid<=ask or not -2<=self.clock()-stamp<=15:raise ValueError('Delta India bid/ask crossed, stale or invalid.')
        return dict(symbol=symbol,bid=bid,ask=ask,exchange_at=stamp,received_at=self.clock(),mark_price=r.get('mark_price'),quote_currency=self.product(symbol)['quoting_currency'])
    def chart(self,symbol,resolution='5m',rsi_length=14,ma_length=14,ma_type='SMA'):
        product=self.product(symbol)
        if resolution not in RESOLUTIONS:raise ValueError('Unsupported Delta candle timeframe.')
        interval=RESOLUTIONS[resolution];now=self.clock();key=('candles',symbol,resolution,int(now//interval))
        cached=self.cache.get(key);data=cached[1] if cached and now-cached[0]<5 else None
        if not data:
            raw=self._get('/v2/history/candles',dict(symbol=symbol,resolution=resolution,start=int(now)-interval*500,end=int(now)))['result']
            if not isinstance(raw,list):raise ValueError('Delta candle history unavailable.')
            rows=[dict(timestamp=float(r['time']),open=float(r['open']),high=float(r['high']),low=float(r['low']),close=float(r['close']),volume=float(r.get('volume') or 0),is_forming=float(r['time'])+interval>now) for r in raw]
            unique={}
            for row in rows:
                if not all(math.isfinite(row[k]) for k in ('timestamp','open','high','low','close','volume')) or row['timestamp']<=0 or min(row['open'],row['high'],row['low'],row['close'])<=0 or row['high']<max(row['open'],row['close']) or row['low']>min(row['open'],row['close']) or row['volume']<0:raise ValueError('Invalid Delta candle evidence.')
                if row['timestamp'] in unique and unique[row['timestamp']]!=row:raise ValueError('Conflicting Delta candle revisions; no signal accepted.')
                unique[row['timestamp']]=row
            data=sorted(unique.values(),key=lambda r:r['timestamp']);self.cache[key]=(now,data)
            if len(self.cache)>200:self.cache={k:v for k,v in self.cache.items() if isinstance(k,str) or isinstance(k,tuple) and k[0]!='candles' or k==key}
        completed=rsi_sma_series(data,rsi_length,ma_length,ma_type);last=completed[-1] if completed else None
        return dict(broker='DELTA_INDIA',symbol=symbol,timeframe=resolution,product=product,candles=deepcopy(data),last_completed=last,signal_policy='COMPLETED_RSI_CROSSOVER_ONLY',strategy='RSI based '+ma_type,analysis_only=True,fetched_at=now)
    def _paper_contract(self,symbol):
        p=self.product(symbol)
        try:value=Decimal(str(p['contract_value']));tick=Decimal(str(p['tick_size']))
        except Exception:raise ValueError('Verified Delta contract units unavailable.') from None
        if not value.is_finite() or not tick.is_finite() or value<=0 or tick<=0 or p.get('notional_type')!='vanilla' or p.get('is_quanto') is not False or p.get('contract_unit_currency')!=p.get('underlying') or p.get('quoting_currency')!=p.get('settlement_currency'):raise ValueError('Paper valuation supports verified linear vanilla contracts only; no guessed quanto/inverse conversion.')
        return p,value
    def preview(self,payload):
        if self.corrupt:raise ValueError('Resolve corrupt Delta paper ledger before recording simulations.')
        if payload.get('mode')!='PAPER':raise PermissionError('Delta India live orders are unavailable.')
        contracts=payload.get('contracts');side=payload.get('side','LONG');symbol=payload.get('symbol')
        if isinstance(contracts,bool) or not isinstance(contracts,int) or not 1<=contracts<=100000 or side not in ('LONG','SHORT'):raise ValueError('Choose LONG/SHORT and positive whole Delta contracts.')
        p,value=self._paper_contract(symbol)
        if side=='SHORT' and p['contract_type'] in ('call_options','put_options'):raise ValueError('Paper option writing is unavailable; only long options are supported.')
        if self.paper['position']:raise ValueError('Close the existing isolated Delta paper position first.')
        q=self.ticker(symbol);fill=q['ask'] if side=='LONG' else q['bid'];price_value=float(value*Decimal(str(fill))*contracts)
        preview=dict(id=secrets.token_hex(16),expires_at=self.clock()+60,mode='PAPER',symbol=symbol,product=p,contracts=contracts,side=side,quote=q,reference_fill=fill,contract_units=float(value*contracts),entry_reference_value=price_value,value_currency=p['quoting_currency'],value_basis='Option premium before fees' if 'options' in p['contract_type'] else 'Contract notional; not margin or cash invested',strategy='MANUAL_DELTA_PAPER',message='Simulation only. No Delta order will be submitted. No INR conversion, fees, funding or margin model applied.')
        self.previews={preview['id']:preview};return deepcopy(preview)
    def _save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp')
        with tmp.open('w') as f:os.chmod(tmp,0o600);json.dump(self.paper,f,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(tmp,self.path)
    def record_paper(self,payload):
        with self.lock:
            if payload.get('mode')!='PAPER':raise PermissionError('Only isolated paper simulation is supported.')
            preview=self.previews.get(payload.get('preview_id'))
            if not preview or self.clock()>preview['expires_at'] or self.paper['position']:raise ValueError('Review a fresh Delta paper preview while flat.')
            p,value=self._paper_contract(preview['symbol']);q=self.ticker(preview['symbol']);fill=q['ask'] if preview['side']=='LONG' else q['bid']
            position=dict(lifecycle_id=preview['id'],symbol=preview['symbol'],contracts=preview['contracts'],side=preview['side'],entry_price=fill,entry_time=self.clock(),contract_value=str(value),quote_currency=p['quoting_currency'],strategy='MANUAL_DELTA_PAPER',mode='PAPER',status='OPEN',product_id=p['id'])
            self.paper['position']=position;self.paper['trades'].append(deepcopy(position));self.previews={};self._save();return self.status()
    def close_paper(self,payload):
        with self.lock:
            if payload.get('mode')!='PAPER':raise PermissionError('No live close route exists.')
            if self.corrupt or not self.paper['position']:raise ValueError('No verified Delta paper position to close.')
            p=self.paper['position'];current,value=self._paper_contract(p['symbol'])
            if current['id']!=p['product_id'] or str(value)!=p['contract_value']:raise ValueError('Delta contract identity/units changed; paper close unavailable.')
            self._paper_reduce(p['contracts'],payload.get('reason','EXPLICIT_CLOSE'));return self.status()
    def _position(self,product_id):
        r=self._private('GET','/v2/positions',params={'product_id':product_id})['result']
        if not isinstance(r,dict):raise ValueError('Real-time Delta product position unavailable.')
        size=Decimal(str(r.get('size')))
        if not size.is_finite() or size!=size.to_integral_value():raise ValueError('Delta position quantity is invalid.')
        return int(size)
    def _live_ready(self):
        if self.corrupt:raise ValueError('Delta execution ledger is corrupt; reconcile before live actions.')
        if not self._gate():raise PermissionError('Delta India live gate is disabled by configuration.')
        self.verify_auth()
    def _validate_order(self,payload):
        if payload.get('mode')!='LIVE':raise PermissionError('Select LIVE explicitly to submit a real Delta order.')
        size=payload.get('contracts');side=payload.get('side');tif=payload.get('time_in_force','ioc');reduce=payload.get('reduce_only',False)
        if isinstance(size,bool) or not isinstance(size,int) or not 1<=size<=100000 or side not in ('buy','sell') or tif not in ('ioc','gtc') or not isinstance(reduce,bool):raise ValueError('Choose buy/sell, positive whole contracts and IOC/GTC.')
        if payload.get('order_type','limit_order')!='limit_order':raise ValueError('This adapter supports price-protected limit orders only.')
        self.cache.pop(('product',payload.get('symbol')),None);p,value=self._paper_contract(payload.get('symbol'));q=self.ticker(p['symbol']);tick=Decimal(str(p['tick_size']))
        try:price=Decimal(str(payload.get('limit_price')))
        except Exception:raise ValueError('Enter a positive tick-aligned limit price.') from None
        if not price.is_finite() or price<=0 or price%tick!=0:raise ValueError('Limit price must be positive and a multiple of tick '+str(tick)+'.')
        pos=self._position(p['id'])
        if reduce and (pos==0 or (pos>0 and side!='sell') or (pos<0 and side!='buy') or size>abs(pos)):raise ValueError('Reduce-only quantity/side exceeds the current broker position.')
        funds=self._private('GET','/v2/wallet/balances')['result']
        if not isinstance(funds,list) or not funds:raise ValueError('Broker wallet balances unavailable.')
        if not reduce and not any(Decimal(str(r.get('available_balance','0')))>0 for r in funds):raise ValueError('No positive broker-reported available balance. No currency conversion or margin assumption made.')
        return p,dict(product_id=p['id'],size=size,side=side,order_type='limit_order',limit_price=str(price),time_in_force=tif,reduce_only=reduce),q
    def _apply_order(self,owned,r):
        expected=owned['request']
        if not isinstance(r,dict) or not r.get('id') or r.get('client_order_id')!=owned['client_order_id'] or r.get('product_id')!=expected['product_id'] or r.get('side')!=expected['side'] or r.get('size')!=expected['size']:raise ValueError('Broker order identity/quantity mismatch; manual reconciliation required.')
        if r.get('order_type')!=expected['order_type'] or Decimal(str(r.get('limit_price')))!=Decimal(expected['limit_price']) or bool(r.get('reduce_only',False))!=expected['reduce_only']:raise ValueError('Broker order terms differ from the submitted intent.')
        unfilled=r.get('unfilled_size');state=r.get('state')
        if isinstance(unfilled,bool) or not isinstance(unfilled,int) or not 0<=unfilled<=expected['size'] or state not in ('open','pending','closed','cancelled'):raise ValueError('Delta order fill/state evidence unavailable.')
        if state=='closed' and unfilled:raise ValueError('Closed Delta order reports unfilled quantity; reconciliation required.')
        filled=expected['size']-unfilled;old=owned.get('filled_contracts',0)
        if filled<old:raise ValueError('Delta cumulative fills decreased; reconciliation unavailable.')
        avg=r.get('average_fill_price')
        if filled and (avg is None or not Decimal(str(avg)).is_finite() or Decimal(str(avg))<=0):raise ValueError('Filled Delta order lacks verified average fill price.')
        owned.pop('reconciliation_message',None)
        owned.update(order_id=r['id'],status=state,filled_contracts=filled,unfilled_contracts=unfilled,average_fill_price=avg,updated_at=self.clock(),commission=r.get('paid_commission'),cancellation_reason=r.get('cancellation_reason'))
        self._save_live();return deepcopy(owned)
    def submit(self,payload,runner=False):
        with self.lock:
            token=payload.get('request_id')
            if not isinstance(token,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',token):raise ValueError('A unique submission request ID is required.')
            digest=hashlib.sha256(json.dumps({k:v for k,v in payload.items() if k!='request_id'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
            existing=self.live['orders'].get(token)
            if existing:
                if existing['payload_digest']!=digest:raise ValueError('Submission request ID reused with different terms.')
                return self.reconcile({'request_id':token}) if existing['status'] not in ('REJECTED','closed','cancelled') else deepcopy(existing)
            if self.runner['running'] and not runner:raise ValueError('Stop the Delta runner before manual live submission.')
            if any(o['status'] in ('SUBMITTING','UNKNOWN','open','pending','CANCEL_UNKNOWN') for o in self.live['orders'].values()):raise ValueError('Reconcile/cancel the outstanding owned Delta order first.')
            self._live_ready();p,body,q=self._validate_order(payload)
            if not -2<=self.clock()-q['exchange_at']<=15:raise ValueError('Delta quote aged during preflight; submit again with fresh data.')
            if runner and payload.get('signal_close') is not None and not 0<=self.clock()-payload['signal_close']<=30:raise ValueError('Completed Delta crossover expired during preflight; no order submitted.')
            client='spdi_'+hashlib.sha256(token.encode()).hexdigest()[:26];body['client_order_id']=client
            owned=dict(request_id=token,client_order_id=client,payload_digest=digest,request=body,symbol=p['symbol'],product=p,status='SUBMITTING',filled_contracts=0,created_at=self.clock(),quote=q,account_identity=self._identity(),strategy=payload.get('strategy','MANUAL_DELTA_LIMIT'),execution_reason=payload.get('execution_reason','MANUAL'))
            self.live['orders'][token]=owned;self._save_live() # durable intent precedes financial request
            try:r=self._private('POST','/v2/orders',body=body)['result']
            except ValueError as e:owned.update(status='REJECTED',error=str(e));self._save_live();return deepcopy(owned)
            except Exception:owned.update(status='UNKNOWN',error='Submission outcome unknown. Reconcile this request; it will never be blindly resent.');self._save_live();return deepcopy(owned)
            try:return self._apply_order(owned,r)
            except Exception:owned.update(status='UNKNOWN',error='Order response could not be verified. Reconcile; no resubmission.');self._save_live();return deepcopy(owned)
    def _owned(self,payload):
        o=self.live['orders'].get(payload.get('request_id'))
        if not o or o.get('account_identity')!=self._identity():raise ValueError('No owned Delta order for the configured account/request.')
        return o
    def reconcile(self,payload):
        with self.lock:
            o=self._owned(payload)
            if o['status']=='REJECTED':return deepcopy(o)
            try:r=self._private('GET','/v2/orders/client_order_id/'+o['client_order_id'])['result'];return self._apply_order(o,r)
            except Exception:o['reconciliation_message']='Broker order lookup unavailable; no retry submission. Check Delta account before further actions.';self._save_live();return deepcopy(o)
    def cancel(self,payload):
        with self.lock:
            if payload.get('mode')!='LIVE':raise PermissionError('Explicit LIVE cancel required.')
            self._live_ready();o=self._owned(payload)
            if o['status']=='CANCEL_UNKNOWN':return self.reconcile(payload)
            current=self.reconcile(payload)
            if current['status'] in ('closed','cancelled','REJECTED'):return current
            if current['status'] not in ('open','pending') or not current.get('order_id') or current.get('reconciliation_message'):raise ValueError('Owned order is not verified open; cancellation unavailable.')
            o['status']='CANCEL_UNKNOWN';self._save_live()
            try:return self._apply_order(o,self._private('DELETE','/v2/orders',body={'id':o['order_id'],'product_id':o['request']['product_id']})['result'])
            except Exception:self._save_live();return deepcopy(o)
    def fills(self,payload):
        o=self._owned(payload);rows=[];cursor=None;seen=set()
        for _ in range(20):
            params={'product_ids':o['request']['product_id'],'start_time':int((o['created_at']-60)*1e6),'page_size':100}
            if cursor:params['after']=cursor
            d=self._private('GET','/v2/fills',params=params)
            if not isinstance(d['result'],list):raise ValueError('Delta fill evidence unavailable.')
            rows.extend({k:r.get(k) for k in ('id','order_id','product_id','size','price','side','commission','settling_asset_symbol','created_at')} for r in d['result'] if str(r.get('order_id'))==str(o.get('order_id')) and r.get('product_id')==o['request']['product_id'])
            cursor=(d.get('meta') or {}).get('after')
            if not cursor:break
            if cursor in seen:raise ValueError('Fill pagination incomplete.')
            seen.add(cursor)
        else:raise ValueError('Fill pagination limit exceeded.')
        return {'fills':list({r['id']:r for r in rows}.values()),'request_id':o['request_id']}
    def start_runner(self,payload):
        with self.lock:
            if self.runner['running']:raise ValueError('Delta runner already running.')
            if self.runner.get('pending') and not self._settle_runner():raise ValueError('Reconcile pending runner order before restarting.')
            if self.live['runner_position']:raise ValueError('Existing runner position needs reconciliation/explicit close before restarting.')
            mode=payload.get('mode');direction=payload.get('direction','BOTH');size=payload.get('contracts')
            if mode not in ('LIVE','PAPER') or direction not in ('BOTH','LONG_ONLY') or isinstance(size,bool) or not isinstance(size,int) or not 1<=size<=100000:raise ValueError('Choose LIVE/PAPER, runner direction and whole contract quantity.')
            if mode=='LIVE':
                self._live_ready()
                if any(o['status'] in ('SUBMITTING','UNKNOWN','open','pending','CANCEL_UNKNOWN') for o in self.live['orders'].values()):raise ValueError('Reconcile outstanding Delta orders before starting.')
            p,_=self._paper_contract(payload.get('symbol'))
            if 'options' in p['contract_type'] and direction!='LONG_ONLY':raise ValueError('Options runner supports selected-contract LONG_ONLY: bullish buys, bearish closes. No automatic strike mapping or option writing.')
            if mode=='LIVE' and self._position(p['id'])!=0:raise ValueError('Selected Delta product already has a broker position; runner ownership cannot be established.')
            if mode=='PAPER' and self.paper['position']:raise ValueError('Close the existing Delta paper position first.')
            trailing_settings=delta_trailing.settings(payload)
            cfg={k:payload.get(k,d) for k,d in [('symbol',None),('resolution','5m'),('rsi_length',14),('ma_length',14),('ma_type','SMA'),('contracts',1),('direction','BOTH'),('mode','PAPER')]}
            cfg.update(trailing_settings)
            quote=self.ticker(p['symbol'])
            if cfg['trailing_enabled'] and cfg['trailing_mode']=='POINTS' and cfg['direction']=='BOTH' and cfg['trailing_step']>=quote['bid']:raise ValueError('Short trailing price step must be smaller than the current entry quote.')
            last=self.chart(cfg['symbol'],cfg['resolution'],cfg['rsi_length'],cfg['ma_length'],cfg['ma_type'])['last_completed']
            if not last or last.get('rsi_ma') is None:raise ValueError('Completed RSI/MA history is not warmed up.')
            self.live['runner_config']=deepcopy(cfg);self._save_live()
            self.runner={'running':True,'config':cfg,'product_id':p['id'],'last_candle':last['timestamp'],'message':'Armed for a future completed RSI crossover; no historical replay.','pending':None,'action':None}
            self.stop_event=threading.Event();threading.Thread(target=self._run,args=(self.stop_event,),daemon=True,name='delta-india-runner').start();return self.status()
    def stop_runner(self,payload=None):
        with self.lock:self.runner['running']=False;self.stop_event.set();self.runner['message']='Stopped. Any owned position remains; use Close runner position explicitly.';return self.status()
    def _settle_runner(self):
        token=self.runner.get('pending')
        if not token:return True
        o=self.reconcile({'request_id':token})
        if o['status'] not in ('closed','cancelled','REJECTED'):self.runner['message']='Awaiting verified order completion; no further orders.';return False
        qty=o['filled_contracts'];action=self.runner['action'];p=self.live['runner_position']
        if action=='ENTRY' and qty:self.live['runner_position']={'symbol':o['symbol'],'product_id':o['request']['product_id'],'side':o['request']['side'],'contracts':qty,'entry_price':o['average_fill_price'],'mode':'LIVE','entry_request_id':token}
        if action=='ENTRY' and qty:
            position=self.live['runner_position'];position['trailing']=delta_trailing.initial(position['entry_price'],o['product']['tick_size'],qty,position['side'],self.runner['config'])
        if (action=='EXIT' or str(action).startswith('TRAIL_')) and p:
            if str(action).startswith('TRAIL_') and qty:
                stage=str(action).split('_')[1];p['trailing']['target_filled'][stage]=p['trailing']['target_filled'].get(stage,0)+qty
            p['contracts']-=qty
            if p['contracts']==0:self.live['runner_position']=None
        self.live['runner_pending']=None;self.live['runner_action']=None;self._save_live();self.runner['pending']=None;self.runner['action']=None;return True
    def _runner_order(self,side,size,reduce,action,signal_close=None):
        cfg=self.runner['config'];q=self.ticker(cfg['symbol']);p=self.product(cfg['symbol']);tick=Decimal(str(p['tick_size']));raw=Decimal(str(q['ask'] if side=='buy' else q['bid']))
        if action=='ENTRY' and side=='sell' and cfg.get('trailing_enabled') and cfg.get('trailing_mode')=='POINTS' and Decimal(str(cfg['trailing_step']))>=raw:raise ValueError('Short trailing price step must be smaller than the fresh entry quote.')
        # Marketable tick-aligned IOC limit; at most one tick beyond the fresh quote.
        price=((raw/tick).to_integral_value(rounding='ROUND_CEILING' if side=='buy' else 'ROUND_FLOOR'))*tick
        token='runner_'+secrets.token_hex(12);self.runner['pending']=token;self.runner['action']=action;self.live['runner_pending']=token;self.live['runner_action']=action;self._save_live()
        try:result=self.submit(dict(mode='LIVE',request_id=token,symbol=cfg['symbol'],side=side,contracts=size,limit_price=str(price),time_in_force='ioc',reduce_only=reduce,strategy='DELTA_COMPLETED_RSI_'+cfg['ma_type'],signal_close=signal_close,execution_reason=action),runner=True)
        except Exception:self.runner['pending']=None;self.runner['action']=None;self.live['runner_pending']=None;self.live['runner_action']=None;self._save_live();raise
        self._settle_runner()
        if result['status']=='REJECTED':raise ValueError(result.get('error','Delta runner order rejected; runner stopped.'))
    def runner_tick(self):
        with self.lock:
            if not self.runner['running']:return
            cfg=self.runner['config']
            if cfg['mode']=='LIVE' and not self._settle_runner():return
            last=self.chart(cfg['symbol'],cfg['resolution'],cfg['rsi_length'],cfg['ma_length'],cfg['ma_type'])['last_completed']
            p=self.live['runner_position'] if cfg['mode']=='LIVE' else self.paper['position']
            if p and last and last['timestamp']>self.runner['last_candle'] and 0<=self.clock()-last['timestamp']-RESOLUTIONS[cfg['resolution']]<=30:
                side=p['side'] if cfg['mode']=='LIVE' else ('buy' if p['side']=='LONG' else 'sell')
                cross=last.get('cross_direction')
                if (side=='buy' and cross=='BEARISH') or (side=='sell' and cross=='BULLISH'):
                    self.runner['last_candle']=last['timestamp'];self.close_runner({'mode':cfg['mode'],'signal_close':last['timestamp']+RESOLUTIONS[cfg['resolution']],'reason':'OPPOSITE_CROSSOVER'});self.runner['message']='Opposite completed crossover closed owned residual before trailing targets.';return
            if self._manage_trailing():
                if last and last['timestamp']>self.runner['last_candle']:self.runner['last_candle']=last['timestamp']
                return
            if not last or last['timestamp']<=self.runner['last_candle']:return
            self.runner['last_candle']=last['timestamp'] # consume once even if action fails
            close=last['timestamp']+RESOLUTIONS[cfg['resolution']]
            if not 0<=self.clock()-close<=30:self.runner['message']='Older completed candle skipped after delay/reconnect.';return
            cross=last.get('cross_direction');desired='buy' if cross=='BULLISH' else ('sell' if cross=='BEARISH' and cfg['direction']=='BOTH' else None)
            p=self.live['runner_position'] if cfg['mode']=='LIVE' else self.paper['position']
            if p:
                side=p['side'] if cfg['mode']=='LIVE' else ('buy' if p['side']=='LONG' else 'sell')
                opposite=(side=='buy' and cross=='BEARISH') or (side=='sell' and cross=='BULLISH')
                if opposite:self.close_runner({'mode':cfg['mode'],'signal_close':close,'reason':'OPPOSITE_CROSSOVER'});self.runner['message']='Opposite completed crossover closed owned position; no same-bar reentry.'
                return
            if not desired:return
            if cfg['mode']=='LIVE':
                if self._position(self.runner['product_id'])!=0:raise ValueError('External Delta position detected; entry blocked.')
                self._runner_order(desired,cfg['contracts'],False,'ENTRY',signal_close=close)
            else:
                v=self.preview(dict(mode='PAPER',symbol=cfg['symbol'],contracts=cfg['contracts'],side='LONG' if desired=='buy' else 'SHORT'));self.record_paper({'mode':'PAPER','preview_id':v['id']})
                position=self.paper['position'];position['trailing']=delta_trailing.initial(position['entry_price'],self.product(cfg['symbol'])['tick_size'],position['contracts'],desired,cfg);self._save()
            self.runner['message']='Fresh completed '+str(cross)+' crossover processed.'
    def close_runner(self,payload):
        with self.lock:
            cfg=self.runner.get('config')
            mode=payload.get('mode')
            if mode=='PAPER':return self.close_paper({'mode':'PAPER'})
            if mode!='LIVE' or not cfg or cfg['mode']!='LIVE':raise ValueError('No owned LIVE runner configuration to close.')
            if not self._settle_runner():raise ValueError('Pending Delta order must settle before closing.')
            p=self.live['runner_position']
            if not p:raise ValueError('No owned Delta runner position.')
            if p.get('trailing'):p['trailing']['exit_latched']=True;p['exit_reason']=payload.get('reason','EXPLICIT_CLOSE');self._save_live()
            self._live_ready();expected=p['contracts'] if p['side']=='buy' else -p['contracts']
            if self._position(p['product_id'])!=expected:raise ValueError('Broker position differs from runner-owned quantity; close blocked for reconciliation.')
            self._runner_order('sell' if p['side']=='buy' else 'buy',p['contracts'],True,'EXIT',signal_close=payload.get('signal_close'));return self.status()
    def _paper_reduce(self,size,reason,stage=None):
        p=self.paper['position']
        if not p or not isinstance(size,int) or size<=0 or size>p['contracts']:raise ValueError('Paper exit exceeds owned contracts.')
        current,value=self._paper_contract(p['symbol'])
        if current['id']!=p['product_id'] or str(value)!=p['contract_value']:raise ValueError('Paper contract identity changed.')
        q=self.ticker(p['symbol']);fill=q['bid'] if p['side']=='LONG' else q['ask'];change=(Decimal(str(fill))-Decimal(str(p['entry_price'])))*(1 if p['side']=='LONG' else -1)
        trade=next(r for r in self.paper['trades'] if r['lifecycle_id']==p['lifecycle_id']);exits=trade.setdefault('exit_fills',[]);exits.append(dict(contracts=size,price=fill,time=self.clock(),reason=reason,pnl=float(change*value*size)))
        trade['realized_pnl']=sum(r['pnl'] for r in exits);trade['remaining_contracts']=p['contracts']-size
        if stage is not None:p['trailing']['target_filled'][str(stage)]=p['trailing']['target_filled'].get(str(stage),0)+size
        p['contracts']-=size
        if not p['contracts']:
            trade.update(status='CLOSED',exit_time=self.clock(),exit_price=sum(r['contracts']*r['price'] for r in exits)/sum(r['contracts'] for r in exits),basis='Quote currency; before fees/funding; no INR conversion');self.paper['position']=None
        self._save()
    def _manage_trailing(self):
        cfg=self.runner['config']
        if not cfg.get('trailing_enabled'):return False
        p=self.live['runner_position'] if cfg['mode']=='LIVE' else self.paper['position']
        if not p or not p.get('trailing'):return False
        state=p['trailing']
        if state.get('exit_latched'):
            self.close_runner({'mode':cfg['mode'],'reason':p.get('exit_reason','TRAILING_STOP')});return True
        q=self.ticker(p['symbol']);updated,hit=delta_trailing.advance(state,q,self.clock());p['trailing']=updated
        if cfg['mode']=='LIVE':self._save_live()
        else:self._save()
        if hit:
            updated['exit_latched']=True;p['exit_reason']='TRAILING_STOP'
            self.close_runner({'mode':cfg['mode'],'reason':'TRAILING_STOP'});self.runner['message']='Application trailing stop triggered; verified residual exit requested.';return True
        target=delta_trailing.target(updated,p['contracts'])
        if not target:return False
        stage,size=target
        if cfg['mode']=='LIVE':
            expected=p['contracts'] if p['side']=='buy' else -p['contracts']
            if self._position(p['product_id'])!=expected:raise ValueError('Broker position differs from trailing-owned quantity; reconciliation required.')
            self._runner_order('sell' if p['side']=='buy' else 'buy',size,True,'TRAIL_'+str(stage))
        else:self._paper_reduce(size,'TRAIL_TARGET_'+str(stage),stage=stage)
        self.runner['message']='Trailing target '+str(stage)+' processed using verified contracts.';return True
    def _run(self,event):
        while not event.wait(2):
            try:
                with self.lock:
                    if event is not self.stop_event or event.is_set():return
                    self.runner_tick()
            except Exception as e:
                with self.lock:self.runner['running']=False;self.runner['message']=str(e);event.set()
