"""Durable at-most-once guard for a deliberate parser Submit action."""
import hashlib
import json
import sqlite3
import threading
import uuid


class ParserSubmissionGuard:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute('CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT)')
        self.db.commit()

    def submit(self, key, payload, callback):
        try:
            uuid.UUID(key)
        except ValueError as error:
            raise ValueError('A parsed submission identifier is required.') from error
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.lock:
            row = self.db.execute('SELECT digest,result FROM submissions WHERE id=?', (key,)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError('Submission terms changed; check the broker before submitting again.')
                if row[1]:
                    return json.loads(row[1])
                raise ValueError('Submission is pending or uncertain; check the FYERS orderbook. No retry sent.')
            self.db.execute('INSERT INTO submissions VALUES (?,?,NULL)', (key, digest))
            self.db.commit()
        # Reservation survives failures/restarts, including an uncertain broker acknowledgement.
        result = callback()
        with self.lock:
            self.db.execute('UPDATE submissions SET result=? WHERE id=?', (json.dumps(result), key))
            self.db.commit()
        return result
