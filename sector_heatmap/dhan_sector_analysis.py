"""Read-only sector analysis using one owned Dhan account's Data API."""
from .persistent_jobs import checkpoint
from datetime import datetime, timedelta
import logging
import math
import re
import time

from .sector_service import CandleHistoryProvider, SectorAnalysisService
from .sectors import BENCHMARK_SYMBOL, SECTOR_DEFINITIONS, equity_symbol

LOGGER = logging.getLogger(__name__)

# Match names in the current master rather than assume security IDs are permanent.
INDEX_NAMES = {
    BENCHMARK_SYMBOL: ('NIFTY', 'NIFTY 50', 'NIFTY50'),
    'NSE:NIFTYBANK-INDEX': ('BANKNIFTY', 'NIFTY BANK'),
    'NSE:FINNIFTY-INDEX': ('FINNIFTY', 'NIFTY FIN SERVICE', 'NIFTY FINANCIAL SERVICES'),
    'NSE:NIFTYIT-INDEX': ('NIFTY IT',),
    'NSE:NIFTYAUTO-INDEX': ('NIFTY AUTO',),
    'NSE:NIFTYPHARMA-INDEX': ('NIFTY PHARMA',),
    'NSE:NIFTYHEALTHCARE-INDEX': ('NIFTY HEALTHCARE', 'NIFTY HEALTHCARE INDEX'),
    'NSE:NIFTYFMCG-INDEX': ('NIFTY FMCG',),
    'NSE:NIFTYMETAL-INDEX': ('NIFTY METAL',),
    'NSE:NIFTYREALTY-INDEX': ('NIFTY REALTY',),
    'NSE:NIFTYENERGY-INDEX': ('NIFTY ENERGY',),
    'NSE:NIFTYOILANDGAS-INDEX': ('NIFTY OIL AND GAS', 'NIFTY OIL & GAS'),
    'NSE:NIFTYPSUBANK-INDEX': ('NIFTY PSU BANK',),
    'NSE:NIFTYCONSRDURBL-INDEX': ('NIFTY CONSR DURBL', 'NIFTY CONSUMER DURABLES'),
    'NSE:NIFTYMEDIA-INDEX': ('NIFTY MEDIA',),
}


def normalized(value):
    return re.sub(r'[^A-Z0-9]', '', str(value).upper())


