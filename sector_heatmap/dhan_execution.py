"""Account-owned Dhan v2 manual LIMIT tickets; no strategy or protective-order routing."""
from contextlib import contextmanager
from copy import deepcopy
import os
import csv
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import io
import json
from pathlib import Path
import secrets
import threading
import time
from zoneinfo import ZoneInfo
import requests
import fcntl
import tempfile
from .config import _atomic_private_write
from .fyers_execution import PreviewChanged
from .premium_exit_mapping import premium_exits

IST = ZoneInfo('Asia/Kolkata')
MASTER_URL = 'https://images.dhan.co/api-data/api-scrip-master.csv'


def number(value, label, positive=False):
    try:
        result = Decimal(str(value))
    except Exception:
        raise ValueError(label + ' must be numeric.') from None
    if not result.is_finite() or (positive and result <= 0):
        raise ValueError(label + ' must be finite and positive.')
    return result


class DhanAPIError(RuntimeError):
    def __init__(self, message, definitive_rejection=False, reauthentication_required=False):
        super().__init__(message)
        self.definitive_rejection = definitive_rejection
        self.reauthentication_required = reauthentication_required


def contract_underlying(row):
    symbol=str(row.get('SEM_TRADING_SYMBOL') or '')
    if row.get('SEM_SEGMENT')=='D' and row.get('SEM_OPTION_TYPE') in ('CE','PE'):
        parts=symbol.rsplit('-',3)
        if len(parts)!=4:
            raise ValueError('Dhan derivative symbol has no verified underlying suffix.')
        return parts[0]
    return symbol


def fresh_quote_snapshot(client, segment, security_id, clock=time.time, max_age=15):
    """Dhan REST snapshots are current at request time; LTT is not depth time."""
    for attempt in range(2):
        started = clock()
        data = client.request('POST', '/marketfeed/quote', {segment: [int(security_id)]})
        received = clock()
        elapsed=received-started
        if isinstance(client,DhanClient) and isinstance(data,dict):
            timing=data.get('_sector_snapshot_timing') or {}
            received=timing.get('received_at',received)
            elapsed=timing.get('elapsed',elapsed)
        if isinstance(data, dict) and data.get('status') not in (None, 'success'):
            raise ValueError('Dhan did not return a successful quote snapshot.')
        quote = data.get('data', {}).get(segment, {}).get(str(security_id))
        if not isinstance(quote, dict):
            raise ValueError('Dhan returned no quote for the selected native instrument.')
        # Bound the complete request including account-wide throttle waits.
        if 0 <= elapsed <= max_age:
            return quote, received
    raise ValueError('Dhan quote response remained delayed after automatic refresh; no order can be prepared.')


class DhanClient:
    def __init__(self, credentials):
        self.client_id = credentials['DHAN_CLIENT_ID']
        self.headers = {'access-token': credentials['DHAN_ACCESS_TOKEN'], 'client-id': self.client_id, 'Content-Type': 'application/json'}
        self.last_quote = 0
        self.lock = threading.Lock()

    @contextmanager
    def _quote_slot(self, category="quote", interval=1.1):
        # Coordinate all workers for this account, not just one client object.
        digest = hashlib.sha256((self.client_id+":"+category).encode()).hexdigest()[:24]
        folder = Path(tempfile.gettempdir()) / ("sector-dhan-quotes-" + str(os.getuid()))
        folder.mkdir(mode=0o700, exist_ok=True)
        with (folder / (digest + ".lock")).open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            try:
                previous = float(handle.read() or 0)
            except ValueError:
                previous = 0
            time.sleep(max(0, interval - (time.time() - previous)))
            try:
                yield
            finally:
                handle.seek(0)
                handle.truncate()
                handle.write(str(time.time()))
                handle.flush()
                fcntl.flock(handle, fcntl.LOCK_UN)

    def request(self, method, path, payload=None):
        if path.startswith('/marketfeed/'):
            with self._quote_slot():
                return self._request(method, path, payload)
        if path.startswith('/optionchain'):
            with self._quote_slot('optionchain', 3.1):
                return self._request(method, path, payload)
        if path.startswith('/charts/'):
            with self._quote_slot('history', .25):
                return self._request(method, path, payload)
        return self._request(method, path, payload)

    def _request(self, method, path, payload=None):
        # Fixed provider origin; neither credentials nor broker errors are reflected.
        if path.startswith('/marketfeed/'):
            with self.lock:
                time.sleep(max(0, 1.05 - (time.monotonic() - self.last_quote)))
                self.last_quote = time.monotonic()
        try:
            requested_at=time.monotonic()
            response = requests.request(method, 'https://api.dhan.co/v2'+path, headers=self.headers, json=payload, timeout=20)
            if response.status_code == 401:
                raise DhanAPIError('Dhan session expired or invalid. Reauthenticate this saved account; no order was retried.', True, True)
            if response.status_code == 403:
                raise DhanAPIError('Dhan rejected account authorization or API permission. Test the selected account connection before retrying.', True)
            if response.status_code == 429:
                raise DhanAPIError('Dhan API rate limit reached. Wait briefly before a new read or preview. Order submissions are never retried automatically.', True)
            if response.status_code >= 500:
                raise RuntimeError('Dhan service is temporarily unavailable. Read/preview failed; an attempted submission requires reconciliation, not retry.')
            if response.status_code >= 400:
                raise DhanAPIError('Dhan rejected the API request. Verify the selected instrument, segment and account permissions.', True)
            response.raise_for_status()
            data = response.json()
            if path.startswith('/marketfeed/') and isinstance(data,dict):
                data['_sector_snapshot_timing']={'received_at':time.time(),'elapsed':time.monotonic()-requested_at}
        except (requests.RequestException, ValueError):
            raise RuntimeError('Dhan request failed; check token, data subscription, permissions and connectivity. Do not retry an uncertain order submission.') from None
        if isinstance(data, dict) and (data.get('status') in ('failure','failed','error') or data.get('errorType')):
            raise DhanAPIError('Dhan rejected the request; check account permissions and broker status.', not bool(data.get('orderId')))
        return data


