from __future__ import annotations

import fcntl
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .processor import Options, ProcessingError, process_lead

logger = logging.getLogger("lead_phone")


class Queue:
    """Durable ID-only queue. One worker; HTTP enqueues via separate connections."""

    def __init__(self, path: str, options: Options, clock=time.time):
        self.path = Path(path)
        self.options = options
        self.clock = clock
        self._lock = None

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = open(str(self.path) + ".lock", "a")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.connection() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                    lead_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL,
                    error_code TEXT, changed INTEGER NOT NULL DEFAULT 0)""")
                db.execute("CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(status, next_at)")
        except Exception:
            self.close()
            raise

    def close(self):
        if self._lock:
            self._lock.close()
            self._lock = None

    def enqueue(self, lead_id: str) -> bool:
        with self.connection() as db:
            cursor = db.execute("INSERT OR IGNORE INTO jobs(lead_id, next_at) VALUES (?, ?)", (lead_id, self.clock()))
            return cursor.rowcount == 1

    def tick(self, call):
        with self.connection() as db:
            job = db.execute("SELECT * FROM jobs WHERE status='pending' AND next_at<=? ORDER BY next_at LIMIT 1",
                             (self.clock(),)).fetchone()
        if job is None:
            return
        lead_id, attempts = job["lead_id"], job["attempts"] + 1
        changed, error_code = 0, None
        try:
            status, changed = process_lead(call, lead_id, self.options)
        except ProcessingError as exc:
            error_code = exc.code
            status = "pending" if exc.retryable and attempts < self.options.max_attempts else "failed"
        except Exception:
            # Programmer/unknown errors must not leak payloads or silently mutate data.
            error_code, status = "UNEXPECTED_ERROR", "failed"
        next_at = self.clock() + min(300, self.options.retry_seconds * 2 ** (attempts - 1))
        with self.connection() as db:
            db.execute("UPDATE jobs SET status=?, attempts=?, next_at=?, error_code=?, changed=? WHERE lead_id=?",
                       (status, attempts, next_at, error_code, changed, lead_id))
        logger.info("lead_phone status=%s lead_id=%s attempts=%s changed=%s code=%s",
                    status, lead_id, attempts, changed, error_code or "none")

    def stats(self):
        with self.connection() as db:
            return {row["status"]: row["count"] for row in db.execute("SELECT status, count(*) AS count FROM jobs GROUP BY status")}
