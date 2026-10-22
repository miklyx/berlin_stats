import logging
import os
from contextlib import contextmanager

import dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

SCHEMA_LOCK_ID = 727001
POLL_LOCK_ID = 727002

SCHEMA = """
CREATE TABLE IF NOT EXISTS polizei (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title TEXT,
    time TEXT NOT NULL,
    district TEXT,
    url TEXT,
    details TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_polizei_time ON polizei(time);

CREATE TABLE IF NOT EXISTS meeting (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def init_db():
    with get_pool().connection() as conn:
        # replicas start together; serialize schema creation
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (SCHEMA_LOCK_ID,))
        conn.execute(SCHEMA)


@contextmanager
def poll_lock():
    """Yields True for the one replica that gets to poll, False for the others."""
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        got = conn.execute("SELECT pg_try_advisory_lock(%s)", (POLL_LOCK_ID,)).fetchone()[0]
        yield got


def _clean(value):
    return value.strip() if isinstance(value, str) else (value or "")


def _insert_new(table, columns, rows):
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({', '.join(['%s'] * len(columns))}) ON CONFLICT DO NOTHING"
    )
    values = [tuple(_clean(row.get(c)) for c in columns) for row in rows]
    if not values:
        return 0
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.executemany(sql, values)
        inserted = cur.rowcount
    logger.info("%s: %d new of %d", table, inserted, len(rows))
    return inserted


def existing_polizei_urls():
    with get_pool().connection() as conn:
        return {r["url"] for r in conn.execute("SELECT url FROM polizei")}


def insert_only_new_polizei_data(data):
    return _insert_new("polizei", POLIZEI_COLUMNS, data)


def insert_only_new_meeting_data(data):
    # scraper returns capitalised header ids (Datum, Von, ...)
    rows = [{k.lower(): v for k, v in item.items()} for item in data]
    return _insert_new("meeting", MEETING_COLUMNS, rows)


def _like(keyword):
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search(sql, params):
    with get_pool().connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows or None


def find_meeting_by_keyword(keyword):
    return _search("SELECT * FROM meeting WHERE thema ILIKE %s ORDER BY id", (_like(keyword),))


def find_polizei_by_keyword(keyword):
    return _search("SELECT * FROM polizei WHERE details ILIKE %s ORDER BY id", (_like(keyword),))


def find_meeting_by_datum_and_keyword(datum, keyword):
    return _search(
        "SELECT * FROM meeting WHERE thema ILIKE %s AND datum = %s ORDER BY id",
        (_like(keyword), datum),
    )