class DhanMaster:
    def __init__(self):
        self.rows, self.day = [], None
        self.lock = threading.Lock()

    def load(self, now):
        with self.lock:
            if self.day != now.date():
                response = requests.get(MASTER_URL, timeout=40)
                response.raise_for_status()
                rows = list(csv.DictReader(io.StringIO(response.text)))
                if not rows or 'SEM_SMST_SECURITY_ID' not in rows[0]:
                    raise ValueError('Dhan security master schema is unavailable.')
                self.rows, self.day = rows, now.date()
            return self.rows

    def resolve(self, payload, now):
        proposal = payload.get('proposal') or {}
        kind = str(proposal.get('kind') or 'NATIVE').upper()
        underlying = str(payload.get('underlying') or '').upper()
        exchange, ticker = underlying.split(':',1) if ':' in underlying else ('NSE',underlying)
        ticker = ticker.removesuffix('-EQ')
        def segment(row):
            return row['SEM_EXM_EXCH_ID'] + {'E':'_EQ','D':'_FNO','M':'_COMM','C':'_CURRENCY'}.get(row['SEM_SEGMENT'],'_UNKNOWN')
        rows = self.load(now)
        if kind == 'EQUITY':
            matches = [r for r in rows if r['SEM_EXM_EXCH_ID']==exchange and r['SEM_SEGMENT']=='E' and (r['SEM_SERIES']=='EQ' if exchange=='NSE' else r['SEM_SERIES'] in ('A','B','X','XT','T')) and r['SEM_TRADING_SYMBOL']==ticker]
        elif kind == 'LONG_OPTION':
            legs=proposal.get('legs') or []
            expected={'BULLISH':'CE','BEARISH':'PE'}.get(proposal.get('direction'))
            if len(legs)!=1 or legs[0].get('action')!='BUY' or legs[0].get('option_type')!=expected or not expected:
                raise ValueError('Dhan option tickets require one bought Call or Put.')
            strike=number(legs[0].get('strike'),'Strike',True)
            expiry=str(payload.get('expiry') or '')
            if not expiry:raise ValueError('Exact option expiry is required.')
            matches=[r for r in rows if r['SEM_EXM_EXCH_ID']==exchange and r['SEM_SEGMENT']=='D' and contract_underlying(r)==ticker and r['SEM_OPTION_TYPE']==expected and r['SEM_EXPIRY_DATE'][:10]==expiry and number(r['SEM_STRIKE_PRICE'],'Master strike')==strike]
        elif kind == 'NATIVE':
            matches=[r for r in rows if r['SEM_SMST_SECURITY_ID']==str(payload.get('security_id')) and segment(r)==payload.get('exchange_segment')]
        else:
            raise ValueError('This proposal needs a dedicated Dhan adapter. No cross-broker fallback is allowed.')
        if len(matches)!=1:raise ValueError('Exact contract is missing or ambiguous in today’s Dhan security master.')
        row=matches[0]
        if kind == 'LONG_OPTION':
            supplied = str((proposal.get('legs') or [{}])[0].get('symbol') or '')
            if supplied.startswith(('NSE_FNO:', 'BSE_FNO:')) and supplied != segment(row)+':'+str(row['SEM_SMST_SECURITY_ID']):
                raise ValueError('Dhan proposal contract ID differs from the current native master.')
        expiry=row['SEM_EXPIRY_DATE'][:10]
        if expiry and expiry < now.date().isoformat():raise ValueError('Dhan contract has expired.')
        result={'security_id':row['SEM_SMST_SECURITY_ID'],'exchange_segment':segment(row), 'symbol':row['SEM_TRADING_SYMBOL'],
                'lot_size':int(number(row['SEM_LOT_UNITS'],'Lot size',True)), 'tick_size':float(number(row['SEM_TICK_SIZE'],'Tick size',True)/100),
                'option_type':row['SEM_OPTION_TYPE'],'strike':float(number(row.get('SEM_STRIKE_PRICE') or 0,'Master strike')),'expiry':expiry,'kind':kind,'quantity_multiplier':1}
        if segment(row)=='MCX_COMM':
            from . import dhan_mcx
            result.update(dhan_mcx.valuation(row),entry_cutoff=dhan_mcx.entry_cutoff(row))
        return result


