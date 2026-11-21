"""Account-native positions and conservative historical realized-P&L reconstruction."""
from collections import defaultdict,deque
from contextlib import contextmanager
from datetime import datetime,timedelta,time as day_time
from decimal import Decimal,InvalidOperation
import json,threading,time
from .persistent_jobs import checkpoint,JobCancelled,JobInterrupted
from .dhan_execution import IST,DhanAPIError

FEES=('sebiTax','stt','brokerageCharges','serviceTax','exchangeTransactionCharges','stampDuty')
def number(value):
    if value is None or isinstance(value,bool):raise ValueError('Required broker amount is unavailable.')
    try:v=Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError):raise ValueError('Broker amount is invalid.') from None
    if not v.is_finite():raise ValueError('Broker returned a non-finite amount.')
    return v

def period_start(period,now):
    period={'daily':'day','weekly':'week','monthly':'month','annual':'year','yearly':'year'}.get(period,period)
    today=now.astimezone(IST).date()
    if period=='day':start=today
    elif period=='week':start=today-timedelta(days=today.weekday())
    elif period=='month':start=today.replace(day=1)
    elif period=='year':start=today.replace(year=today.year if today.month>=4 else today.year-1,month=4,day=1)
    else:raise ValueError('Choose daily, weekly, monthly or annual P&L.')
    return period,datetime.combine(start,day_time.min,IST)

def trade_time(value):
    moment=datetime.fromisoformat(value)
    return moment.replace(tzinfo=IST) if moment.tzinfo is None else moment.astimezone(IST)

def checked_rows(rows,client_id):
    if not isinstance(rows,list):raise ValueError('Broker returned incomplete account rows.')
    if any(str(r.get('dhanClientId'))!=str(client_id) for r in rows):raise PermissionError('Broker returned rows belonging to another account.')
    return rows

