"""Optional directional structure gate from confirmed actual host pivots."""
from .zone_target import validate

REVISION = 'confirmed-host-structure-v1'


def settings(payload):
    enabled = payload.get('market_structure_enabled', False)
    if not isinstance(enabled, bool):
        raise ValueError('Market structure enabled must be a boolean.')
    return {'market_structure_enabled': enabled}


def check(rows, direction, seconds, event_at):
    validate(rows)
    closed = [r for r in rows if not r.get('is_forming') and r['timestamp']+seconds <= event_at]
    highs, lows = [], []
    for i in range(2, len(closed)-2):
        c = closed[i]
        n = closed[i-2:i]+closed[i+1:i+3]
        point = dict(price=c['high'], origin_at=c['timestamp'], confirmed_at=closed[i+2]['timestamp']+seconds)
        if all(c['high'] > x['high'] for x in n):
            highs.append(point)
        if all(c['low'] < x['low'] for x in n):
            lows.append({**point, 'price': c['low']})
    h, l = highs[-2:], lows[-2:]
    state = 'INSUFFICIENT_CONFIRMED_SWINGS'
    if len(h) == len(l) == 2:
        hh, hl = h[1]['price'] > h[0]['price'], l[1]['price'] > l[0]['price']
        lh, ll = h[1]['price'] < h[0]['price'], l[1]['price'] < l[0]['price']
        state = 'BULLISH_HH_HL' if hh and hl else 'BEARISH_LH_LL' if lh and ll else 'EXPANDING_HH_LL' if hh and ll else 'CONTRACTING_LH_HL' if lh and hl else 'RANGE_OR_EQUAL_SWINGS'
    allowed = (direction == 'BULLISH' and state == 'BULLISH_HH_HL') or (direction == 'BEARISH' and state == 'BEARISH_LH_LL')
    return dict(revision=REVISION, state=state, allowed=allowed, direction=direction, source_seconds=seconds,
                pivot_left=2, pivot_right=2, highs=h, lows=l, assessed_at=event_at,
                reason=('Confirmed directional structure passes.' if allowed else 'Entry blocked: '+state+'; long requires HH + HL, short requires LH + LL.'))
