"""SQLite (WAL) + esquema. Una conexión por hilo; sin ORM (A10)."""
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  filename TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'en',
  status TEXT NOT NULL DEFAULT 'uploaded',
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  total_cost_cents REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sections (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
  id INTEGER PRIMARY KEY,
  section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,
  text_clean TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  audio_path TEXT,
  audio_status TEXT NOT NULL DEFAULT 'pending',
  duration_ms INTEGER,
  tts_cost_cents REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_blocks_doc ON blocks(document_id, idx);
CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(text_hash);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}',
  priority INTEGER NOT NULL DEFAULT 5,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_pending ON jobs(status, priority, id);
CREATE TABLE IF NOT EXISTS positions (
  document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  block_id INTEGER NOT NULL,
  offset_ms INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS costs (
  id INTEGER PRIMARY KEY,
  document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
  kind TEXT NOT NULL,
  chars INTEGER NOT NULL,
  cost_cents REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_local = threading.local()
_db_path: Path | None = None


def init(path: Path) -> None:
    global _db_path
    _db_path = path
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()


def connect() -> sqlite3.Connection:
    assert _db_path is not None, "db.init() no llamado"
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != _db_path:
        conn = sqlite3.connect(_db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
        _local.path = _db_path
    return conn
