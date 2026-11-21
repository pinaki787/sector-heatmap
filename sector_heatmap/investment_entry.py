"""Account-owned NSE delivery entry monitoring over Dhan's native LIMIT route."""
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from decimal import ROUND_FLOOR
from pathlib import Path
import json
import os
import secrets
from urllib.parse import quote

from .config import _atomic_private_write
from .dhan_execution import DhanAPIError, number
from .market_calendar import IST, NSE_SPECIAL_SESSIONS, is_trading_day, market_session
from .persistent_jobs import JobCancelled, JobInterrupted


ROUTE = '/api/investment/entry-monitor/'
WORKING = {'TRANSIT', 'PENDING', 'PART_TRADED'}
TERMINAL = {'TRADED', 'EXPIRED', 'CANCELLED', 'REJECTED'}
OPEN_WINDOW = timedelta(minutes=10)
# The NSE post-close session ends at 16:00. Use a later, bounded AMO slot.
AMO_AT = time(16, 15)


def session_slot(now):
    day = now.date()
    if day.year != 2026 or not is_trading_day(day):
        return None
    opening = NSE_SPECIAL_SESSIONS.get(day, (time(9, 15),))[0]
    start = datetime.combine(day, opening, IST)
    if start <= now < start + OPEN_WINDOW:
        return 'OPEN'
    start = datetime.combine(day, AMO_AT, IST)
    if start <= now < start + OPEN_WINDOW:
        return 'AMO'
    return None


def received_quantity(value):
    quantity = number(value, 'Broker quantity')
    if quantity != quantity.to_integral_value():
        raise ValueError('Broker returned a fractional equity quantity.')
    return int(quantity)


from .chart_trade_admission import serialized_dhan_entry, mark_dhan_entry_attempt