class DhanExecutionService:
    def __init__(self, account, folder, client_factory=DhanClient, master=None, now=None, egress=None, execution_halt=None, execution_allowed=None):
        self.account, self.folder = dict(account), Path(folder)
        self.client_factory, self.master = client_factory, master or DhanMaster()
        self.now = now or (lambda:datetime.now(IST))
        self.egress = egress or self._egress
        self.execution_halt=execution_halt
        self.execution_allowed=execution_allowed or (lambda:True)
        self.lock=threading.RLock()
        self.previews={}
        self.client=None
        self.credential_digest=None

    @staticmethod
    def _egress():
        response=requests.get('https://api.ipify.org',timeout=10)
        response.raise_for_status()
        import ipaddress
        return str(ipaddress.ip_address(response.text.strip()))

    def _client(self):
        if (self.folder/'disconnected.json').exists():
            self.client=None;self.credential_digest=None
            raise PermissionError('Dhan account disconnected. Reconnect from Accounts.')
        values=json.loads((self.folder/'credentials.json').read_text())
        if self.account['broker']!='DHAN' or values.get('DHAN_CLIENT_ID')!=self.account['account_ref'] or not values.get('DHAN_ACCESS_TOKEN'):
            raise PermissionError('Configure this user’s Dhan account before connecting.')
        digest=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
        if digest!=self.credential_digest:
            self.client=self.client_factory(values);self.credential_digest=digest
        return self.client

    def capabilities(self):
        configured=(self.folder/'credentials.json').exists()
        return {'selected_broker':'dhan','account_id':self.account['id'],'account_label':self.account['label'],
                'strategy_routes':['renko','rsi','band','kama'], 'dhan_configured':configured,'live_submission_enabled':bool(self.account['live_enabled']) and self.execution_allowed(),
                'message':'Dhan account credentials are saved; broker validation occurs on preview.' if configured else 'Save your Dhan client ID and access token in Broker accounts.'}

    def status(self):
        client=self._client()
        try:profile=client.request('GET','/profile')
        except DhanAPIError as error:
            if not error.reauthentication_required:raise
            return {**self.capabilities(),'authenticated':False,'reauthentication_required':True,'message':str(error)}
        if str(profile.get('dhanClientId'))!=client.client_id:raise PermissionError('Dhan token belongs to a different client ID.')
        return {**self.capabilities(),'authenticated':True,'token_validity':profile.get('tokenValidity'),'data_plan':profile.get('dataPlan'),
                'static_ips':client.request('GET','/ip/getIP')}

    def _fresh_preview_quote(self, client, segment, security_id):
        row, received=fresh_quote_snapshot(client, segment, security_id, lambda: self.now().timestamp())
        return dict(row, snapshot_received_at=received, timestamp_basis='DHAN_REST_SNAPSHOT')

    def _preflight(self, payload):
        now=self.now().astimezone(IST)
        if str(payload.get('broker','')).upper()!='DHAN':raise ValueError('Explicitly select Dhan for this ticket.')
        if payload.get('account_id') and payload['account_id']!=self.account['id']:raise PermissionError('Ticket account differs from this Dhan workspace.')
        proposal=payload.get('proposal') or {}
        if proposal.get('broker') and str(proposal['broker']).upper()!='DHAN':
            raise PermissionError('Proposal broker differs from the selected Dhan account.')
        if proposal.get('source')=='ANALYSIS_HANDOFF' and proposal.get('broker')!='DHAN':
            raise ValueError('Collect a fresh Dhan-native analysis proposal before preparing this account ticket.')

        if str(payload.get('order_type','LIMIT')).upper()!='LIMIT':raise ValueError('This Dhan route currently supports LIMIT orders only.')
        for journal in (self.folder/'dhan-orders').glob('*.json'):
            if json.loads(journal.read_text()).get('status') in ('UNKNOWN','SUBMITTING'):
                raise ValueError('An uncertain Dhan submission needs broker reconciliation before another order.')
        for journal in (self.folder/'dhan-strategy-intents').glob('*.json'):
            if json.loads(journal.read_text()).get('status') in ('SUBMITTING','UNKNOWN'):
                raise ValueError('An uncertain Dhan strategy submission needs reconciliation before another order.')
        client=self._client();profile=client.request('GET','/profile')
        if str(profile.get('dhanClientId'))!=client.client_id:raise PermissionError('Dhan token belongs to a different client ID.')
        if str(profile.get('dataPlan','')).lower()!='active':raise ValueError('Dhan Data API subscription must be active for fresh quotes.')
        ips=client.request('GET','/ip/getIP')
        if self.egress() not in (ips.get('primaryIP'),ips.get('secondaryIP')):raise ValueError('This server’s outgoing IP is not whitelisted for this Dhan account.')
        contract=self.master.resolve(payload,now)
        opening,closing=9*60+15,15*60+30
        if contract['exchange_segment']=='MCX_COMM':
            from . import dhan_mcx
            end=dhan_mcx.session(now.timestamp())['master_regular_session'][-4:]
            opening,closing=dhan_mcx.trading_bounds(now.timestamp())
            if now.timestamp()>=contract['entry_cutoff']:raise ValueError('Dhan MCX pre-expiry protection blocks new entry.')
        if now.weekday()>4 or not opening<=now.hour*60+now.minute<closing:
            raise ValueError('Dhan manual tickets require an open session for the selected contract.')
        if contract['exchange_segment'] not in ('NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO','MCX_COMM'):
            raise ValueError('Dhan manual tickets currently support NSE/BSE equities and bought options.')
        option=contract['exchange_segment'].endswith('_FNO') or contract['exchange_segment']=='MCX_COMM'
        if option and contract.get('option_type') not in ('CE','PE'):raise ValueError('Futures need a dedicated Dhan risk adapter.')
        proposal=payload.get('proposal') or {}
        action='BUY' if option else payload.get('transaction_type') or ('SELL' if proposal.get('direction')=='BEARISH' else 'BUY')
        if action not in ('BUY','SELL'):raise ValueError('Choose BUY or SELL.')
        if option and payload.get('transaction_type','BUY')!='BUY':raise ValueError('Short options are not supported by this Dhan route.')
        quantity=number(payload.get('quantity',proposal.get('quantity',1)),'Quantity',True)
        if contract['kind']=='LONG_OPTION':quantity=number(payload.get('lots'),'Lots',True)*contract['lot_size']
        if quantity!=int(quantity) or int(quantity)%contract['lot_size']:raise ValueError('Quantity must be a whole multiple of the current contract lot size.')
        product=payload.get('cash_product') or payload.get('product_type') or ('MARGIN' if option else 'INTRADAY')
        if product not in (('INTRADAY','MARGIN') if option else ('INTRADAY','CNC')):raise ValueError('Product is unsupported for this Dhan contract.')
        if action=='SELL' and product!='INTRADAY':raise ValueError('Dhan delivery sells require a dedicated holdings/eDIS flow.')
        quote=self._fresh_preview_quote(client, contract['exchange_segment'], contract['security_id'])
        try:
            bid=number(quote['depth']['buy'][0]['price'],'Bid',True);ask=number(quote['depth']['sell'][0]['price'],'Ask',True)
        except (KeyError,IndexError,TypeError):raise ValueError('Dhan returned incomplete two-sided market depth.') from None
        if bid>ask:raise ValueError('Dhan market depth is crossed: bid exceeds ask.')
        tick=number(contract['tick_size'],'Tick',True)
        selected_price=number(payload.get('limit_price',ask if action=='BUY' else bid),'Limit price',True)
        price=(selected_price/tick).to_integral_value(rounding=ROUND_CEILING if action=='BUY' else ROUND_FLOOR)*tick
        stop=number(payload.get('invalidation'),'Explicit stop/invalidation',True)
        target_value=payload.get('target_price',proposal.get('target'))
        multiplier=number(contract.get('quantity_multiplier',1),'Contract multiplier',True)
        if option:
            risk=price*quantity*multiplier
        else:
            if (action=='BUY' and stop>=price) or (action=='SELL' and stop<=price):raise ValueError('Stop must be on the loss side of the Dhan limit price.')
            risk=abs(price-stop)*quantity
        ticket={'dhanClientId':client.client_id,'transactionType':action,'exchangeSegment':contract['exchange_segment'],
                'productType':product,'orderType':'LIMIT','validity':'DAY','securityId':contract['security_id'],
                'quantity':int(quantity),'price':float(price),'triggerPrice':0,'disclosedQuantity':0,'afterMarketOrder':False}
        funds=client.request('GET','/fundlimit');positions=client.request('GET','/positions');orders=client.request('GET','/orders')
        if str(funds.get('dhanClientId'))!=client.client_id or not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Dhan account state could not be verified.')
        if any(str(row.get('dhanClientId',client.client_id))!=client.client_id for row in positions+orders):raise PermissionError('Dhan returned mixed account state.')
        for journal in (self.folder/'dhan-orders').glob('*.json'):
            saved=json.loads(journal.read_text())
            if saved.get('status') in ('TRANSIT','PENDING','PART_TRADED') and saved['ticket']['securityId']==contract['security_id'] and saved['ticket']['exchangeSegment']==contract['exchange_segment']:
                raise ValueError('An acknowledged Dhan order for this contract needs reconciliation before another ticket.')
        pending=[row for row in orders if row.get('orderStatus') in ('TRANSIT','PENDING','PART_TRADED')]
        if any(str(row.get('securityId'))==contract['security_id'] and row.get('exchangeSegment')==contract['exchange_segment'] for row in pending):raise ValueError('A pending Dhan order already exists for this contract.')
        if any(float(row.get('netQty',0))!=0 and str(row.get('securityId'))==contract['security_id'] and row.get('exchangeSegment')==contract['exchange_segment'] for row in positions):raise ValueError('Reconcile the existing Dhan position before opening another ticket for this contract.')
        margin=client.request('POST','/margincalculator',{k:v for k,v in ticket.items() if k in ('dhanClientId','exchangeSegment','transactionType','quantity','productType','securityId','price','triggerPrice')})
        cash=number(funds.get('availabelBalance',funds.get('availableBalance')),'Available funds')
        required=number(margin.get('totalMargin'),'Broker margin',True)
        # Dhan returns a positive surplus in insufficientBalance; derive coverage from balances.
        margin_cash=number(margin.get('availableBalance',cash),'Margin available balance')
        cash=min(cash,margin_cash)
        required=max(required,price*quantity*multiplier) if option else required
        if cash<required:raise ValueError(f'Insufficient Dhan funds/margin: available ₹{cash:.2f}; required ₹{required:.2f}.')
        open_positions=[row for row in positions if float(row.get('netQty',0))!=0]
        realized_loss=sum(max(0,-float(row.get('realizedProfit',0))) for row in positions)
        enforce_risk=payload.get('enforce_risk_controls') is not False
        external=payload.get('external_open_risk')
        if enforce_risk and (open_positions or pending):
            if external is None:raise ValueError('Declare the worst-case risk of existing Dhan positions and pending orders.')
        external=number(external or 0,'External open risk')
        daily=number(payload.get('daily_loss_limit',5000),'Daily loss limit',True)
        idea=number(payload.get('idea_risk_limit',2000),'Idea risk limit',True)
        reserve=number(payload.get('risk_reserve',1000),'Risk reserve')
        if external<0 or reserve<0:raise ValueError('Risk values cannot be negative.')
        if enforce_risk and (risk>idea or Decimal(str(realized_loss))+external+reserve+risk>daily):raise ValueError('Dhan ticket exceeds the configured idea or daily risk budget.')
        max_positions=number(payload.get('max_simultaneous_positions',5),'Maximum positions',True)
        if enforce_risk and len(open_positions)+len(pending)>=max_positions:raise ValueError('Dhan maximum simultaneous positions reached.')
        state_snapshot={
            'positions':sorted([{k:row.get(k) for k in ('securityId','exchangeSegment','netQty','realizedProfit','buyQty','sellQty')} for row in open_positions],key=lambda row:json.dumps(row,sort_keys=True)),
            'pending':sorted([{k:row.get(k) for k in ('orderId','securityId','exchangeSegment','quantity','filledQty','price','transactionType','productType')} for row in pending],key=lambda row:json.dumps(row,sort_keys=True))}
        protection=None
        if option and contract['kind']=='LONG_OPTION':
            plan=payload.get('underlying_exit_plan') or {}
            if not plan.get('stop') or not plan.get('target'):
                raise ValueError('The analysis must provide underlying stop and target levels for a protected Dhan Super Order.')
            underlying=self.master.resolve({'underlying':payload.get('underlying'),'proposal':{'kind':'EQUITY'}},now)
            spot_quote=self._fresh_preview_quote(client, underlying['exchange_segment'], underlying['security_id'])
            try:
                spot=number(spot_quote['last_price'],'Underlying quote',True)
            except (KeyError,TypeError,ValueError):raise ValueError('Fresh underlying quote is required to map premium exits.') from None
            protection=premium_exits(spot=spot,stop=plan['stop'],target=plan['target'],premium=price,
                                    strike=contract.get('strike'),expiry=contract['expiry'],option_type=contract['option_type'],tick=tick,now=self.now())
            ticket={k:v for k,v in ticket.items() if k not in ('validity','triggerPrice','disclosedQuantity','afterMarketOrder')}
            ticket.update(stopLossPrice=protection['stop_loss_price'],targetPrice=protection['target_price'],trailingJump=0)
        warnings=([protection['assumptions'],'Dhan Super Order requests linked premium stop-loss and target legs. Broker acknowledgement is not fill or exit-leg confirmation.'] if protection else ['Stop and target are planning levels; this normal LIMIT entry does not place protective exit orders.'])
        if price*quantity*multiplier>50000:warnings.append('Order notional exceeds ₹50,000.')
        if target_value is not None:
            target=number(target_value,'Target',True)
            if not option and ((action=='BUY' and target<=price) or (action=='SELL' and target>=price)):raise ValueError('Target must be on the profit side of the entry.')
        return {'broker':'DHAN','account_id':self.account['id'],'account_label':self.account['label'],'ticket':ticket,
                'instrument':{'kind':contract['kind'],'contracts':[{**contract,'action':action,'quantity':int(quantity),'limit_price':float(price)}],'worst_case_risk':float(risk)},
                'risk_controls_enforced':enforce_risk,'daily_risk_ledger':{'controls_enforced':enforce_risk,'hard_daily_loss_limit':float(daily),'realized_loss':realized_loss,'declared_external_open_risk':float(external),'protected_reserve':float(reserve),'remaining_after_proposal':float(daily-external-reserve-risk-Decimal(str(realized_loss)))},
                'margin_required':float(required),'available_funds':float(cash),'warnings':warnings,'protection':protection,'order_route':'SUPER' if protection else 'NORMAL',
                'live_submission_enabled':bool(self.account['live_enabled']) and self.execution_allowed(),'submission_eligible':True,
                'state_snapshot':state_snapshot,'state_signature':hashlib.sha256(json.dumps(state_snapshot,sort_keys=True).encode()).hexdigest()}

    def prepare(self,payload):
        with self.lock:
            preview=self._preflight(deepcopy(payload))
            preview_id='DHAN-'+secrets.token_hex(8).upper()
            preview.update(preview_id=preview_id,confirmation_phrase='CONFIRM '+preview_id)
            self.previews[preview_id]={'preview':deepcopy(preview),'payload':deepcopy(payload),'expires':self.now()+timedelta(seconds=120)}
            self.previews={k:v for k,v in self.previews.items() if v['expires']>self.now()}
            return preview

    @contextmanager
    def _submission_lock(self):
        from .file_lock import lock_file, unlock_file
        self.folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(self.folder/'dhan-submission.lock',os.O_RDWR|os.O_CREAT,0o600)
        acquired=False
        try:
            try:lock_file(fd,blocking=False);acquired=True
            except OSError:raise PermissionError('Another Dhan submission is in progress for this account.') from None
            yield
        finally:
            if acquired:unlock_file(fd)
            os.close(fd)

    def submit(self,preview_id,confirmation):
        with self.lock, self._submission_lock():
            stored=self.previews.get(preview_id)
            if not stored or self.now()>stored['expires']:raise ValueError('Dhan preview expired; prepare a new ticket.')
            if confirmation!=stored['preview']['confirmation_phrase']:raise ValueError('Review the Dhan ticket and provide its exact confirmation.')
            if not self.account['live_enabled']:raise PermissionError('Live capability is disabled for this Dhan account.')
            if not self.execution_allowed():raise PermissionError('Execution is halted by the application policy.')
            fresh=self._preflight(stored['payload'])
            if fresh['ticket']!=stored['preview']['ticket'] or fresh['state_signature']!=stored['preview']['state_signature']:
                del self.previews[preview_id]
                raise PreviewChanged(self.prepare(stored['payload']))
            del self.previews[preview_id]
            return self._send(preview_id,fresh)

    def _send(self,preview_id,fresh):
        ticket={**fresh['ticket'],'correlationId':preview_id}
        endpoint='/super/orders' if fresh.get('order_route')=='SUPER' else '/orders'
        quote=self._fresh_preview_quote(self._client(),ticket['exchangeSegment'],ticket['securityId'])
        try:
            bid=number(quote['depth']['buy'][0]['price'],'Bid',True)
            ask=number(quote['depth']['sell'][0]['price'],'Ask',True)
        except (KeyError,IndexError,TypeError):
            raise ValueError('Dhan executable depth became unavailable before submission.') from None
        if bid>ask or (ticket['transactionType']=='BUY' and ask>number(ticket['price'],'Limit price')) or (ticket['transactionType']=='SELL' and bid<number(ticket['price'],'Limit price')):
            raise ValueError('Dhan executable quote moved beyond the reviewed limit. Prepare and review a new preview; no order was sent.')
        journal=self.folder/'dhan-orders'/ (preview_id+'.json')
        journal.parent.mkdir(exist_ok=True,mode=0o700)
        if journal.exists():raise ValueError('Dhan ticket was already submitted; reconcile its correlation ID.')
        _atomic_private_write(journal,json.dumps({'status':'SUBMITTING','ticket':ticket,'endpoint':endpoint,'protection':fresh.get('protection')}))
        try:
            result=self._client().request('POST',endpoint,ticket)
            if not isinstance(result,dict) or not result.get('orderId'):raise RuntimeError('Dhan submission result is uncertain.')
        except DhanAPIError as error:
            if error.definitive_rejection:
                _atomic_private_write(journal,json.dumps({'status':'REJECTED','ticket':ticket,'endpoint':endpoint,'reason':str(error)}))
                return {'preview_id':preview_id,'broker':'DHAN','account_id':self.account['id'],'status':'REJECTED','order_ids':[],
                        'message':str(error)+' No order was acknowledged; submissions are not retried automatically.'}
            _atomic_private_write(journal,json.dumps({'status':'UNKNOWN','ticket':ticket,'endpoint':endpoint,'protection':fresh.get('protection')}))
            if self.execution_halt:self.execution_halt(preview_id,'DHAN_EXECUTION_STATUS_UNCERTAIN')
            return {'preview_id':preview_id,'broker':'DHAN','account_id':self.account['id'],'status':'UNKNOWN','message':'Dhan response is uncertain; reconcile before another order. No automatic retry.'}
        except Exception:
            _atomic_private_write(journal,json.dumps({'status':'UNKNOWN','ticket':ticket,'endpoint':endpoint,'protection':fresh.get('protection')}))
            if self.execution_halt:self.execution_halt(preview_id,'DHAN_EXECUTION_STATUS_UNCERTAIN')
            return {'preview_id':preview_id,'broker':'DHAN','account_id':self.account['id'],'status':'UNKNOWN','message':'Submission outcome is uncertain. Reconcile this correlation ID in Dhan before any new order; automatic retry is disabled.'}
        _atomic_private_write(journal,json.dumps({'status':result.get('orderStatus','PENDING'),'ticket':ticket,'order_id':result['orderId'],'endpoint':endpoint,'protection':fresh.get('protection')}))
        return {'preview_id':preview_id,'broker':'DHAN','account_id':self.account['id'],'status':result.get('orderStatus','PENDING'),'order_ids':[result['orderId']],
                'order_route':fresh.get('order_route','NORMAL'),'protection_requested':bool(fresh.get('protection')),'protection_confirmed':False,'message':'Dhan acknowledged the order. Verify fills and linked exit legs in Dhan; acknowledgement is not protection confirmation.'}

    def prepare_batch(self,payload):
        with self.lock:
            items=payload.get('items')
            if not isinstance(items,list) or not 1<=len(items)<=20:
                raise ValueError('Choose between one and twenty Dhan tickets.')
            previews=[];seen=set()
            for item in items:
                if not isinstance(item,dict) or str(item.get('broker','')).upper()!='DHAN' or item.get('account_id',self.account['id'])!=self.account['id']:
                    raise PermissionError('Every Dhan batch item must belong to the selected Dhan account.')
                item={**item,'broker':'DHAN','account_id':self.account['id']}
                preview=self._preflight(item)
                key=(preview['ticket']['exchangeSegment'],preview['ticket']['securityId'])
                if key in seen:raise ValueError('A Dhan batch cannot repeat the same contract.')
                seen.add(key);previews.append(preview)
            risk=sum(p['instrument']['worst_case_risk'] for p in previews)
            margin=sum(p['margin_required'] for p in previews)
            available=min(p['available_funds'] for p in previews)
            remaining=min(p['daily_risk_ledger']['remaining_after_proposal']+p['instrument']['worst_case_risk'] for p in previews)
            if margin>available or (any(p.get('risk_controls_enforced',True) for p in previews) and risk>remaining):raise ValueError('Combined Dhan batch exceeds available funds or daily risk budget.')
            budget=payload.get('allocation_budget')
            if budget is not None and margin>float(number(budget,'Allocation budget',True)):
                raise ValueError('Dhan batch margin exceeds the selected allocation budget. Adjust quantities and prepare again.')
            preview_id='DHAN-BATCH-'+secrets.token_hex(7).upper()
            preview={'broker':'DHAN','account_id':self.account['id'],'preview_id':preview_id,'confirmation_phrase':'CONFIRM '+preview_id,
                     'items':previews,'excluded':[],'aggregate':{'order_count':len(previews),'total_worst_case_risk':risk,'cash_reserved':margin},
                     'live_submission_enabled':bool(self.account['live_enabled']) and self.execution_allowed(),'submission_eligible':True,
                     'warnings':['Each exact LIMIT order is sent sequentially; submission stops on a rejection or uncertain result. No automatic retry.']}
            self.previews[preview_id]={'preview':deepcopy(preview),'payload':deepcopy(payload),'expires':self.now()+timedelta(seconds=120)}
            return preview

    def submit_batch(self,preview_id,confirmation):
        with self.lock, self._submission_lock():
            stored=self.previews.get(preview_id)
            if not stored or self.now()>stored['expires']:raise ValueError('Dhan batch preview expired.')
            if confirmation!=stored['preview']['confirmation_phrase']:raise ValueError('Confirm the exact reviewed Dhan batch.')
            if not self.account['live_enabled'] or not self.execution_allowed():raise PermissionError('Dhan live execution is disabled or halted.')
            fresh=self.prepare_batch(stored['payload'])
            self.previews.pop(fresh['preview_id'],None)
            if any(a['ticket']!=b['ticket'] or a['state_signature']!=b['state_signature'] for a,b in zip(fresh['items'],stored['preview']['items'])):
                self.previews.pop(preview_id,None)
                raise PreviewChanged(self.prepare_batch(stored['payload']))
            self.previews.pop(preview_id,None)
            results=[];sent_risk=0.0
            for index,(item,approved) in enumerate(zip(stored['payload']['items'],fresh['items'])):
                try:
                    # Include this batch's acknowledged exposure when refreshing subsequent tickets.
                    item={**item,'broker':'DHAN','account_id':self.account['id'],
                          'external_open_risk':float(item.get('external_open_risk') or 0)+sent_risk}
                    current=self._preflight(item)
                    if current['ticket']!=approved['ticket']:raise ValueError('Dhan batch ticket changed before submission; remaining orders were stopped.')
                    acknowledged={oid for result in results for oid in result.get('order_ids',[])}
                    unrelated={**current['state_snapshot'],'pending':[row for row in current['state_snapshot']['pending'] if row.get('orderId') not in acknowledged]}
                    if unrelated!=approved['state_snapshot']:
                        raise ValueError('Dhan account exposure changed during the batch; remaining orders were stopped.')

                    if not self.account['live_enabled'] or not self.execution_allowed():raise PermissionError('Dhan execution halted during batch.')
                    result=self._send(preview_id+'-'+str(index+1),current)
                    results.append(result)
                    sent_risk+=current['instrument']['worst_case_risk']
                    if result['status'] in ('UNKNOWN','REJECTED','CANCELLED','EXPIRED'):break
                except Exception:
                    return {'preview_id':preview_id,'broker':'DHAN','status':'PARTIAL' if results else 'STOPPED','results':results,
                            'message':'Batch stopped before the remaining orders. Reconcile acknowledged orders in Dhan and prepare a new reviewed batch; no automatic retry.'}
            complete=len(results)==len(fresh['items']) and all(r['status'] not in ('UNKNOWN','REJECTED','CANCELLED','EXPIRED') for r in results)
            return {'preview_id':preview_id,'broker':'DHAN','status':'ACKNOWLEDGED' if complete else 'PARTIAL','results':results,
                    'message':'Dhan batch acknowledgements recorded; verify fills in Dhan. No automatic retry.'}

    def reconcile(self):
        with self.lock, self._submission_lock():
            client=self._client();profile=client.request('GET','/profile')
            if str(profile.get('dhanClientId'))!=client.client_id:raise PermissionError('Dhan token belongs to a different client ID.')
            rows=[]
            for path in sorted((self.folder/'dhan-orders').glob('*.json')):
                record=json.loads(path.read_text())
                if record.get('status') in ('UNKNOWN','SUBMITTING','TRANSIT','PENDING','PART_TRADED'):
                    try:
                        if record.get('endpoint')=='/super/orders':
                            listed=client.request('GET','/super/orders')
                            matches=[row for row in listed if row.get('correlationId')==path.stem and str(row.get('dhanClientId'))==client.client_id]
                            result=matches[0] if len(matches)==1 else {}
                        else:result=client.request('GET','/orders/external/'+path.stem)
                        if isinstance(result,dict) and result.get('orderId') and result.get('correlationId')==path.stem and str(result.get('dhanClientId'))==client.client_id and result.get('orderStatus') in ('TRANSIT','PENDING','PART_TRADED','TRADED','CANCELLED','REJECTED','EXPIRED','CLOSED'):
                            record.update(status=result['orderStatus'],order_id=result['orderId'])
                            _atomic_private_write(path,json.dumps(record))
                    except (RuntimeError,ValueError):pass
                rows.append({'correlation_id':path.stem,'status':record['status'],'order_id':record.get('order_id')})
            return {'broker':'DHAN','account_id':self.account['id'],'orders':rows,
                    'unresolved':sum(row['status'] in ('UNKNOWN','SUBMITTING') for row in rows)}
