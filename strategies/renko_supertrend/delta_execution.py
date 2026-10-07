"""Internal Delta execution boundary; deliberately not registered as an HTTP action.

The Renko runner must authorize each intent before invoking this boundary. Existing
Delta durable intents, native validation and unknown-ack recovery remain in use.
"""
from copy import deepcopy
from .delta_contracts import owned_order, order_intent, position


class Execution:
    def __init__(self, delta):
        self.delta = delta
        self.account_identity = None

    def authenticate(self):
        self.delta.verify_auth()
        identity = self.delta._identity()
        if self.account_identity and self.account_identity != identity:
            raise ValueError('Delta account changed; saved exposure requires reconciliation.')
        self.account_identity = identity
        return identity

    def active_orders(self):
        """Read the complete broker book, including orders placed outside this app."""
        rows, cursor, seen = [], None, set()
        for _ in range(100):
            params = dict(page_size=100)
            if cursor:
                params['after'] = cursor
            response = self.delta._private('GET', '/v2/orders', params=params)
            batch = response.get('result')
            if not isinstance(batch, list):
                raise ValueError('Delta active order book unavailable.')
            for row in batch:
                if not isinstance(row, dict) or not row.get('id') or row['id'] in seen:
                    raise ValueError('Ambiguous Delta active-order pagination.')
                seen.add(row['id']); rows.append(deepcopy(row))
            next_cursor = (response.get('meta') or {}).get('after')
            if not next_cursor:
                return rows
            if next_cursor == cursor:
                raise ValueError('Delta order pagination did not advance.')
            cursor = next_cursor
        raise ValueError('Delta order inventory incomplete; ownership cannot be verified.')

    def positions(self):
        account = self.delta.account({'refresh': True})
        result = []
        for row in account['positions']:
            product = self.delta.product(row['product_symbol'])
            result.append(position(row, product, self.delta.clock()))
        return result

    def reconcile(self, request_id):
        self.authenticate()
        owned = self.delta.reconcile({'request_id': request_id})
        if owned.get('strategy') != 'RENKO_SUPERTREND_V1':
            raise ValueError('Order is not owned by the Renko strategy.')
        return owned_order(owned, self.account_identity)

    def submit(self, symbol, size, side, quote, token, signal_symbol, reason):
        """Only a server-owned runner may invoke this; no client runner flag exists."""
        self.authenticate()
        with self.delta.lock:
            if self.delta.runner.get('running') or self.delta.runner.get('pending') or self.delta.live.get('runner_position'):
                raise ValueError('Existing Delta strategy ownership blocks a separate Renko order.')
            product = self.delta.product(symbol)
            payload = order_intent(symbol, size, side, quote, product, self.delta.clock())
            # Stable identity is the shared runner's persisted tag. Delta.submit
            # separately persists native intent before touching the exchange.
            payload.pop('product_id')
            payload.update(request_id=token, signal_symbol=signal_symbol, execution_reason=reason)
            if side == 1:
                if self.delta._position(product['id']) != 0:
                    raise ValueError('Existing broker position blocks a new Renko entry.')
                if any(row.get('product_id') == product['id'] for row in self.active_orders()):
                    raise ValueError('External active order blocks Renko ownership.')
            # Native submit enforces account, gate, signed position, whole size,
            # tick, wallet and durable idempotence. It does not start the RSI runner.
            return self.delta.submit(payload, runner=True)

    def cancel(self, request_id):
        self.authenticate()
        owned = self.delta._owned({'request_id': request_id})
        if owned.get('strategy') != 'RENKO_SUPERTREND_V1':
            raise ValueError('Cannot cancel another strategy or external order.')
        return self.delta.cancel({'mode': 'LIVE', 'request_id': request_id})