class DhanCandleHistoryProvider(CandleHistoryProvider):
    broker = 'DHAN'

    def __init__(self, execution, now=None):
        super().__init__(None, now=now)
        self.execution = execution
        self.rows = []

    def prepare(self):
        client = self.execution._client()
        profile = client.request('GET', '/profile')
        if str(profile.get('dhanClientId')) != str(client.client_id):
            raise PermissionError('Dhan token does not belong to the selected broker account.')
        if str(profile.get('dataPlan', '')).lower() != 'active':
            raise ValueError('Dhan Data API subscription must be active for sector analysis.')
        if self.client is not client:
            with self.lock:
                self.cache.clear()
        self.client = client
        self.rows = self.execution.master.load(self.now())
        self.resolve(BENCHMARK_SYMBOL)

    def resolve(self, symbol):
        if symbol in INDEX_NAMES:
            names = {normalized(name) for name in INDEX_NAMES[symbol]}
            matches = [row for row in self.rows
                       if row.get('SEM_EXM_EXCH_ID') == 'NSE' and row.get('SEM_SEGMENT') == 'I'
                       and any(normalized(row.get(key, '')) in names
                               for key in ('SEM_TRADING_SYMBOL', 'SEM_CUSTOM_SYMBOL'))]
            segment = 'IDX_I'
        elif symbol.startswith('NSE:') and symbol.endswith('-EQ'):
            ticker = symbol[4:-3]
            matches = [row for row in self.rows
                       if row.get('SEM_EXM_EXCH_ID') == 'NSE' and row.get('SEM_SEGMENT') == 'E'
                       and row.get('SEM_SERIES') == 'EQ' and row.get('SEM_TRADING_SYMBOL') == ticker]
            segment = 'NSE_EQ'
        else:
            raise ValueError('Unsupported Dhan sector symbol: ' + symbol)
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous Dhan security master mapping for ' + symbol)
        row = matches[0]
        return dict(securityId=str(row['SEM_SMST_SECURITY_ID']), exchangeSegment=segment,
                    instrument='INDEX' if segment == 'IDX_I' else 'EQUITY')

    def _request(self, path, payload):
        with self.request_lock:
            time.sleep(max(0, .35 - (time.monotonic() - self.last_request)))
            try:
                return self.client.request('POST', path, payload)
            finally:
                self.last_request = time.monotonic()

    @staticmethod
    def parse(raw):
        fields = ('timestamp', 'open', 'high', 'low', 'close', 'volume')
        if not isinstance(raw, dict) or any(not isinstance(raw.get(k), list) for k in fields):
            raise ValueError('Dhan returned incomplete sector OHLCV arrays.')
        if len({len(raw[k]) for k in fields}) != 1:
            raise ValueError('Dhan returned unequal sector OHLCV arrays.')
        rows = {}
        for values in zip(*(raw[k] for k in fields)):
            if any(isinstance(v, bool) for v in values):
                raise ValueError('Invalid Dhan sector candle.')
            bar = {key: float(value) for key, value in zip(fields, values)}
            if (not all(math.isfinite(v) for v in bar.values())
                    or min(bar[k] for k in fields[:-1]) <= 0 or bar['volume'] < 0
                    or bar['timestamp'] != int(bar['timestamp'])
                    or bar['high'] < max(bar['open'], bar['close'], bar['low'])
                    or bar['low'] > min(bar['open'], bar['close'])):
                raise ValueError('Invalid Dhan sector candle.')
            bar['timestamp'] = int(bar['timestamp'])
            if bar['timestamp'] in rows:
                raise ValueError('Duplicate Dhan sector candle timestamp.')
            rows[bar['timestamp']] = bar
        return [rows[key] for key in sorted(rows)]

    def _download(self, symbol, resolution, lookback_days):
        meta = self.resolve(symbol)
        end = self.now().date() + timedelta(days=1)
        cursor = self.now().date() - timedelta(days=lookback_days)
        rows = {}
        daily = resolution == 'D'
        while cursor < end:
            checkpoint("Collecting "+symbol+" Dhan history chunk.")
            chunk_end = min(end, cursor + timedelta(days=365 if daily else 89))
            payload = dict(meta, oi=False, fromDate=cursor.isoformat(), toDate=chunk_end.isoformat())
            if daily:
                payload['expiryCode'] = 0
            else:
                payload.update(interval=resolution, fromDate=cursor.isoformat()+' 00:00:00',
                               toDate=chunk_end.isoformat()+' 00:00:00')
            raw = self._request('/charts/historical' if daily else '/charts/intraday', payload)
            for bar in self.parse(raw):
                # Reject out-of-range provider rows rather than contaminating a timeframe.
                if cursor <= datetime.fromtimestamp(bar['timestamp'], self.now().tzinfo).date() < chunk_end:
                    rows[bar['timestamp']] = bar
            cursor = chunk_end
        current = self.now().timestamp()
        return self._completed_only([rows[k] for k in sorted(rows) if k <= current], resolution)

    def constituent_moves(self):
        symbols = {item.ticker for sector in SECTOR_DEFINITIONS for item in sector.constituents}
        mapped = {}
        for ticker in symbols:
            try:
                mapped[ticker] = self.resolve(equity_symbol(ticker))['securityId']
            except ValueError:
                continue
        if not mapped:
            return {}
        raw = self._request('/marketfeed/ohlc', {'NSE_EQ': sorted({int(v) for v in mapped.values()})})
        quotes = raw.get('data', {}).get('NSE_EQ', {})
        moves = {}
        for ticker, security in mapped.items():
            quote = quotes.get(security, {})
            try:
                price = float(quote['last_price'])
                previous = float(quote['ohlc']['close'])
                if all(math.isfinite(v) and v > 0 for v in (price, previous)):
                    moves[ticker] = (price - previous) / previous * 100
            except (KeyError, TypeError, ValueError):
                continue
        return moves


class DhanSectorAnalysisService(SectorAnalysisService):
    def __init__(self, execution, provider=None, now=None):
        self.execution = execution
        provider = provider or DhanCandleHistoryProvider(execution, now=now)
        super().__init__('', state_file=execution.folder/'dhan-sector-analysis-history.json', provider=provider, now=now)
        for snapshot in self.snapshots.values():
            snapshot['refresh_state']['message'] = 'Connecting to Dhan history'

    def refresh(self):
        self.provider.prepare()
        super().refresh()
        error = None
        try:
            moves = self.provider.constituent_moves()
        except Exception as exc:
            LOGGER.warning('Dhan sector constituent quotes unavailable: %s', exc)
            moves, error = {}, str(exc)
        with self.lock:
            for snapshot in self.snapshots.values():
                snapshot['constituent_quote_error'] = error
                snapshot['constituent_quotes_updated_at'] = None if error else self.now().isoformat()
                for sector in snapshot['sectors']:
                    drivers = []
                    for item in sector['constituents']:
                        change = moves.get(item['ticker'])
                        drivers.append(dict(item, change=change, provider='DHAN',
                                            contribution=item['weight']*change/100 if change is not None else None))
                    drivers.sort(key=lambda item: abs(item['contribution']) if item['contribution'] is not None else -1, reverse=True)
                    sector['constituent_movers'] = drivers
                    sector['top_contributors'] = [d for d in drivers if d['contribution'] is not None][:3]
                    sector['attribution']['available_constituents'] = sum(d['change'] is not None for d in drivers)
                    sector['attribution']['available_weight_pct'] = round(sum(d['weight'] for d in drivers if d['change'] is not None), 2)

    def snapshot(self, mode='intraday', sector_id=None):
        # Credential removal/disconnection must also block previously cached reads.
        self.execution._client()
        result = super().snapshot(mode, sector_id)
        result.update(broker='DHAN', provider='DHAN', account_id=self.execution.account['id'],
                      source='Dhan Data API; completed candles')
        return result
