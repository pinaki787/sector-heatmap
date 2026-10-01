"""Independent Python reference for the checked-in Red Bar Pine zone algorithm.
Read-only; verifies JS results on the same OHLC, not feed parity with TradingView.
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo


def reference(candles,symbol,tick):
    rows=[c for c in candles if not c.get('is_forming')]
    atr=[]; zones=[]; total=0; smooth=None
    local=[datetime.fromtimestamp(c['timestamp'],ZoneInfo('Asia/Kolkata')) for c in rows]
    opening=540 if symbol.startswith('MCX:') else 555
    closing=1410 if symbol.startswith('MCX:') else 930
    inside=[opening<=d.hour*60+d.minute<closing for d in local]
    for i,c in enumerate(rows):
        tr=c['high']-c['low'] if not i else max(c['high']-c['low'],abs(c['high']-rows[i-1]['close']),abs(c['low']-rows[i-1]['close']))
        total+=tr
        if i==13:smooth=total/14
        elif i>13:smooth=(13*smooth+tr)/14
        atr.append(smooth)
        for z in zones[:]:
            if (c['close']>z['high'] if z['supply'] else c['close']<z['low']) or i-z['born']>300:
                zones.remove(z);continue
            touching=c['high']>=z['low'] and c['low']<=z['high']
            if touching and not z['touching'] and i>z['born']:z['touches']+=1
            z['touching']=touching
            distance=z['low']-c['close'] if z['supply'] else c['close']-z['high']
            if not z['strong'] and z['touches']==0 and i-z['born']<=3 and distance>=.9*z['atr']:z['strong']=True
            z['right']=c['timestamp']
        if not inside[i] or i<22 or atr[i-9] is None:continue
        made=False
        for departure in range(1,4):
            for n in range(2,7):
                indices=list(range(i-departure-n+1,i-departure+1))
                base=[rows[k] for k in indices]
                compact=all(inside[k] and local[k].date()==local[i].date() for k in indices)
                compact=compact and all(a['high']>=b['low'] and a['low']<=b['high'] for a,b in zip(base,base[1:]))
                high=max(b['high'] for b in base);low=min(b['low'] for b in base);a=atr[i-departure]
                if not compact or not tick<high-low<=1.8*a or sum(abs(b['close']-b['open']) for b in base)>.6*sum(b['high']-b['low'] for b in base):continue
                down=c['close']<low-.35*a;up=c['close']>high+.35*a
                impulse_bars=rows[i-departure+1:i+1]
                valid=(down or up) and all(inside[k] and local[k].date()==local[i].date() for k in range(i-departure+1,i+1)) and all(b['close']<=high if down else b['close']>=low for b in impulse_bars)
                impulse=max((b['open']-b['close'] if down else b['close']-b['open']) for b in impulse_bars)
                distance=low-c['close'] if down else c['close']-high
                strong=distance>=.9*a and impulse>=.5*a
                top=high if down else max(max(b['open'],b['close']) for b in base)
                bottom=min(min(b['open'],b['close']) for b in base) if down else low
                side=[z for z in zones if z['supply']==down]
                duplicate=any(top>=z['low'] and bottom<=z['high'] for z in side)
                if valid and impulse>=.25*a and top-bottom>=tick and not duplicate:
                    if len(side)>=6:zones.remove(side[0])
                    zones.append(dict(supply=down,strong=strong,atr=a,born=i,detected=c['timestamp'],timestamp=base[0]['timestamp'],low=bottom,high=top,touches=0,touching=False,right=c['timestamp']))
                    made=True;break
            if made:break
    return zones

if __name__=='__main__':
    import sys
    d=json.load(open(sys.argv[1]));print(json.dumps(reference(d['candles'],d['symbol'],d['tick_size'])))
