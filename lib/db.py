import sqlite3
from pathlib import Path

from lib.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL DEFAULT 'rss',
    weight REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS raw_items (
    id TEXT PRIMARY KEY,
    source_id INTEGER,
    url TEXT,
    title TEXT,
    author TEXT,
    published_at TEXT,
    text TEXT,
    meta_json TEXT,
    fetched_at TEXT,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_label INTEGER,
    score REAL,
    title TEXT,
    summary TEXT,
    created_at TEXT
);
"""


def get_db() -> sqlite3.Connection:
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {settings.DB_PATH}")
