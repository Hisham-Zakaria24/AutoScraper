"""SQLite storage. Made by Hisham-Zakaria."""
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config TEXT NOT NULL,
    next_run REAL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    started REAL NOT NULL,
    finished REAL,
    status TEXT NOT NULL,
    pages INTEGER DEFAULT 0,
    found INTEGER DEFAULT 0,
    added INTEGER DEFAULT 0,
    error TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    hash TEXT NOT NULL,
    data TEXT NOT NULL,
    first_seen REAL NOT NULL,
    UNIQUE (job_id, hash)
);
"""


class Database:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    @staticmethod
    def _next_run(config):
        # A scheduled job is due immediately after it is saved.
        return time.time() if config.get("interval_minutes") else None

    def add_job(self, config):
        with self.connect() as con:
            return con.execute("INSERT INTO jobs (config, next_run) VALUES (?, ?)",
                               (json.dumps(config), self._next_run(config))).lastrowid

    def update_job(self, job_id, config):
        with self.connect() as con:
            con.execute("UPDATE jobs SET config=?, next_run=? WHERE id=?",
                        (json.dumps(config), self._next_run(config), job_id))

    def delete_job(self, job_id):
        with self.connect() as con:
            con.execute("DELETE FROM jobs WHERE id=?", (job_id,))

    def get_job(self, job_id):
        with self.connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        return {**json.loads(row["config"]), "id": row["id"], "next_run": row["next_run"]}

    def list_jobs(self):
        sql = """SELECT j.*,
          (SELECT COUNT(*) FROM items WHERE job_id=j.id) AS total,
          (SELECT status FROM runs WHERE job_id=j.id ORDER BY id DESC LIMIT 1) AS last_status
          FROM jobs j ORDER BY j.id DESC"""
        with self.connect() as con:
            rows = con.execute(sql).fetchall()
        return [{**json.loads(r["config"]), "id": r["id"], "next_run": r["next_run"],
                 "total": r["total"], "last_status": r["last_status"]} for r in rows]

    def due_jobs(self, now):
        with self.connect() as con:
            rows = con.execute("SELECT id FROM jobs WHERE next_run IS NOT NULL "
                               "AND next_run<=?", (now,)).fetchall()
        return [r["id"] for r in rows]

    def set_next_run(self, job_id, when):
        with self.connect() as con:
            con.execute("UPDATE jobs SET next_run=? WHERE id=?", (when, job_id))

    def start_run(self, job_id):
        with self.connect() as con:
            return con.execute("INSERT INTO runs (job_id, started, status) "
                               "VALUES (?, ?, 'running')", (job_id, time.time())).lastrowid

    def finish_run(self, run_id, status, pages=0, found=0, added=0, error=""):
        with self.connect() as con:
            con.execute("UPDATE runs SET finished=?, status=?, pages=?, found=?, "
                        "added=?, error=? WHERE id=?",
                        (time.time(), status, pages, found, added, error, run_id))

    def close_stale_runs(self):
        with self.connect() as con:
            con.execute("UPDATE runs SET status='failed', finished=?, "
                        "error='App band ho gayi thi' WHERE status='running'",
                        (time.time(),))

    def list_runs(self, job_id, limit=20):
        with self.connect() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM runs WHERE job_id=? ORDER BY id DESC LIMIT ?",
                (job_id, limit))]

    def save_items(self, job_id, rows):
        """Insert only new rows. Returns how many were added."""
        added, now = 0, time.time()
        with self.connect() as con:
            for row in rows:
                data = json.dumps(row, ensure_ascii=False, sort_keys=True)
                digest = hashlib.sha256(data.encode()).hexdigest()
                added += con.execute(
                    "INSERT OR IGNORE INTO items (job_id, hash, data, first_seen) "
                    "VALUES (?, ?, ?, ?)",
                    (job_id, digest, json.dumps(row, ensure_ascii=False), now)).rowcount
        return added

    def get_items(self, job_id, limit=None, offset=0, search=""):
        with self.connect() as con:
            rows = con.execute("SELECT * FROM items WHERE job_id=? ORDER BY id DESC",
                               (job_id,)).fetchall()
        items = [{**json.loads(r["data"]), "_first_seen": r["first_seen"]} for r in rows]
        if search:
            needle = search.casefold()
            items = [i for i in items if any(
                needle in str(v).casefold() for k, v in i.items() if k != "_first_seen")]
        end = None if limit is None else offset + limit
        return items[offset:end], len(items)

    def clear_items(self, job_id):
        with self.connect() as con:
            con.execute("DELETE FROM items WHERE job_id=?", (job_id,))
