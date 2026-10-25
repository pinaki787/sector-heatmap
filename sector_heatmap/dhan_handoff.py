"""Broker-native, read-only Dhan evidence for the shared Analysis Handoff."""
from datetime import datetime
from .dhan_execution import IST, fresh_quote_snapshot, contract_underlying
from .handoff import build_long_option_proposals

class DhanHandoff:
    broker = 'DHAN'
    def __init__(self, execution, sectors):
        self.execution, self.sectors = execution, sectors
        self.client = execution._client()
        sectors.provider.prepare()

    def candidates(self, mode):
        snap = self.sectors.snapshot(mode)
        live = [dict(row, drivers=row.get('constituent_movers', [])) for row in snap.get('sectors', [])]
        result = self.sectors.alignment_candidates(live, mode=mode)
        for candidate in result.get('candidates', []):
            if candidate.get('kind') == 'stock':
                candidate['price'], stamp = self.quote(candidate['symbol'])
                candidate['provider_tick_timestamp_iso'] = datetime.fromtimestamp(stamp, IST).isoformat()
                candidate['broker'] = 'DHAN'
        result['broker'] = 'DHAN'
        return result

    def positions(self):
        rows = self.client.request('GET', '/positions')
        if not isinstance(rows, list) or any(str(row.get('dhanClientId', self.client.client_id)) != self.client.client_id for row in rows):
            raise PermissionError('Dhan positions do not match the selected account.')
        masters = self.execution.master.load(datetime.now(IST))
        lookup = {(row['SEM_EXM_EXCH_ID']+{'E':'_EQ','D':'_FNO','M':'_COMM','I':''}.get(row['SEM_SEGMENT'],''),str(row['SEM_SMST_SECURITY_ID'])):row for row in masters}
        result=[]
        for row in rows:
            if not float(row.get('netQty') or 0): continue
            meta=lookup.get((row.get('exchangeSegment'),str(row.get('securityId'))))
            if not meta: raise ValueError('Open Dhan position has no verified master mapping.')
            ticker=contract_underlying(meta)
            result.append(dict(symbol=meta['SEM_EXM_EXCH_ID']+':'+ticker+'-EQ', netQty=row['netQty']))
        return result

    def orders(self):
        rows=self.client.request('GET','/orders')
        if not isinstance(rows,list) or any(str(r.get('dhanClientId',self.client.client_id))!=self.client.client_id for r in rows):
            raise PermissionError('Dhan orders do not match selected account.')
        masters=self.execution.master.load(datetime.now(IST))
        lookup={(r['SEM_EXM_EXCH_ID']+{'E':'_EQ','D':'_FNO','M':'_COMM','I':''}.get(r['SEM_SEGMENT'],''),str(r['SEM_SMST_SECURITY_ID'])):r for r in masters}
        result=[]
        for row in rows:
            if row.get('orderStatus') in ('TRADED','CANCELLED','REJECTED','EXPIRED'):continue
            if row.get('orderStatus') not in ('TRANSIT','PENDING','PART_TRADED'):raise ValueError('Unknown Dhan order status; duplicate entry cannot be excluded.')
            meta=lookup.get((row.get('exchangeSegment'),str(row.get('securityId'))))
            if not meta:raise ValueError('Pending Dhan order has no verified native master mapping.')
            result.append(dict(symbol=meta['SEM_EXM_EXCH_ID']+':'+contract_underlying(meta)+'-EQ',status=row['orderStatus']))
        return result

    def funds(self):
        data=self.client.request('GET','/fundlimit')
        if str(data.get('dhanClientId')) != self.client.client_id:
            raise PermissionError('Dhan funds do not match the selected account.')
        return dict(connected=True,available_funds=data.get('availabelBalance',data.get('availableBalance')))

    def quote(self, symbol):
        meta=self.sectors.provider.resolve(symbol)
        row, received=fresh_quote_snapshot(self.client,meta['exchangeSegment'],meta['securityId'])
        price=float(row.get('last_price') or 0)
        if price<=0:raise ValueError('Dhan underlying price unavailable.')
        return price, received

    def tick(self, symbol):
        meta=self.sectors.provider.resolve(symbol)
        rows=self.execution.master.load(datetime.now(IST))
        match=[r for r in rows if str(r['SEM_SMST_SECURITY_ID'])==meta['securityId'] and r['SEM_EXM_EXCH_ID']=='NSE' and r['SEM_SEGMENT']=='E']
        if len(match)!=1:raise ValueError('Dhan cash tick is missing or ambiguous.')
        return float(match[0]['SEM_TICK_SIZE'])/100

    def options(self, symbol, direction, risk):
        meta=self.sectors.provider.resolve(symbol)
        master=self.execution.master.load(datetime.now(IST))
        if meta['exchangeSegment']=='NSE_EQ':
            host=[row for row in master if row['SEM_SEGMENT']=='E' and str(row['SEM_SMST_SECURITY_ID'])==meta['securityId'] and row['SEM_EXM_EXCH_ID']=='NSE']
            if len(host)==1 and not any(row['SEM_SEGMENT']=='D' and contract_underlying(row)==host[0]['SEM_TRADING_SYMBOL'] for row in master):
                raise ValueError('Dhan master lists no option contracts for this equity.')
        body=dict(UnderlyingScrip=int(meta['securityId']),UnderlyingSeg=meta['exchangeSegment'])
        expiries=self.client.request('POST','/optionchain/expirylist',body).get('data')
        today=datetime.now(IST).date().isoformat()
        active=sorted(e for e in (expiries or []) if isinstance(e,str) and e>=today)
        if not active:raise ValueError('Dhan has no active option expiry for this underlying.')
        if meta['exchangeSegment'] in ('NSE_EQ','BSE_EQ'):
            from .stock_expiry_policy import require_options_allowed
            require_options_allowed(active,datetime.now(IST))
        expiry=active[0]
        raw=self.client.request('POST','/optionchain',dict(body,Expiry=expiry))
        if raw.get('status')!='success':raise ValueError('Dhan option-chain request failed.')
        data=raw.get('data') or {}
        epoch=str(int(datetime.fromisoformat(expiry).replace(hour=15,minute=30,tzinfo=IST).timestamp()))
        rows=[dict(option_type='',ltp=data.get('last_price'))];masters={}
        master=self.execution.master.load(datetime.now(IST))
        for strike, pair in (data.get('oc') or {}).items():
            for side in ('ce','pe'):
                item=pair.get(side) or {};sid=str(item.get('security_id') or '')
                matches=[r for r in master if str(r['SEM_SMST_SECURITY_ID'])==sid and r['SEM_EXM_EXCH_ID']=='NSE' and r['SEM_SEGMENT']=='D' and r['SEM_OPTION_TYPE']==side.upper() and r['SEM_EXPIRY_DATE'][:10]==expiry and float(r['SEM_STRIKE_PRICE'])==float(strike)]
                if len(matches)!=1:continue
                m=matches[0];native='NSE_FNO:'+sid
                rows.append(dict(symbol=native,option_type=side.upper(),strike_price=float(strike),ltp=item.get('last_price'),
                    bid=item.get('top_bid_price'),ask=item.get('top_ask_price'),oi=item.get('oi'),volume=item.get('volume'),
                    greeks=dict(item.get('greeks') or {},iv=item.get('implied_volatility'))))
                masters[native]=dict(exchange_token=sid,lot_size=int(float(m['SEM_LOT_UNITS'])),tick_size=float(m['SEM_TICK_SIZE'])/100,expiry_epoch=epoch)
        result=build_long_option_proposals({'data':{'optionsChain':rows}},dict(date=datetime.fromisoformat(expiry).strftime('%d-%m-%Y'),expiry=epoch),masters,direction,risk)
        result['broker']='DHAN'
        for proposal in result.get('proposals',[]):
            proposal['broker']='DHAN'
            for leg in proposal.get('legs',[]):leg['broker']='DHAN'
        return result
