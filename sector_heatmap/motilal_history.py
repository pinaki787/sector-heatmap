"""Reusable captured MO candles. Gaps are retained and never fabricated."""
from contextlib import contextmanager
import math
from pathlib import Path
import sqlite3
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo


class History:
    def __init__(self,path,clock=time.time):
        self.path=Path(path);self.clock=clock;self.lock=threading.RLock();self.forming={}
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS candles(symbol TEXT, timestamp INTEGER, open REAL, high REAL, low REAL, close REAL, observations INTEGER, open_verified INTEGER, PRIMARY KEY(symbol,timestamp))')
            columns={r[1] for r in db.execute('PRAGMA table_info(candles)')}
            if 'volume' not in columns:db.execute('ALTER TABLE candles ADD COLUMN volume REAL')
            if 'volume_verified' not in columns:db.execute('ALTER TABLE candles ADD COLUMN volume_verified INTEGER DEFAULT 0')
            db.execute("""CREATE TABLE IF NOT EXISTS daily_snapshots (
                symbol TEXT NOT NULL, timestamp INTEGER NOT NULL,
                open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
                volume REAL, PRIMARY KEY(symbol, timestamp)
            )""")
        self.path.chmod(0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=1)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            with db:yield db
        finally:db.close()
    def invalidate(self):
        with self.lock:
            for bar in self.forming.values():bar['open_verified']=False
    def _persist(self, symbol, bar):
        if bar.get('persisted'):
            return
        with self.db() as db:
            db.execute(
                '''INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(symbol,timestamp) DO UPDATE SET
                       open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
                       observations=excluded.observations,open_verified=excluded.open_verified,
                       volume=excluded.volume,volume_verified=excluded.volume_verified
                   WHERE candles.open_verified=0 AND excluded.open_verified=1''',
                (symbol, bar['timestamp'], bar['open'], bar['high'], bar['low'], bar['close'],
                 bar['observations'], int(bar['open_verified']), bar.get('volume'),
                 int(bar.get('volume_verified', False))),
            )
        bar['persisted'] = True

    def _flush_elapsed(self, symbol):
        with self.lock:
            bar = self.forming.get(symbol)
            # Leave time for the same late ticks accepted by ingest().
            if bar and bar['open_verified'] and self.clock() >= bar['timestamp'] + 75:
                self._persist(symbol, bar)

    def ingest(self,tick,coverage_since):
        symbol=tick['symbol'];stamp=float(tick['exch_feed_time']);price=float(tick['ltp'])
        if not math.isfinite(price) or price<=0 or not 0<=self.clock()-stamp<=15:return
        opening=int(stamp)//60*60
        with self.lock:
            previous=self.forming.get(symbol)
            if previous and opening<previous['timestamp']:return
            baseline=previous.get('cumulative_volume') if previous else None
            if previous and opening>previous['timestamp']:
                self._persist(symbol, previous)
                if opening!=previous['timestamp']+60:baseline=None
                previous=None
            if not previous:
                cumulative=tick.get('cumulative_volume')
                if cumulative is not None and baseline is not None and cumulative<baseline:baseline=None
                previous=dict(timestamp=opening,open=price,high=price,low=price,close=price,observations=0,open_verified=coverage_since<=opening,volume_baseline=baseline,volume_verified=bool(tick.get('is_index')) or baseline is not None,volume=0 if tick.get('is_index') else None)
                self.forming[symbol]=previous
            cumulative=tick.get('cumulative_volume');baseline=previous.get('volume_baseline')
            if cumulative is not None:
                previous['cumulative_volume']=cumulative
                if baseline is not None and cumulative>=baseline:previous['volume']=cumulative-baseline
                elif baseline is not None:previous['volume_verified']=False
            previous.update(high=max(previous['high'],price),low=min(previous['low'],price),close=price,observations=previous['observations']+1)
            if coverage_since>opening:previous['open_verified']=False
    def candles(self,symbol,minutes=1,limit=500,session_open=None,*,session_minutes=None, session_bounds=None, before=None):
        if isinstance(minutes,bool) or not isinstance(minutes,int) or not 1<=minutes<=1440:raise ValueError('Invalid candle interval.')
        self._flush_elapsed(symbol)
        with self.db() as db:
            # MCX calendar candles need complete sessions across the requested
            # history window, even when it contains more than 100,000 minutes.
            row_limit = limit * minutes if limit >= 750 else min(limit * minutes, 100000)
            cutoff = self.clock() - 60
            if before is not None:
                cutoff = min(cutoff, before - 1)
            rows = db.execute(
                'SELECT timestamp,open,high,low,close,observations,open_verified,volume,volume_verified '
                'FROM candles WHERE symbol=? AND timestamp<=? ORDER BY timestamp DESC LIMIT ?',
                (symbol, cutoff, row_limit),
            ).fetchall()[::-1]
        if session_minutes is not None and (not isinstance(session_minutes, int) or not 1 <= session_minutes <= 1440):
            raise ValueError('Invalid session length.')
        groups={}
        ends={}
        now=self.clock()
        for row in rows:
            if not row[6]:continue
            stamp=datetime.fromtimestamp(row[0],ZoneInfo('Asia/Kolkata'))
            bounds = session_bounds(row[0]) if session_bounds else None
            if bounds and bounds[0] == bounds[1]:
                continue
            hour,minute=divmod(bounds[0],60) if bounds else map(int,(session_open or '00:00').split(':'))
            anchor=int(stamp.replace(hour=hour,minute=minute,second=0,microsecond=0).timestamp())
            length = bounds[1] - bounds[0] if bounds else session_minutes
            session_end = anchor + length * 60 if length is not None else None
            if row[0] < anchor or (session_end is not None and row[0] >= session_end):
                continue
            opening=anchor+(row[0]-anchor)//(minutes*60)*(minutes*60)
            end = opening + minutes * 60
            ends[opening] = min(end, session_end) if session_end is not None else end
            groups.setdefault(opening,[]).append(row)
        result=[]
        for opening,parts in sorted(groups.items()):
            end = ends[opening]
            if end > now or [r[0] for r in parts] != list(range(opening, end, 60)):
                continue
            volume_ok=all(r[8] and r[7] is not None for r in parts)
            result.append(dict(timestamp=opening,open=parts[0][1],high=max(r[2] for r in parts),low=min(r[3] for r in parts),close=parts[-1][4],volume=sum(r[7] for r in parts) if volume_ok else None,volume_available=volume_ok,source='MOTILAL_CAPTURED_TICKS',open_verified=True))
        return result[-limit:]

    def save_daily_snapshot(self, symbol, row):
        """Store a confirmed broker session in the daily archive."""
        with self.db() as db:
            db.execute("""
                INSERT INTO daily_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timestamp) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume
                WHERE daily_snapshots.open IS NOT excluded.open
                   OR daily_snapshots.high IS NOT excluded.high
                   OR daily_snapshots.low IS NOT excluded.low
                   OR daily_snapshots.close IS NOT excluded.close
                   OR daily_snapshots.volume IS NOT excluded.volume
            """, (symbol, *row))

    def daily_snapshots(self, symbol):
        with self.db() as db:
            return db.execute("""
                SELECT timestamp, open, high, low, close, volume FROM daily_snapshots
                WHERE symbol=? ORDER BY timestamp
            """, (symbol,)).fetchall()

    def session_candles(self,symbol,session_open='09:15',minutes=375,limit=3000):
        """Aggregate complete native sessions without truncating older minutes.

        SQL aggregates the indexed symbol history rather than loading a bounded
        minute tail into Python. Every minute must have verified opening coverage.
        """
        if isinstance(minutes,bool) or not isinstance(minutes,int) or not 1<=minutes<=1440:
            raise ValueError('Invalid session interval.')
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=3000:
            raise ValueError('Invalid session history limit.')
        try:
            hour,minute=map(int,session_open.split(':'))
            if not 0<=hour<24 or not 0<=minute<60:raise ValueError()
        except (ValueError,AttributeError):raise ValueError('Invalid session opening.') from None
        shift=19800-(hour*60+minute)*60
        self._flush_elapsed(symbol)
        with self.db() as db:
            rows=db.execute("""
                WITH aligned AS (
                    SELECT *,CAST((timestamp+?)/86400 AS INTEGER)*86400-? AS anchor
                    FROM candles WHERE symbol=? AND timestamp+60<=?
                ), sessions AS (
                    SELECT anchor,MAX(high) AS high,MIN(low) AS low,
                           SUM(volume) AS volume,
                           MIN(CASE WHEN volume_verified=1 AND volume IS NOT NULL THEN 1 ELSE 0 END) AS volume_ok
                    FROM aligned WHERE timestamp>=anchor AND timestamp<anchor+?
                    GROUP BY anchor
                    HAVING COUNT(*)=? AND MIN(open_verified)=1
                       AND MIN(timestamp)=anchor AND MAX(timestamp)=anchor+?-60
                       AND anchor+?<=?
                )
                SELECT s.anchor,o.open,s.high,s.low,c.close,s.volume,s.volume_ok
                FROM sessions s
                JOIN candles o ON o.symbol=? AND o.timestamp=s.anchor
                JOIN candles c ON c.symbol=? AND c.timestamp=s.anchor+?-60
                ORDER BY s.anchor DESC LIMIT ?
            """,(shift,shift,symbol,self.clock(),minutes*60,minutes,minutes*60,minutes*60,self.clock(),symbol,symbol,minutes*60,limit)).fetchall()
        return [dict(timestamp=r[0],open=r[1],high=r[2],low=r[3],close=r[4],
                     volume=r[5] if r[6] else None,volume_available=bool(r[6]),
                     source='MOTILAL_CAPTURED_TICKS',open_verified=True) for r in reversed(rows)]
