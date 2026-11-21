"""Private broker-native recommendation mapping, quotes and reviewed tickets."""
from datetime import datetime
from decimal import Decimal
import hashlib,math,re,time
from .recommendation_text import parse_text
from .dhan_execution import IST,contract_underlying,fresh_quote_snapshot

NAMES={'DHAN':'Dhan','MOTILAL_OSWAL':'Motilal Oswal','DELTA_INDIA':'Delta India'}
def normalized(v):return re.sub('[^A-Z0-9]','',str(v).upper())
def expiry_matches(expiry,hint):
    if not hint:return True
    try:d=datetime.fromisoformat(expiry[:10])
    except (ValueError,TypeError):return False
    return d.day==hint['day'] and d.strftime('%b').upper()==hint['month'] and (not hint.get('year') or d.year==2000+int(hint['year'][-2:]))

class AccountParser:
    def __init__(self,account,execution):self.account=account;self.execution=execution;self.previews={}
    def contracts(self,parsed):
        broker=self.account['broker'];today=datetime.now(IST).date().isoformat();rows=[]
        if broker=='DHAN':
            client=self.execution._client();profile=client.request('GET','/profile')
            if str(profile.get('dhanClientId'))!=str(client.client_id):raise PermissionError('Dhan profile differs from the selected account.')
            desired=normalized(parsed.get('underlying'))
            native=re.search(r'\b(NSE_EQ|BSE_EQ|NSE_FNO|BSE_FNO|MCX_COMM):(\d+)\b',parsed['source_text'].upper())
            for r in self.execution.master.load(datetime.now(IST)):
                host=contract_underlying(r) if r['SEM_SEGMENT']!='E' else r['SEM_TRADING_SYMBOL']
                if native:
                    if str(r['SEM_SMST_SECURITY_ID'])!=native.group(2):continue
                elif normalized(host)!=desired:continue
                segment=r['SEM_EXM_EXCH_ID']+{'E':'_EQ','D':'_FNO','M':'_COMM'}.get(r['SEM_SEGMENT'],'_UNSUPPORTED')
                if segment.endswith('_UNSUPPORTED'):continue
                option=r.get('SEM_OPTION_TYPE');expiry=r.get('SEM_EXPIRY_DATE','')[:10]
                if r['SEM_SEGMENT']=='E' and r.get('SEM_SERIES') not in ('EQ','A','B','X','XT','T'):continue
                rows.append(dict(symbol=segment+':'+str(r['SEM_SMST_SECURITY_ID']),security_id=str(r['SEM_SMST_SECURITY_ID']),exchange_segment=segment,description=r.get('SEM_CUSTOM_SYMBOL') or r['SEM_TRADING_SYMBOL'],underlying=contract_underlying(r) if r['SEM_SEGMENT']!='E' else r['SEM_TRADING_SYMBOL'],option_type=option if option in ('CE','PE') else None,expiry=expiry if expiry and expiry!='0000-00-00' else None,strike=float(r.get('SEM_STRIKE_PRICE') or 0),lot_size=int(float(r['SEM_LOT_UNITS'])),tick_size=float(r['SEM_TICK_SIZE'])/100,instrument=r.get('SEM_INSTRUMENT_NAME','')))
        elif broker=='MOTILAL_OSWAL':
            self.execution.ready()
            from .motilal_strategy_broker import cash_row
            for exchange in ('NSE','BSE','NSEFO','BSEFO','MCX'):
                for r in self.execution.master.rows(exchange):
                    if r.get('suspended') or r.get('banned'):continue
                    if r.get('option_type') not in ('CE','PE') and not cash_row(r) and 'FUT' not in str(r.get('instrument','')):continue
                    rows.append(dict(r,description=r.get('name') or r['symbol'],option_type=r.get('option_type') if r.get('option_type') in ('CE','PE') else None))
        elif broker=='DELTA_INDIA':
            for r in self.execution.catalog()['instruments']:
                typ={'call_options':'CE','put_options':'PE'}.get(r['contract_type']);expiry=r.get('settlement_time')
                rows.append(dict(symbol=r['symbol'],description=r.get('description') or r['symbol'],underlying=r['underlying'],option_type=typ,expiry=expiry[:10] if expiry else None,strike=float(r.get('strike_price') or 0),lot_size=1,tick_size=float(r['tick_size']),instrument=r['contract_type']))
        else:raise ValueError('No native parser adapter for selected broker.')
        rows=[r for r in rows if not r.get('expiry') or r['expiry']>=today]
        exact=[r for r in rows if re.search(r'(?<![A-Z0-9])'+re.escape(r['symbol'])+r'(?![A-Z0-9])',parsed['source_text'].upper())]
        if exact:
            return [r for r in exact if (not parsed.get('option_type') or r.get('option_type')==parsed['option_type']) and (parsed.get('strike') is None or abs(float(r.get('strike') or 0)-parsed['strike'])<.00001) and expiry_matches(r.get('expiry'),parsed.get('expiry_hint'))]
        underlying=normalized(parsed.get('underlying'));matches=[]
        hint=parsed.get('expiry_hint');option=parsed.get('option_type')
        exchange=next((v for v in ('MCX','BSE','NSE') if re.search(r'\b'+v+r'\b',parsed['source_text'].upper())),None)
        futures=bool(re.search(r'\bFUT(?:URE)?S?\b',parsed['source_text'].upper()))
        for r in rows:
            if normalized(r.get('underlying'))!=underlying or r.get('option_type')!=option:continue
            if exchange and not str(r.get('exchange_segment') or r.get('exchange') or '').startswith(exchange):continue
            expiry=r.get('expiry')
            if expiry and expiry<today:continue
            if option and (parsed.get('strike') is None or abs(float(r.get('strike') or 0)-parsed['strike'])>.00001):continue
            if not option and bool(expiry)!=futures and broker!='DELTA_INDIA':continue
            if not expiry_matches(expiry,hint):continue
            matches.append(r)
        matches.sort(key=lambda r:(r.get('expiry') or '',r['symbol']))
        # Nearest expiry is inherited only when it resolves one native identity.
        if option and not hint and matches:
            earliest=matches[0].get('expiry');matches=[r for r in matches if r.get('expiry')==earliest]
        return matches[:30]
    def parse(self,payload):
        parsed=parse_text(payload.get('text'));candidates=self.contracts(parsed)
        mapping=dict(status='EXACT',contract=candidates[0],expiry_inferred=bool(parsed.get('option_type') and not parsed.get('expiry_hint'))) if len(candidates)==1 else dict(status='AMBIGUOUS' if candidates else 'UNRESOLVED',candidates=candidates,message='Include the exact native symbol, exchange and expiry to resolve one contract.')
        return dict(status='REVIEW_ONLY',broker=self.account['broker'],account_id=self.account['id'],parsed=parsed,mapping=mapping,trailing_plan=[],execution=dict(prepare=self.account['broker'] in ('DHAN','MOTILAL_OSWAL'),submit=self.account['broker']=='DHAN' or self.account['broker']=='MOTILAL_OSWAL' and bool(mapping.get('contract')) and not mapping['contract'].get('option_type'),entry_modes=['LIMIT'] if self.account['broker'] in ('DHAN','MOTILAL_OSWAL') else [],protection=False),message='Native account mapping only. No order, stop or trailing instruction has been sent.')
    def exact(self,payload):
        result=self.parse(payload);c=result['mapping'].get('contract')
        if not c or c['symbol']!=payload.get('symbol'):raise ValueError('Parse an exact contract again for this selected account.')
        return result,c
    def quote(self,payload):
        _,c=self.exact(payload);broker=self.account['broker']
        if broker=='DHAN':q,stamp=fresh_quote_snapshot(self.execution._client(),c['exchange_segment'],c['security_id']);ltp=q.get('last_price')
        elif broker=='MOTILAL_OSWAL':
            from .motilal_strategy_broker import Broker
            adapter=Broker(self.execution)
            try:q=adapter.quote(c['symbol']);ltp=q.get('ltp') or q.get('last_price')
            finally:adapter.stop()
            stamp=time.time()
        else:q=self.execution.ticker(c['symbol']);ltp=q.get('mark_price') or q.get('last_price') or q.get('ltp');stamp=time.time()
        ltp=float(ltp)
        if not math.isfinite(ltp) or ltp<=0:raise ValueError('Native quote unavailable.')
        return dict(status='READY',broker=broker,account_id=self.account['id'],symbol=c['symbol'],ltp=ltp,currency=q.get('quote_currency','USD') if broker=='DELTA_INDIA' else 'INR',fetched_at=datetime.fromtimestamp(stamp,IST).isoformat(),provider_timestamp=None,freshness='UNCONFIRMED',message='Selected-account quote received. No execution authority.')
    def analysis(self,payload):
        result,c=self.exact(payload);parsed=result['parsed'];quote=self.quote(payload)
        entry=parsed.get('entry');stop=parsed.get('stop_loss');targets=parsed.get('targets') or []
        valid=bool(entry and stop and targets and ((parsed['action']=='BUY' and stop<entry<min(targets)) or (parsed['action']=='SELL' and stop>entry>max(targets))))
        return dict(status='READY',broker=self.account['broker'],account_id=self.account['id'],advisory_only=True,quote=quote,entry=entry,stop=stop,targets=targets,reward_to_risk=abs(targets[0]-entry)/abs(entry-stop) if valid else None,message='Parsed levels are consistent with the stated direction; this is not a timeframe-based trade recommendation.' if valid else 'Entry, stop and target evidence is incomplete or inconsistent. No execution allowed.',intraday=None,swing=None)
    def prepare(self,payload,csrf):
        result,c=self.exact(payload);p=result['parsed']
        if self.account['broker']=='MOTILAL_OSWAL':
            if c.get('option_type') or c.get('exchange') not in ('NSE','BSE'):
                return dict(result,quote=self.quote(payload),submission_eligible=False,message='Native contract and quote reviewed. This parser has no verified ATM-only option/futures entry adapter; use the selected account’s native ticket.')
            if payload.get('entry_mode',p.get('entry_instruction'))!='LIMIT' or payload.get('protect_after_fill'):raise ValueError('This Motilal parser route supports reviewed cash LIMIT entries without automatic parser protection.')
            mode=payload.get('mode')
            if mode not in ('PAPER','LIVE'):raise ValueError('Choose Paper or Live explicitly for this Motilal ticket.')
            self.execution.ready();user_id=self.account.get('user_id')
            if not user_id:raise PermissionError('Authenticated owner identity is required for native tickets.')
            if payload.get('amount_review') is True:
                from .motilal_strategy_broker import Broker
                adapter=Broker(self.execution)
                try:
                    if p['action']!='BUY':raise ValueError('This amount parser route has no verified native sale mapping.')
                    order=adapter.order(c['symbol'],int(payload.get('lots',1))*c['lot_size'],1,adapter.quote(c['symbol']))
                    order['limitPrice']=float(payload.get('limit_price') or p.get('entry'))
                    adapter.preflight(order,{})
                finally:adapter.stop()
            product={'INTRADAY':'VALUEPLUS','CNC':'DELIVERY'}.get(payload.get('amount_product'),'VALUEPLUS')
            preview=self.execution.tickets.preview(user_id,dict(account_id=self.account['id'],broker='MOTILAL_OSWAL',mode=mode,symbol=c['symbol'],side=p['action'],product=product,lots=payload.get('lots',1),limit_price=payload.get('limit_price') or p.get('entry'),max_notional=payload.get('max_notional')))
            key='MO-'+preview['ticket_id'];self.previews[key]=hashlib.sha256(csrf.encode()).hexdigest()
            if payload.get('amount_review') is True:
                if not hasattr(self,'amount_previews'):self.amount_previews={}
                self.amount_previews[key]=dict(payload)
                preview.update(live_submission_enabled=bool(self.account.get('live_enabled')) and mode=='LIVE',margin_required=preview['order_value'])
            return dict(preview,preview_id=key,confirmation_phrase=preview['confirmation'],submission_eligible=True,message='Review the exact native Motilal cash LIMIT ticket. Parsed stop/targets are advisory; no parser protection is attached.')
        if self.account['broker']!='DHAN':return dict(result,quote=self.quote(payload),submission_eligible=False,message='Native parser mapping and quotes are available. Reviewed entry execution is not integrated for this broker; use its native order ticket.')
        if payload.get('mode','LIVE')!='LIVE':raise ValueError('Dhan parser has no Paper entry-ticket adapter. No mode was changed and no order was prepared.')
        if payload.get('entry_mode',p.get('entry_instruction'))!='LIMIT':raise ValueError('Dhan parser supports LIMIT review only; a trigger recommendation is not converted into a limit order.')
        if payload.get('protect_after_fill'):raise ValueError('Parser protection worker is unavailable for Dhan. No entry was prepared.')
        lots=Decimal(str(payload.get('lots',1)))
        if not lots.is_finite() or lots<=0 or lots!=int(lots):raise ValueError('Choose positive whole lots.')
        args=dict(proposal={'kind':'NATIVE'},security_id=c['security_id'],exchange_segment=c['exchange_segment'],quantity=int(lots)*c['lot_size'],transaction_type=p['action'],limit_price=payload.get('limit_price') or p.get('entry'),invalidation=p.get('stop_loss'),target_price=(p.get('targets') or [None])[0])
        if payload.get('amount_review') is True:
            args.update(manual_amount_budget=payload.get('manual_amount_budget'),product_type=payload.get('amount_product'),external_open_risk=payload.get('external_open_risk'),daily_loss_limit=payload.get('daily_loss_limit',5000),idea_risk_limit=payload.get('idea_risk_limit',2000),risk_reserve=payload.get('risk_reserve',1000))
        preview=self.execution.prepare(args);self.previews[preview['preview_id']]=hashlib.sha256(csrf.encode()).hexdigest()
        return dict(preview,mode='LIVE',broker='DHAN',account_id=self.account['id'],message='Review this native Dhan ticket and enter its confirmation. Parsed stop/targets are advisory and are not attached to this NORMAL entry.')
    def submit(self,payload,csrf):
        if payload.get('live_confirmation') is not True:raise PermissionError('Explicit confirmation of this reviewed broker order is required.')
        key=str(payload.get('preview_id') or '')
        if self.account['broker'] not in ('DHAN','MOTILAL_OSWAL') or self.previews.get(key)!=hashlib.sha256(csrf.encode()).hexdigest():raise PermissionError('Prepare a ticket in this exact account and session before submitting.')
        if self.account['broker']=='MOTILAL_OSWAL':
            if key in getattr(self,'amount_previews',{}):self.prepare(self.amount_previews[key],csrf)
            return self.execution.tickets.submit(self.account['user_id'],key.removeprefix('MO-'),payload.get('confirmation'))
        return self.execution.submit(key,payload.get('confirmation'))
