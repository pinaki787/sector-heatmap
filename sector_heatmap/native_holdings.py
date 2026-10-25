"""Read-only Dhan and Motilal holdings; native identities and data never cross brokers."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from .holdings_analysis import number
from .persistent_jobs import checkpoint

IST=ZoneInfo('Asia/Kolkata')


def quote_time(value):
    if isinstance(value,(int,float)) and not isinstance(value,bool):return value/1000 if value>1e12 else value
    if isinstance(value,str):
        try:
            dt=datetime.fromisoformat(value.replace('Z','+00:00'))
            return dt.replace(tzinfo=IST).timestamp() if dt.tzinfo is None else dt.timestamp()
        except ValueError:pass
        for fmt in ('%d/%m/%Y %H:%M:%S','%d-%m-%Y %H:%M:%S'):
            try:return datetime.strptime(value,fmt).replace(tzinfo=IST).timestamp()
            except ValueError:pass
    return None


class DhanHoldings:
    broker='DHAN'
    scope='Dhan demat/T1 holdings and nonzero open trading positions, shown separately; quantities are not a combined exposure total'
    def __init__(self,execution):
        self.execution=execution;self.client=execution._client();self.identity=execution.account['id'];self.contracts={}
    def inventory(self):
        profile=self.client.request('GET','/profile')
        if str(profile.get('dhanClientId'))!=str(self.client.client_id):raise PermissionError('Dhan holdings token does not belong to the selected account.')
        raw=self.client.request('GET','/holdings')
        if not isinstance(raw,list) or any(not isinstance(r,dict) or str(r.get('dhanClientId',self.client.client_id))!=str(self.client.client_id) for r in raw):raise PermissionError('Dhan holdings have missing or mixed account ownership.')
        positions=self.client.request('GET','/positions')
        if not isinstance(positions,list) or any(not isinstance(r,dict) or str(r.get('dhanClientId',self.client.client_id))!=str(self.client.client_id) for r in positions):raise PermissionError('Dhan positions have missing or mixed account ownership.')
        masters=self.execution.master.load(datetime.now(IST));result=[]
        for index,row in enumerate(raw):
            checkpoint('Mapping Dhan holding '+str(index+1)+'.')
            qty=number(row.get('totalQty'))
            if qty==0:continue
            exchange=str(row.get('exchange') or 'ALL').upper();isin=str(row.get('isin') or '')
            matches=[m for m in masters if m.get('SEM_SEGMENT')=='E' and str(m.get('SEM_SMST_SECURITY_ID'))==str(row.get('securityId')) and m.get('SEM_EXM_EXCH_ID') in ({exchange} if exchange in ('NSE','BSE') else {'NSE','BSE'}) and (not (m.get('SEM_ISIN_CODE') or m.get('SEM_ISIN')) or not isin or str(m.get('SEM_ISIN_CODE') or m.get('SEM_ISIN'))==isin) and (bool(m.get('SEM_ISIN_CODE') or m.get('SEM_ISIN')) or str(m.get('SEM_TRADING_SYMBOL') or '').upper()==str(row.get('tradingSymbol') or '').upper())]
            if len(matches)>1 and exchange=='ALL':matches=[m for m in matches if m.get('SEM_EXM_EXCH_ID')=='NSE']
            meta=matches[0] if len(matches)==1 else None
            symbol=(meta['SEM_EXM_EXCH_ID']+':'+meta['SEM_TRADING_SYMBOL']+'-EQ') if meta else str(row.get('tradingSymbol') or 'Unresolved Dhan holding')
            if meta:self.contracts[symbol]=dict(securityId=str(meta['SEM_SMST_SECURITY_ID']),exchangeSegment=meta['SEM_EXM_EXCH_ID']+'_EQ',instrument='EQUITY')
            result.append(dict(id=str(index),symbol=symbol,quantity=qty,average_price=number(row.get('avgCostPrice')),price=None,quote_timestamp=None,currency='INR',
                               kind='DELIVERY_EQUITY' if meta else 'OTHER_HOLDING',holding_type='MTF funded equity' if number(row.get('mtf_qty')) or number(row.get('mtf_t1_qty')) else 'Demat + T1',native_identity=self.contracts.get(symbol),
                               review_reason='Native Dhan security/ISIN mapping is missing or ambiguous; no alternative broker was used.'))
        for index,row in enumerate(positions):
            qty=number(row.get('netQty'))
            if qty is None:raise ValueError('Dhan position quantity is unavailable; portfolio coverage cannot be established.')
            if qty==0:continue
            segment=str(row.get('exchangeSegment') or '')
            sid=str(row.get('securityId') or '')
            matches=[m for m in masters if str(m.get('SEM_SMST_SECURITY_ID'))==sid and
                     m.get('SEM_EXM_EXCH_ID','')+{'E':'_EQ','D':'_FNO','M':'_COMM','C':'_CURRENCY'}.get(m.get('SEM_SEGMENT'),'_UNSUPPORTED')==segment]
            meta=matches[0] if len(matches)==1 else None
            native=dict(securityId=sid,exchangeSegment=segment) if meta else None
            symbol=segment+':'+str(meta.get('SEM_TRADING_SYMBOL') if meta else row.get('tradingSymbol') or sid or 'Unresolved position')
            avg=number(row.get('costPrice'))
            if not avg or avg<=0:avg=number(row.get('buyAvg' if qty>0 else 'sellAvg'))
            result.append(dict(id='position:'+str(index),symbol=symbol,quantity=qty,average_price=avg,
                               price=None,quote_timestamp=None,currency='INR',kind='OPEN_POSITION',
                               holding_type='Open position · '+str(row.get('productType') or 'Unknown product'),
                               native_identity=native,broker_unrealized_pnl=number(row.get('unrealizedProfit')),
                               review_reason='Open trading position: review entry thesis, direction, existing stop, expiry and any hedge together. Daily delivery swing rules do not establish an exit for this product.' if native else
                               'Open trading position retained, but native instrument mapping is missing or ambiguous; contract-specific analysis is unavailable.'))
        return result
    def enrich(self,rows):
        from .dhan_execution import fresh_quote_snapshot
        for row in rows:
            if row['kind']!='DELIVERY_EQUITY' and not row.get('native_identity'):continue
            checkpoint('Reading Dhan quote for '+row['symbol']+'.')
            meta=row.get('native_identity') or self.contracts[row['symbol']];quote,received=fresh_quote_snapshot(self.client,meta['exchangeSegment'],meta['securityId'])
            row.update(price=number(quote.get('last_price')),quote_timestamp=quote_time(quote.get('last_trade_time')),quote_received_at=received)
        return rows
    def candles(self,row,now):
        from .dhan_sector_analysis import DhanCandleHistoryProvider
        meta=row.get('native_identity') or self.contracts[row['symbol']]
        start=datetime.fromtimestamp(now,IST).date()-timedelta(days=365);end=datetime.fromtimestamp(now,IST).date()+timedelta(days=1)
        raw=self.client.request('POST','/charts/historical',{**meta,'expiryCode':0,'oi':False,'fromDate':start.isoformat(),'toDate':end.isoformat()})
        return DhanCandleHistoryProvider.parse(raw)


class MotilalHoldings:
    broker='MOTILAL_OSWAL'
    scope='Motilal native DP holdings; collateral is included in DP quantity and is not added again'
    def __init__(self,execution):self.execution=execution;self.identity=execution.account['id'];self.contracts={}
    def inventory(self):
        rows=self.execution.book('holdings')['data'];result=[]
        for index,row in enumerate(rows):
            qty=number(row.get('dpquantity'))
            if qty==0:continue
            checkpoint('Mapping Motilal holding '+str(index+1)+'.')
            isin=str(row.get('scripisinno') or '');matches=[]
            for exchange,key in (('NSE','nsesymboltoken'),('BSE','bsescripcode')):
                token=number(row.get(key))
                if not token or token!=int(token):continue
                from .motilal_strategy_broker import cash_row
                found=[m for m in self.execution.master.rows(exchange) if m['token']==int(token) and isin and m.get('isin')==isin and cash_row(m)]
                if len(found)==1:matches=found;break
                if found:break
            meta=matches[0] if len(matches)==1 else None
            symbol=meta['symbol'] if meta else str(row.get('scripname') or 'Unresolved Motilal holding')
            if meta:self.contracts[symbol]={**meta,'securityId':str(meta['token']),'exchangeSegment':meta['exchange']+'_EQ'}
            result.append(dict(id=str(index),symbol=symbol,quantity=qty,average_price=number(row.get('buyavgprice')),price=None,quote_timestamp=None,currency='INR',
                               kind='DELIVERY_EQUITY' if meta else 'OTHER_HOLDING',holding_type='Native DP holding',native_identity=self.contracts.get(symbol),
                               review_reason='Native Motilal security/ISIN mapping is missing or ambiguous; no alternative broker was used.'))
        return result
    def enrich(self,rows):
        for row in rows:
            if row['kind']!='DELIVERY_EQUITY':continue
            meta=row.get('native_identity') or self.contracts[row['symbol']];quote=self.execution.client.quote(meta['exchange'],meta['token'])
            row.update(price=number(quote.get('ltp')),quote_timestamp=quote_time(quote.get('provider_timestamp')),quote_received_at=quote.get('received_at'))
            # A REST receipt cannot masquerade as an exchange price timestamp.
            # Use native socket LTP timing if already available; never stop a shared feed.
            try:
                self.execution.feed.subscribe(meta['exchange'],meta['token']);self.execution.feed.start()
                ltp,stamp=self.execution.feed.price(meta['exchange'],meta['token'])
                row.update(price=number(ltp),quote_timestamp=stamp)
            except ValueError:pass
        return rows
    def candles(self,row,now):
        return self.execution.history.session_candles(row['symbol'],session_open='09:15',minutes=375,limit=3000)
