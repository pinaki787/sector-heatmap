"""Read-only polling and durable review queue. No broker execution capability.

A source adapter must return independently verified group identity, message IDs,
absolute timestamps and reply metadata. No consumer WhatsApp session scraping.
Without an installed adapter start fails closed; startup never resumes polling.
"""
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone


class WhatsAppPolling:
    def __init__(self, path, preview, reconcile, source=None, clock=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        os.chmod(path, 0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, signal TEXT, state TEXT, data TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS processed (id TEXT PRIMARY KEY)')
        self.db.execute('CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, data TEXT)')
        row = self.db.execute('SELECT data FROM config WHERE id=1').fetchone()
        self.config = json.loads(row[0]) if row else {'group': 'Trading With Mo 2.O', 'interval': 60, 'max_age': 300}
        self.preview, self.reconcile, self.source = preview, reconcile, source
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.last_poll = None
        self.error = None

    def status(self):
        with self.lock:
            rows = self.db.execute('SELECT id,state,data FROM messages ORDER BY rowid DESC LIMIT 100').fetchall()
            readiness = self.source.readiness() if self.source and hasattr(self.source, 'readiness') else {'ready': self.source is not None, 'blocker': None if self.source else 'No supported WhatsApp source adapter is installed.'}
            return {'running': bool(self.thread and self.thread.is_alive() and not self.stop_event.is_set()),
                    'source_ready': readiness['ready'], 'config': dict(self.config),
                    'last_poll': self.last_poll, 'error': self.error,
                    'blocker': readiness['blocker'],
                    'broker': 'FYERS (existing parser route)', 'automatic_orders': False,
                    'queue': [{'id': i, 'state': state, **json.loads(data)} for i, state, data in rows]}

    def configure(self, payload):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('Stop polling before changing configuration.')
            group = str(payload.get('group', '')).strip()
            interval = int(payload.get('interval', 60))
            if not group or len(group) > 150 or not 30 <= interval <= 3600:
                raise ValueError('Group is required; interval must be 30–3600 seconds.')
            self.config = {'group': group, 'interval': interval, 'max_age': 300}
            self.db.execute('INSERT OR REPLACE INTO config VALUES (1,?)', (json.dumps(self.config),))
            self.db.commit()
            return self.status()

    def start(self):
        with self.lock:
            if not self.status()['source_ready']:
                raise ValueError(self.status()['blocker'])
            if self.thread and self.thread.is_alive():
                return self.status()
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run, name='whatsapp-review-poll', daemon=True)
            self.thread.start()
            return self.status()

    def stop(self):
        self.stop_event.set()
        return self.status()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                messages = self.source.read_latest(self.config['group'])
                if len(messages) > 1:
                    raise RuntimeError('Source must return only the latest unread message; multiple messages were rejected.')
                for message in messages:
                    if self.stop_event.is_set():
                        break
                    if any(message.get(field) is not True for field in ('unread_verified', 'is_unread', 'is_latest_unread')):
                        raise RuntimeError('Source did not verify that this is the latest unread message. No message was processed.')
                    self.ingest(message)
                self.error = None
            except Exception as error:
                self.error = str(error)[:600] if isinstance(error, RuntimeError) else 'Source verification failed. No order was prepared or submitted.'
            self.last_poll = self.clock().isoformat()
            if self.stop_event.wait(self.config['interval']):
                break

    def _fresh(self, stamp):
        when = datetime.fromisoformat(stamp)
        if when.tzinfo is None:
            return False
        return 0 <= (self.clock() - when).total_seconds() <= self.config['max_age']

    def _verify(self, text):
        preview = self.preview({'text': text})
        parsed, mapping = preview['parsed'], preview['mapping']
        if mapping.get('status') != 'EXACT' or not mapping.get('contract'):
            raise ValueError('Ambiguous or unavailable contract/expiry.')
        if parsed.get('missing') or not parsed.get('targets'):
            raise ValueError('Incomplete recommendation.')
        prices = [parsed.get('entry'), parsed.get('stop_loss'), *parsed['targets']]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in prices):
            raise ValueError('Invalid recommendation prices.')
        contract = mapping['contract']
        symbol = contract.get('symbol')
        if not symbol:
            raise ValueError('Missing exact symbol.')
        account = self.reconcile()
        if not isinstance(account, dict) or account.get('verified') is not True:
            raise ValueError('Broker reconciliation unavailable.')
        if symbol in account['occupied_symbols']:
            raise ValueError('Already taken or pending at FYERS.')
        signal = hashlib.sha256(json.dumps([symbol, parsed['action'], parsed['entry'],
                    parsed['stop_loss'], parsed['targets'], parsed.get('entry_instruction')], sort_keys=True).encode()).hexdigest()
        return preview, signal

    def ingest(self, message):
        # This boundary is adapter-only: it is deliberately not a public HTTP input.
        with self.lock:
            if message.get('verified') is not True or message.get('group') != self.config['group']:
                return 'UNVERIFIED_SOURCE'
            if not message.get('id') or not isinstance(message.get('text'), str):
                return 'UNVERIFIED_MESSAGE'
            if message.get('unread_verified') is not True or message.get('is_unread') is not True or message.get('is_latest_unread') is not True:
                return 'UNVERIFIED_UNREAD'
            key = hashlib.sha256((message['group'] + '\0' + str(message['id'])).encode()).hexdigest()
            if self.db.execute('SELECT 1 FROM processed WHERE id=?', (key,)).fetchone() or self.db.execute('SELECT 1 FROM messages WHERE id=?', (key,)).fetchone():
                return 'DUPLICATE'
            # Claim the source ID durably before any parsing or broker reads.
            # Even transient failures must not cause this message to be reprocessed.
            self.db.execute('INSERT INTO processed VALUES (?)', (key,))
            self.db.commit()
            text = message['text']
            data = {'text': text[:12000], 'group': message['group'], 'timestamp': message.get('timestamp')}
            state, signal = 'IGNORED', None
            try:
                if len(text) > 12000 or not self._fresh(message['timestamp']):
                    raise ValueError('Stale or unverified message timestamp.')
                if message.get('is_reply') is not False or message.get('is_forwarded') is not False:
                    raise ValueError('Reply, quoted or forwarded message excluded.')
                if re.search(r'(?im)^\s*>|\b(book(?:ed|ing)?|profit|achieved|hit|exit|closed|update|trail|hold|running)\b', text):
                    raise ValueError('Follow-up or progress report excluded.')
                preview, signal = self._verify(text)
                if self.db.execute('SELECT 1 FROM messages WHERE signal=?', (signal,)).fetchone():
                    raise ValueError('Recommendation already seen/taken.')
                state = 'REVIEW'
                data['preview'] = preview
                data['reason'] = 'Fresh go-ahead required. Review only; no order prepared.'
            except (ValueError, KeyError, TypeError) as error:
                data['reason'] = str(error)
            except Exception:
                # Retain the processed ID; retrying the same message is forbidden.
                return 'RECONCILIATION_UNAVAILABLE'
            self.db.execute('INSERT INTO messages VALUES (?,?,?,?)', (key, signal, state, json.dumps(data)))
            self.db.commit()
            return state

    def review(self, key):
        with self.lock:
            row = self.db.execute('SELECT state,data FROM messages WHERE id=?', (key,)).fetchone()
            if not row or row[0] != 'REVIEW':
                raise ValueError('Recommendation is not available for review.')
            data = json.loads(row[1])
            if data['group'] != self.config['group'] or not self._fresh(data['timestamp']):
                raise ValueError('Recommendation expired or source group changed.')
            preview, _ = self._verify(data['text'])
            return {'text': data['text'], 'preview': preview, 'order_authority': 'NONE'}

    def dismiss(self, key):
        with self.lock:
            self.db.execute("UPDATE messages SET state='DISMISSED' WHERE id=?", (key,))
            self.db.commit()
            return self.status()
