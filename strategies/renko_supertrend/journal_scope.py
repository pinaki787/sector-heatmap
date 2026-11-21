"""Select journal evidence within one already authenticated workspace registry."""
import time


def journal_scope(instances, broker, instance='all', mode='ALL'):
    if mode not in ('ALL', 'PAPER', 'LIVE'):
        raise ValueError('Unknown journal mode.')
    candidates = [row for row in instances if row.get('broker') == broker]
    if instance != 'all':
        candidates = [row for row in candidates if row.get('instance_key', 'default') == instance]
        if not candidates:
            raise ValueError('Unknown journal instance for this broker.')
    trades = []
    for row in candidates:
        for trade in row.get('trade_history', []):
            if mode == 'ALL' or trade.get('mode') == mode:
                trades.append({**trade, 'broker': broker,
                               'instance_key': row.get('instance_key', 'default'),
                               'instance_instrument': row.get('instrument') or (row.get('config') or {}).get('underlying')})
    trades.sort(key=lambda trade: (trade.get('entry_time') or 0, trade.get('instance_key', ''), trade.get('trade_id', '')))
    return dict(schema_version=1, exported_at=time.time(), broker=broker,
                instance=instance, mode=mode, scope='Authenticated account workspace only; recorded runner trades across retained runs.',
                trades=trades)