class DhanAccountReports:
    def __init__(self,execution,now=lambda:datetime.now(IST)):
        self.execution=execution;self.now=now;self.cache={};self.lock=threading.RLock()
    @contextmanager
    def report_lock(self):
        while not self.lock.acquire(timeout=1):checkpoint('Waiting for another account report; Stop remains available.')
        try:yield
        finally:self.lock.release()
    def client(self):
        client=self.execution._client();profile=client.request('GET','/profile')
        if str(profile.get('dhanClientId'))!=str(client.client_id):raise PermissionError('Dhan profile differs from selected account.')
        return client
    def positions(self):
        c=self.client();rows=checked_rows(c.request('GET','/positions'),c.client_id)
        def total(key):
            try:return float(sum((number(r.get(key)) for r in rows),Decimal(0)))
            except ValueError:return None
        realized=total('realizedProfit');unrealized=total('unrealizedProfit');positions=[]
        for row in rows:
            qty=number(row.get('netQty'))
            if qty:
                positions.append(dict(symbol=row.get('tradingSymbol') or row.get('securityId'),security_id=row.get('securityId'),exchange_segment=row.get('exchangeSegment'),product=row.get('productType'),netQty=float(qty),netAvg=row.get('costPrice') if row.get('costPrice') is not None else row.get('buyAvg'),pl=row.get('unrealizedProfit')))
        funds=None;funds_error=None
        try:
            raw=c.request('GET','/fundlimit')
            if str(raw.get('dhanClientId'))!=str(c.client_id):raise PermissionError('Funds belong to a different account.')
            funds=raw.get('availabelBalance',raw.get('availableBalance'))
        except PermissionError:raise
        except Exception:funds_error='Funds unavailable; verified positions retained.'
        return dict(broker='DHAN',account_id=self.execution.account['id'],connected=True,positions=positions,realized=realized,unrealized=unrealized,pnl=realized+unrealized if realized is not None and unrealized is not None else None,available_funds=funds,funds_error=funds_error,estimated_net_pnl=None,estimated_charges=dict(available=False,total=None,disclaimer='Current-session broker gross P&L. Fees are not deducted; historical realized P&L is shown separately.'))
    def history(self,c,start,end):
        rows={};cursor=start;pages=0
        while cursor<=end:
            until=min(end,cursor+timedelta(days=29));seen_pages=set()
            for page in range(100):
                checkpoint('Reading Dhan history '+cursor.isoformat()+' – '+until.isoformat()+' · page '+str(page+1),dict(status='READING_HISTORY',broker='DHAN',account_id=self.execution.account['id'],pages_read=pages,rows_read=len(rows),summary={'gross_pnl':None,'net_pnl':None}))
                for attempt in range(3):
                    try:
                        raw=checked_rows(c.request('GET',f'/trades/{cursor.isoformat()}/{until.isoformat()}/{page}'),c.client_id)
                        break
                    except DhanAPIError as error:
                        if not error.rate_limited or attempt==2:raise
                        for remaining in range(20*(attempt+1),0,-1):
                            checkpoint('Dhan history rate limit · retrying this read in '+str(remaining)+'s. Stop remains available.')
                            time.sleep(1)
                pages+=1
                if not raw:break
                fingerprint=json.dumps(raw,sort_keys=True)
                if fingerprint in seen_pages:raise ValueError('Dhan repeated a history page; completeness is unverified.')
                seen_pages.add(fingerprint)
                page_ids=set()
                for row in raw:
                    if not row.get('securityId') or not row.get('exchangeSegment'):raise ValueError('Trade identity is incomplete.')
                    stamp=trade_time(row['exchangeTime'])
                    if not cursor<=stamp.date()<=until:raise ValueError('Dhan history row falls outside the requested range.')
                    trade_id=str(row.get('exchangeTradeId') or '').upper()
                    if trade_id in ('','0','NA','NONE','NULL'):
                        if not row.get('orderId') or not row.get('exchangeOrderId'):raise ValueError('Historical fill identity is unavailable.')
                        # Some Dhan statement rows have exchangeTradeId=0. Order,
                        # exchange order, fill time, side, price and quantity must
                        # then agree; unrelated orders must never collapse to 0.
                        identity=('ORDER_FILL',row['orderId'],row['exchangeOrderId'],row['exchangeTime'],row.get('transactionType'),str(number(row.get('tradedPrice'))),str(number(row.get('tradedQuantity'))))
                    else:identity=('TRADE',trade_id)
                    key=(row['exchangeSegment'],row['securityId'],identity,stamp.date().isoformat())
                    if key in page_ids and identity[0]=='ORDER_FILL':raise ValueError('Duplicate fill without a unique exchange trade ID; completeness is unverified.')
                    page_ids.add(key)
                    if key in rows and rows[key]!=row:raise ValueError('Conflicting duplicate historical fills.')
                    rows[key]=row
            else:raise ValueError('History pagination limit reached; no complete total is available.')
            cursor=until+timedelta(days=1)
        return sorted(rows.values(),key=lambda r:(r['exchangeTime'],str(r['exchangeTradeId']))),pages
    def realized(self,period):
        now=self.now().astimezone(IST);period,start=period_start(period,now)
        with self.report_lock():
            client=self.client();digest=self.execution.credential_digest
            key=(period,start.date().isoformat(),now.date().isoformat(),digest)
            cached=self.cache.get(key)
            if cached and time.monotonic()-cached[0]<60:return cached[1]
            seed=start.date()
            try:
                rows,pages=self.history(client,start.date(),now.date())
                # Empty verified periods and intraday-only books need no opening
                # inventory. Fetch older cost evidence only when carry is present.
                if period!='day' and any(row.get('productType')!='INTRADAY' and row.get('exchangeSegment') in ('NSE_FNO','BSE_FNO') and row.get('drvOptionType') in ('CALL','PUT','CE','PE') for row in rows):
                    seed=start.date()-timedelta(days=366)
                    prior,prior_pages=self.history(client,seed,start.date()-timedelta(days=1))
                    rows=prior+rows;pages+=prior_pages
                result=reconstruct(rows,client.client_id,start,now)
                result.update(broker='DHAN',account_id=self.execution.account['id'],period=period,from_date=start.date().isoformat(),to_date=now.date().isoformat(),history_from=seed.isoformat(),pages_read=pages,updated_at=now.isoformat())
            except (PermissionError,JobCancelled,JobInterrupted):raise
            except Exception as error:
                result=dict(status='UNAVAILABLE',broker='DHAN',account_id=self.execution.account['id'],period=period,supported=False,complete=False,records=[],summary={'gross_pnl':None,'net_pnl':None},message='Historical realized P&L unavailable: '+str(error))
            result.update(mode='LIVE',from_date=start.date().isoformat(),to_date=now.date().isoformat(),currency='INR',basis='FIFO matched broker fills',timezone='Asia/Kolkata')
            if period=='day':
                # The broker's current-session position book is authoritative for
                # daily realized gross; FIFO history is a supplemental breakdown.
                try:current=self.positions()
                except PermissionError:raise
                except Exception:current={}
                gross=current.get('realized')
                if gross is not None:
                    prior=result.get('summary') or {};fees=number(prior['gross_pnl'])-number(prior['net_pnl']) if prior.get('gross_pnl') is not None and prior.get('net_pnl') is not None and abs(number(prior['gross_pnl'])-number(gross))<=Decimal('0.01') else None
                    result.update(status='READY',records_complete=result.get('complete',False),supported=True,complete=True,basis='Dhan current-session position book',summary=dict(gross_pnl=gross,net_pnl=float(number(gross)-fees) if fees is not None else None),message='Daily realized gross is reported by Dhan positions, not unrealized P&L. Fees/net are unavailable unless the matched trade breakdown reconciles.')
            self.cache[key]=(time.monotonic(),result);return result

