"""Import a consistent SQLite backup into an empty hosted Postgres database.

Usage: DATABASE_URL=... python -m scripts.import_sqlite /path/to/factchecker.db
The destination connection stays in the environment; it is never logged.
"""

import argparse
import asyncio
import sqlite3
from pathlib import Path

import psycopg
from psycopg import sql

from backend import database as db

TABLES = ("videos", "claims", "claim_sources")


def import_rows(source_path, destination_url):
    source_path = Path(source_path).resolve()
    with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Source SQLite integrity check failed")
        with psycopg.connect(destination_url) as destination:
            # All rows and sequence changes commit together. A populated destination
            # is rejected instead of silently overwriting or duplicating data.
            for table in TABLES:
                count = destination.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(
                    sql.Identifier(table),
                )).fetchone()[0]
                if count:
                    raise RuntimeError(f"Destination table {table} is not empty")
            counts = {}
            for table in TABLES:
                cursor = source.execute(f'SELECT * FROM "{table}" ORDER BY id')
                columns = [item[0] for item in cursor.description]
                rows = cursor.fetchall()
                statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                with destination.cursor() as target:
                    target.executemany(statement, rows)
                actual = destination.execute(sql.SQL("SELECT {} FROM {} ORDER BY id").format(
                    sql.SQL(", ").join(map(sql.Identifier, columns)), sql.Identifier(table),
                )).fetchall()
                # SQLite and Postgres can use different text collations. Compare
                # by primary key, independently of each server's ordering.
                id_column = columns.index("id")
                if ({row[id_column]: row for row in actual}
                        != {row[id_column]: row for row in rows}):
                    raise RuntimeError(f"Read-back mismatch for {table}; rolling back")
                counts[table] = len(rows)
            for table in ("claims", "claim_sources"):
                destination.execute(sql.SQL(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                    "GREATEST(COALESCE(MAX(id), 0), 1), COUNT(*) > 0) FROM {}"
                ).format(sql.Identifier(table)), (table,))
            return counts


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    args = parser.parse_args()
    if not db._DATABASE_URL:
        parser.error("Set DATABASE_URL to the destination Postgres database")
    await db.init_db()
    counts = await asyncio.to_thread(import_rows, args.source, db._DATABASE_URL)
    print("Imported and verified:", ", ".join(f"{n} {table}" for table, n in counts.items()))


if __name__ == "__main__":
    asyncio.run(main())
