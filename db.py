import logging
import os
import sqlite3
import threading
from contextlib import closing

import dotenv

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

_write_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS polizei (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    time TEXT NOT NULL,
    district TEXT,
    url TEXT,
    details TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_polizei_time ON polizei(time);

CREATE TABLE IF NOT EXISTS meeting (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datum TEXT NOT NULL,
    von TEXT NOT NULL,
    bis TEXT,
    thema TEXT NOT NULL,
    plz TEXT,
    versammlungsort TEXT,
    aufzugsstrecke TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_meeting_key ON meeting(von, datum, thema);
"""

MEETING_COLUMNS = ("datum", "von", "bis", "thema", "plz", "versammlungsort", "aufzugsstrecke")
POLIZEI_COLUMNS = ("title", "time", "district", "url", "details")


def get_db_path():
    return os.environ.get("DB_PATH", "data/berlin_stats.db")


def connect():
    path = get_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _insert_new(table, columns, rows):
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    values = [tuple((row.get(c) or "").strip() if isinstance(row.get(c) or "", str) else row.get(c) for c in columns) for row in rows]
    with _write_lock, closing(connect()) as conn:
        conn.executescript(SCHEMA)
        before = conn.total_changes
        conn.executemany(sql, values)
        conn.commit()
        inserted = conn.total_changes - before
    logger.info("%s: %d new of %d", table, inserted, len(rows))
    return inserted


def insert_only_new_polizei_data(data):
    rows = [{k: item.get(k) for k in POLIZEI_COLUMNS} for item in data]
    return _insert_new("polizei", POLIZEI_COLUMNS, rows)


def insert_only_new_meeting_data(data):
    # scraper returns capitalised header ids (Datum, Von, ...)
    rows = [{k.lower(): v for k, v in item.items()} for item in data]
    return _insert_new("meeting", MEETING_COLUMNS, rows)


def _search(sql, params):
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows] or None


def _like(keyword):
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def find_meeting_by_keyword(keyword):
    return _search("SELECT * FROM meeting WHERE thema LIKE ? ESCAPE '\\'", (_like(keyword),))


def find_polizei_by_keyword(keyword):
    return _search("SELECT * FROM polizei WHERE details LIKE ? ESCAPE '\\'", (_like(keyword),))


def find_meeting_by_datum_and_keyword(datum, keyword):
    return _search(
        "SELECT * FROM meeting WHERE thema LIKE ? ESCAPE '\\' AND datum = ?",
        (_like(keyword), datum),
    )