class DhanEntry:
    def __init__(self, execution, account_lookup):
        self.execution = execution
        self.account_lookup = account_lookup
        self.folder = Path(execution.folder)
        self.journal = self.folder / 'dhan-orders'

    def contract(self, symbol, now):
        result = self.execution.master.resolve(
            {'underlying': symbol, 'proposal': {'kind': 'EQUITY'}}, now)
        if result['exchange_segment'] != 'NSE_EQ' or result['lot_size'] != 1:
            raise ValueError('This monitor requires an NSE delivery equity traded in single shares.')
        return result

    def plan(self, row, ratio, quantity, now):
        if ratio not in ('50', '56') or type(quantity) is not int or not 0 < quantity <= 2**31 - 1:
            raise ValueError('Choose the 50% or 56% level and enter a whole number of shares.')
        level = row.get('daily_pullback') or {}
        if now.year != 2026:
            raise ValueError('The NSE session calendar needs to be updated before enabling monitoring.')
        session = market_session(now)['last_completed_session']
        if level.get('as_of') != session or not row.get('eligible'):
            raise ValueError('Run a fresh Investment screen with daily Fib prices for this equity.')
        contract = self.contract(row['symbol'], now)
        tick = number(contract['tick_size'], 'NSE tick', True)
        raw = number(level.get('price_' + ratio), 'Fib limit price', True)
        price = (raw / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
        if price <= 0:
            raise ValueError('The Fib level is below the exchange tick.')
        return {
            'account_id': self.execution.account['id'], 'broker': 'DHAN',
            'account_label': self.execution.account['label'], 'symbol': row['symbol'],
            'security_id': str(contract['security_id']), 'ratio': ratio, 'quantity': quantity,
            'limit_price': str(price), 'notional': str(price * quantity),
            'swing_as_of': session, 'swing_high_status': level.get('swing_high_status'),
        }

    def verify_enabled(self):
        account = self.account_lookup()
        if not account.get('live_enabled') or not self.execution.execution_allowed():
            raise PermissionError('Live execution for the selected Dhan account is disabled or halted.')

    def journal_rows(self):
        return [(path, json.loads(path.read_text())) for path in self.journal.glob('*.json')]

    def own_order(self, client, path, record):
        ticket = record['ticket']
        row = client.request('GET', '/orders/external/' + quote(ticket['correlationId'], safe=''))
        if (not isinstance(row, dict) or str(row.get('orderId')) != str(record['order_id'])
                or any(str(row.get(key)) != str(ticket[key]) for key in
                       ('dhanClientId', 'securityId', 'exchangeSegment', 'transactionType', 'productType'))
                or number(row.get('price'), 'Owned order price', True) != number(ticket['price'], 'Limit price', True)
                or received_quantity(row.get('quantity')) != ticket['quantity']):
            raise ValueError('The prior order cannot be verified against its approved ticket.')
        status = row.get('orderStatus')
        if status not in WORKING | TERMINAL:
            raise ValueError('Dhan returned an unrecognized order status.')
        filled = received_quantity(row.get('filledQty'))
        if not record.get('filled', 0) <= filled <= ticket['quantity']:
            raise ValueError('Dhan returned inconsistent cumulative fills.')
        if status == 'TRADED' and filled != ticket['quantity']:
            raise ValueError('Dhan full-fill status and quantity disagree.')
        record.update(status=status, filled=filled)
        _atomic_private_write(path, json.dumps(record))
        return status, filled

    def snapshot(self, client, plan):
        books = {name: client.request('GET', '/' + name) for name in ('orders', 'positions', 'holdings', 'forever/orders')}
        if any(not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
               for rows in books.values()):
            raise ValueError('Complete Dhan orders, positions and holdings are required.')
        for rows in books.values():
            if any(str(row.get('dhanClientId', client.client_id)) != client.client_id for row in rows):
                raise ValueError('Dhan returned data for a different account.')
        security = plan['security_id']
        matching_orders = [r for r in books['orders'] if str(r.get('securityId')) == security
                           and r.get('exchangeSegment') == 'NSE_EQ']
        if any(r.get('orderStatus') not in WORKING | TERMINAL | {'CLOSED'} for r in matching_orders):
            raise ValueError('Dhan order book contains an unrecognized status for this equity.')
        forever = [r for r in books['forever/orders'] if str(r.get('securityId')) == security
                   and r.get('exchangeSegment') == 'NSE_EQ' and r.get('transactionType') == 'BUY']
        working = (any(r.get('orderStatus') in WORKING for r in matching_orders)
                   or any(r.get('orderStatus') not in TERMINAL for r in forever))
        # Reject a matching security with an ambiguous holding identity.
        equity = plan['symbol'][4:-3]
        holdings = [r for r in books['holdings'] if str(r.get('securityId')) == security
                    or str(r.get('tradingSymbol', '')).removesuffix('-EQ') == equity]
        held = sum(received_quantity(r.get('totalQty')) for r in holdings)
        positions = [r for r in books['positions'] if str(r.get('securityId')) == security
                     and r.get('exchangeSegment') == 'NSE_EQ' and received_quantity(r.get('netQty'))]
        net = sum(received_quantity(r['netQty']) for r in positions)
        conflict = any(r.get('productType') != 'CNC' or received_quantity(r['netQty']) < 0 for r in positions)
        recent_sell = any(r.get('transactionType') == 'SELL' and received_quantity(r.get('filledQty', 0)) > 0
                          for r in matching_orders)
        return working, held, net, conflict or recent_sell

    @serialized_dhan_entry
    def check(self, plan, monitor_id, context, now, slot):
        with self.execution.lock, self.execution._submission_lock():
            context.checkpoint()
            self.verify_enabled()
            self.journal.mkdir(mode=0o700, exist_ok=True)
            rows = self.journal_rows()
            if any(rec.get('status') in ('SUBMITTING', 'UNKNOWN') for _, rec in rows):
                raise ValueError('An earlier Dhan send needs reconciliation before a new entry.')
            intents = self.folder / 'dhan-strategy-intents'
            for path in intents.glob('*.json'):
                if json.loads(path.read_text()).get('status') in ('SUBMITTING', 'UNKNOWN'):
                    raise ValueError('An earlier Dhan strategy send needs reconciliation.')
            contract = self.contract(plan['symbol'], now)
            price = number(plan['limit_price'], 'Authorized limit', True)
            if str(contract['security_id']) != plan['security_id'] or price % number(contract['tick_size'], 'NSE tick', True):
                raise ValueError('The broker contract or tick changed. Review a new plan.')
            client = self.execution._client()
            profile = client.request('GET', '/profile')
            if str(profile.get('dhanClientId')) != client.client_id:
                raise PermissionError('Dhan profile account mismatch.')
            fills, managed_working = 0, False
            for path, record in rows:
                if record.get('investment_monitor') != monitor_id:
                    continue
                status = record['status']
                filled = record.get('filled', 0)
                if status not in TERMINAL or not record.get('verified_terminal'):
                    status, filled = self.own_order(client, path, record)
                    if status in TERMINAL:
                        record['verified_terminal'] = True
                        _atomic_private_write(path, json.dumps(record))
                if status in {'REJECTED', 'CANCELLED'}:
                    raise ValueError('A monitored order was rejected or cancelled. Review before re-enabling.')
                managed_working |= status in WORKING
                fills += filled
            working, held, net, conflict = self.snapshot(client, plan)
            if conflict:
                raise ValueError('Conflicting equity activity detected. Review this position in Dhan.')
            if working or managed_working:
                return 'WORKING_ORDER', fills
            confirmed_exposure = max(held, net)
            if not fills and confirmed_exposure > 0:
                return 'EXISTING_POSITION', fills
            if fills == plan['quantity'] and confirmed_exposure >= fills:
                return 'COMPLETE', fills
            if fills > plan['quantity'] or confirmed_exposure > fills:
                raise ValueError('Exposure exceeds the monitored fills. Review before any further entry.')
            if confirmed_exposure < fills:
                return 'AWAITING_POSITION', fills
            quantity = plan['quantity'] - fills
            if quantity <= 0:
                return 'AWAITING_POSITION', fills
            self.send(client, context, plan, monitor_id, quantity, slot, confirmed_exposure)
            return 'BROKER_ACKNOWLEDGED', fills

    def send(self, client, context, plan, monitor_id, quantity, slot, exposure):
        ips = client.request('GET', '/ip/getIP')
        if self.execution.egress() not in (ips.get('primaryIP'), ips.get('secondaryIP')):
            raise PermissionError('The server IP is not whitelisted for the selected Dhan account.')
        ticket = dict(dhanClientId=client.client_id, transactionType='BUY', exchangeSegment='NSE_EQ',
                      productType='CNC', orderType='LIMIT', validity='DAY', securityId=plan['security_id'],
                      quantity=quantity, price=float(plan['limit_price']), triggerPrice=0,
                      disclosedQuantity=0, afterMarketOrder=slot == 'AMO')
        if ticket['afterMarketOrder']:
            ticket['amoTime'] = 'OPEN'
        funds = client.request('GET', '/fundlimit')
        if str(funds.get('dhanClientId')) != client.client_id:
            raise PermissionError('Dhan funds account mismatch.')
        margin = client.request('POST', '/margincalculator', {
            key: ticket[key] for key in ('dhanClientId', 'exchangeSegment', 'transactionType',
                                        'quantity', 'productType', 'securityId', 'price', 'triggerPrice')})
        cash = number(funds.get('availabelBalance', funds.get('availableBalance')), 'Dhan funds')
        cash = min(cash, number(margin.get('availableBalance', cash), 'Margin available balance'))
        required = max(number(margin.get('totalMargin'), 'Dhan margin', True),
                       number(plan['limit_price'], 'Authorized limit', True) * quantity)
        if cash < required:
            raise ValueError('Available funds do not cover the delivery order.')
        working, held, net, conflict = self.snapshot(client, plan)
        if working or conflict or max(held, net) != exposure:
            raise ValueError('Orders or exposure changed during preflight.')
        with context.store.guard:
            self.verify_enabled()
            if session_slot(datetime.now(IST)) != slot:
                raise ValueError('The scheduled submission window ended during broker validation.')
            context.checkpoint()
            correlation = 'INV-' + secrets.token_hex(10)
            ticket['correlationId'] = correlation
            path = self.journal / (correlation + '.json')
            record = {'ticket': ticket, 'status': 'SUBMITTING', 'endpoint': '/orders',
                      'investment_monitor': monitor_id, 'filled': 0}
            mark_dhan_entry_attempt(self.execution)
            _atomic_private_write(path, json.dumps(record))
        try:
            response = client.request('POST', '/orders', ticket)
            if not isinstance(response, dict) or not response.get('orderId'):
                raise RuntimeError('Dhan did not return an order ID.')
        except Exception as error:
            rejected = isinstance(error, DhanAPIError) and error.definitive_rejection
            record['status'] = 'REJECTED' if rejected else 'UNKNOWN'
            _atomic_private_write(path, json.dumps(record))
            raise ValueError('Dhan rejected the order.' if rejected else
                             'Dhan submission outcome is uncertain. Reconcile the correlation ID before another order.') from None
        record.update(order_id=response['orderId'], status=response.get('orderStatus') or 'PENDING')
        _atomic_private_write(path, json.dumps(record))

    @contextmanager
    def symbol_lock(self, plan):
        from .file_lock import lock_file, unlock_file
        identity = str(int(plan['security_id']))
        fd = os.open(self.folder / ('investment-entry-' + identity + '.lock'),
                     os.O_RDWR | os.O_CREAT, 0o600)
        acquired = False
        try:
            try:
                lock_file(fd, blocking=False)
                acquired = True
            except OSError:
                raise ValueError('Another monitor owns this Dhan account and equity.') from None
            yield
        finally:
            if acquired:
                unlock_file(fd)
            os.close(fd)

    def run(self, context, plan, monitor_id):
        with self.symbol_lock(plan):
            return self.monitor(context, plan, monitor_id)

    def monitor(self, context, plan, monitor_id):
        state = {'status': 'MONITORING', 'plan': plan, 'filled': 0, 'monitor_id': monitor_id}
        last_slot = None
        while True:
            now = datetime.now(IST)
            if now.year != 2026:
                raise ValueError('The NSE session calendar needs to be updated before the next check.')
            slot = session_slot(now)
            key = (now.date(), slot)
            if slot and key != last_slot:
                last_slot = key
                state.update(last_checked=now.isoformat(), last_slot=slot)
                context.checkpoint('Checking Dhan order book and exposure.', state)
                try:
                    status, filled = self.check(plan, monitor_id, context, now, slot)
                except (JobCancelled, JobInterrupted):
                    raise
                except Exception as error:
                    reason = str(error) if isinstance(error, (ValueError, PermissionError)) else 'Broker verification did not complete.'
                    state.update(status='NEEDS_REVIEW', reason=reason)
                    context.checkpoint('Entry monitor needs review.', state)
                    raise
                state.update(status=status, filled=filled)
                if status in {'COMPLETE', 'EXISTING_POSITION'}:
                    return state
            context.checkpoint('Monitoring at market open and after close.', state)
            if context.store.shutdown.wait(15):
                raise JobInterrupted()