def reconstruct(rows,client_id,start,now):
    """FIFO matched fills; missing opening basis is never treated as zero cost.

    Seed-window buys establish cost only for fully closed cycles. Overnight CNC
    and futures settlements/corporate actions are not certified by this endpoint.
    Such exits remain explicitly partial rather than inventing realized totals.
    """
    checked_rows(rows,client_id);books=defaultdict(deque);records=[];missing=[];unknown_books=set();all_fees=True;gross_total=Decimal(0);net_total=Decimal(0)
    for row in sorted(rows,key=lambda r:(r['exchangeTime'],str(r.get('exchangeTradeId','')))):
        stamp=trade_time(row['exchangeTime'])
        if stamp>now:raise ValueError('Broker returned a future-dated fill; total is unavailable.')
        side=row.get('transactionType');qty=number(row.get('tradedQuantity'));price=number(row.get('tradedPrice'))
        product=row.get('productType');segment=row.get('exchangeSegment');key=(segment,row.get('securityId'),product,stamp.date() if product=='INTRADAY' else None)
        if product not in ('INTRADAY','CNC','MTF','MARGIN','CO','BO') or segment not in ('NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO','MCX_COMM') or side not in ('BUY','SELL') or qty<=0 or price<=0:
            unknown_books.add(key);books[key].clear()
            if stamp>=start:missing.append('Non-executable or missing-cost statement row for '+str(row.get('tradingSymbol') or row.get('securityId')))
            continue
        fees=all(row.get(f) is not None for f in FEES);fee=sum((number(row[f]) for f in FEES),Decimal(0))/qty if fees else None
        direction=1 if side=='BUY' else -1
        book=books[key]
        # A delivery sell without known acquisition cost is never a short entry.
        if product!='INTRADAY' and side=='SELL' and not book:
            if stamp>=start:
                missing.append('Acquisition cost unavailable for '+str(row.get('tradingSymbol') or row['securityId']))
                records.append(dict(symbol=row.get('tradingSymbol') or row.get('customSymbol') or row['securityId'],closed_at=stamp.isoformat(),exchange_segment=segment,product=product,buy_rate=None,sell_rate=float(price),buy_qty=None,sell_qty=float(qty),pnl=None,fees=None,net_pnl=None,cost_basis_verified=False))
            continue
        while qty and book and book[0]['side']!=direction:
            opening=book[0];matched=min(qty,opening['qty']);gross=(price-opening['price'])*matched*opening['side']
            if stamp>=start:
                # MCX contract multipliers and non-intraday settlement flows need
                # separate verified accounting; price differences are insufficient.
                uncertain=key in unknown_books or segment=='MCX_COMM' or product in ('CNC','MTF') or product!='INTRADAY' and 'FUT' in str(row.get('instrument','')).upper()
                charge=(fee+opening['fee'])*matched if fee is not None and opening['fee'] is not None else None
                if uncertain:
                    missing.append('Cost basis/settlement verification required for '+str(row.get('tradingSymbol') or row['securityId']))
                    records.append(dict(symbol=row.get('tradingSymbol') or row.get('customSymbol') or row['securityId'],closed_at=stamp.isoformat(),exchange_segment=segment,product=product,buy_rate=float(opening['price'] if opening['side']==1 else price),sell_rate=float(price if opening['side']==1 else opening['price']),buy_qty=float(matched),sell_qty=float(matched),pnl=None,fees=None,net_pnl=None,cost_basis_verified=False))
                else:
                    gross_total+=gross
                    if charge is not None:net_total+=gross-charge
                    records.append(dict(symbol=row.get('tradingSymbol') or row.get('customSymbol') or row['securityId'],closed_at=stamp.isoformat(),exchange_segment=segment,product=product,buy_rate=float(opening['price'] if opening['side']==1 else price),sell_rate=float(price if opening['side']==1 else opening['price']),buy_qty=float(matched),sell_qty=float(matched),pnl=float(gross),fees=float(charge) if charge is not None else None,net_pnl=float(gross-charge) if charge is not None else None))
                    all_fees=all_fees and charge is not None
            qty-=matched;opening['qty']-=matched
            if not opening['qty']:book.popleft()
        if qty:book.append(dict(qty=qty,price=price,side=direction,fee=fee))
    # Unclosed seed shorts in overnight instruments may be missing-cost sells.
    for key,book in books.items():
        if key[2]!='INTRADAY' and any(v['side']==-1 for v in book):missing.append('Opening inventory or settlement is incomplete for '+str(key[1]))
    gross=gross_total;net=net_total if all_fees else None
    complete=not missing
    return dict(status='READY' if complete else 'PARTIAL',supported=complete,complete=complete,records=records,summary=dict(gross_pnl=float(gross) if complete else None,net_pnl=float(net) if complete and net is not None else None,matched_gross_pnl=float(gross),matched_trades=sum(r['pnl'] is not None for r in records)),warnings=list(dict.fromkeys(missing)),message='Realized P&L reconstructed from matched broker fills (FIFO); not unrealized P&L. Net includes reported fill charges only.' if complete else 'Partial history/cost basis: matched records are retained, but a complete realized total is unavailable.')
