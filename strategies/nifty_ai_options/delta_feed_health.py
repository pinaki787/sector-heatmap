"""Bounded subscription repair; no fabricated trades, prices or order actions."""
class FeedHealth:
    def __init__(self):
        self.attempts=0
        self.next_retry=0
    def reset(self):
        self.attempts=0
        self.next_retry=0
    def check(self, broker, symbol, now, automatic=False):
        health=broker.source_health(symbol)
        if not health.get('connected') and automatic:
            return dict(state='RECONNECTING',attempts=self.attempts,entries_blocked=True,automatic_recovery=True)
        if not health.get('connected'):
            raise ValueError('Delta transport disconnected; history reconciliation required; exposure preserved')
        if health.get('heartbeat_fresh') and health.get('quote_fresh'):
            return dict(state='WAITING_FOR_TRADED_PRICE',attempts=self.attempts,
                        entries_blocked=True,transport='HEALTHY')
        if now < self.next_retry:
            return dict(state='RECOVERING_SUBSCRIPTION',attempts=self.attempts,entries_blocked=True)
        if self.attempts>=3 and not automatic:
            raise ValueError('Delta source recovery exhausted: heartbeat or executable quote stale; exposure preserved')
        broker.subscribe_all()
        self.attempts+=1
        self.next_retry=now+min(60,10*max(1,self.attempts//3))
        return dict(state='RECOVERING_SUBSCRIPTION',attempts=self.attempts,entries_blocked=True)
