"""One-off: merge one or more SQLite files into Postgres (DATABASE_URL).

Usage: python migrate_sqlite_to_pg.py a.db b.db c.db
Duplicates are dropped by the unique indexes, so it is safe to re-run.
"""
import sqlite3
import sys

import db


def read(path, table, columns):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def main(paths):
    db.init_db()
    for path in paths:
        polizei = read(path, "polizei", db.POLIZEI_COLUMNS)
        meetings = read(path, "meeting", db.MEETING_COLUMNS)
        new_p = db._insert_new("polizei", db.POLIZEI_COLUMNS, polizei)
        new_m = db._insert_new("meeting", db.MEETING_COLUMNS, meetings)
        print(f"{path}: polizei {len(polizei)} read / {new_p} new, meeting {len(meetings)} read / {new_m} new")
    db.close_pool()


if __name__ == "__main__":
    main(sys.argv[1:])
