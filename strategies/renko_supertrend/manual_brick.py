"""Read-only reference ATR sizing; independent of display/runner timeframe."""
import math
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def rule(symbol, session=None, *, atr_length):
    try:
        length = int(atr_length)
        if isinstance(atr_length, bool) or float(atr_length) != length or not 1 <= length <= 100:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ValueError("ATR length must be an integer from 1 to 100.") from None
    exchange = symbol.split(":")[0]
    if exchange in ("NSE", "BSE", "MCX"):
        bounds = (session or {}).get("master_regular_session", "")
        try:
            opening, closing = bounds.split("-")
            start = int(opening[:2])*60+int(opening[2:])
            end = int(closing[:2])*60+int(closing[2:])
        except (ValueError, TypeError):
            raise ValueError("Verified broker session bounds are required.")
        if not 0 <= start < end <= 1440:
            raise ValueError("Invalid broker session bounds.")
        duration = (end-start)*60
        return dict(reference_seconds=duration, atr_length=length,
                    divisor=duration/1800, anchor_zone="Asia/Kolkata",
                    anchor_minutes=start)
    if (session or {}).get("session_exchange") == "CRYPTO":
        return dict(reference_seconds=82800, atr_length=length, divisor=82800 / 1800,
                    anchor_zone="UTC", anchor_minutes=0)
    raise ValueError("Instrument exchange is not supported for reference brick sizing.")

def calculate(rows, specification, source_seconds, now):
    """Aggregate only fully covered completed reference bars, then Wilder ATR.

    Indian reference windows start at the session opening each date. Crypto
    windows are consecutive 23-hour periods anchored at the Unix epoch.
    No missing source bars are synthesized.
    """
    length = specification["atr_length"]
    span = specification["reference_seconds"]
    groups = {}
    for row in rows:
        stamp = int(row["timestamp"])
        if row.get("is_forming") or stamp+source_seconds > now:
            continue
        if specification["anchor_zone"] == "UTC":
            opening = stamp//span*span
        else:
            dt = datetime.fromtimestamp(stamp, IST)
            midnight = int(dt.replace(hour=0,minute=0,second=0,microsecond=0).timestamp())
            opening = midnight+specification["anchor_minutes"]*60
            if not opening <= stamp < opening+span:
                continue
        # Ignore unfinished reference windows before validating their source.
        # They cannot contribute to the completed-reference ATR.
        if opening+span > now:
            continue
        values = [float(row[k]) for k in ("open","high","low","close")]
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError("Invalid source OHLC.")
        if values[1] < max(values[0],values[2],values[3]) or values[2] > min(values[0],values[1],values[3]):
            raise ValueError("Inconsistent source OHLC.")
        source=groups.setdefault(opening,{})
        if stamp in source and source[stamp]!=values:
            raise ValueError("Conflicting source OHLC revisions.")
        source[stamp]=values
    bars = []
    for opening, source in sorted(groups.items()):
        if opening+span > now:
            continue
        expected = list(range(opening, opening+span, source_seconds))
        if sorted(source) != expected:
            continue
        ordered = [source[t] for t in expected]
        bars.append(dict(timestamp=opening,open=ordered[0][0],
                         high=max(v[1] for v in ordered),
                         low=min(v[2] for v in ordered),close=ordered[-1][3]))
    return reference_result(bars,specification,now)


def reference_result(bars,specification,now):
    length=specification['atr_length']
    if len(bars) < length+1:
        raise ValueError("Insufficient fully covered reference bars for ATR warmup.")
    trs = [bars[0]["high"]-bars[0]["low"]] + [max(b["high"]-b["low"],abs(b["high"]-a["close"]),
               abs(b["low"]-a["close"])) for a,b in zip(bars,bars[1:])]
    atr = sum(trs[:length])/length
    for tr in trs[length:]:
        atr = (atr*(length-1)+tr)/length
    value = round(atr/specification["divisor"],2)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Reference ATR did not produce a positive brick size.")
    return dict(manual_brick=value,reference_atr=atr,reference_bars=len(bars),
                reference_last_at=bars[-1]["timestamp"],calculated_at=now,
                rule=specification,revision="broker-session-reference-atr-v2")


def calculate_sessions(rows,specification,now):
    """FYERS native daily OHLC, dated at UTC midnight; only closed sessions.

    Native session candles are used directly. Intraday bars are not repaired,
    synthesized or mixed with another broker. The verified contract session
    supplies the completion boundary and the thirty-minute divisor.
    """
    if specification.get('anchor_zone')!='Asia/Kolkata':raise ValueError('Native daily reference requires a verified Indian session.')
    bars={}
    for row in rows:
        stamp=float(row[0])
        if not math.isfinite(stamp) or stamp!=int(stamp) or int(stamp)%86400:raise ValueError('Native daily candle date is not verified.')
        day=datetime.fromtimestamp(stamp,IST).replace(hour=0,minute=0,second=0,microsecond=0)
        opening=int(day.timestamp())+specification['anchor_minutes']*60
        if opening+specification['reference_seconds']>now:continue
        values=[float(v) for v in row[1:5]]
        if len(values)!=4 or not all(math.isfinite(v) and v>0 for v in values):raise ValueError('Native daily reference OHLC is invalid.')
        if values[1]<max(values[0],values[2],values[3]) or values[2]>min(values[0],values[1],values[3]):raise ValueError('Native daily reference OHLC is inconsistent.')
        bar=dict(timestamp=opening,**dict(zip(('open','high','low','close'),values)))
        if opening in bars and bars[opening]!=bar:raise ValueError('Conflicting native daily reference candles.')
        bars[opening]=bar
    value=reference_result([bars[k] for k in sorted(bars)],specification,now)
    return dict(value,source_resolution='D',source_basis='Selected FYERS contract native daily OHLC; unfinished broker session excluded')
