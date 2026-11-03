"""Postgres connection adapter for the database module's small SQLite query dialect.

Local development retains SQLite. Hosted deployments set DATABASE_URL and use
durable Postgres, with the same transactions, row lookups, and public data API.
"""

from contextlib import asynccontextmanager
import re

import psycopg
from psycopg.rows import dict_row

_NOW = "to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')"


def _sql(query: str) -> str:
    query = query.replace(
        "datetime('now', ? || ' minutes')",
        "to_char((CURRENT_TIMESTAMP AT TIME ZONE 'UTC') + "
        "(? || ' minutes')::interval, 'YYYY-MM-DD HH24:MI:SS')",
    )
    return (
        query.replace("datetime('now')", _NOW)
        .replace("date('now')", "(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date::text")
        .replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
        .replace("REAL DEFAULT", "DOUBLE PRECISION DEFAULT")
        .replace("?", "%s")
    )


class _Cursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    async def fetchone(self):
        return await self._cursor.fetchone()

    async def fetchall(self):
        return await self._cursor.fetchall()


class _Query:
    """Support both `await execute(...)` and `async with execute(...)`."""

    def __init__(self, connection, query, parameters):
        self.connection = connection
        self.query = query
        self.parameters = parameters
        self.cursor = None

    async def _execute(self):
        query = _sql(self.query)
        needs_id = bool(re.match(r"\s*INSERT\s+INTO\s+claims\b", query, re.IGNORECASE))
        if needs_id:
            query += " RETURNING id"
        cursor = await self.connection.execute(query, self.parameters or None)
        lastrowid = (await cursor.fetchone())["id"] if needs_id else None
        self.cursor = cursor
        return _Cursor(cursor, lastrowid)

    def __await__(self):
        return self._execute().__await__()

    async def __aenter__(self):
        return await self._execute()

    async def __aexit__(self, *_):
        await self.cursor.close()


class Connection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, query, parameters=()):
        return _Query(self._connection, query, parameters)

    async def executescript(self, script):
        # The schema contains fixed DDL with no parameters or procedural bodies.
        for statement in script.split(";"):
            if statement.strip():
                await self._connection.execute(_sql(statement))

    async def commit(self):
        await self._connection.commit()

    async def rollback(self):
        await self._connection.rollback()


@asynccontextmanager
async def connect(url):
    async with await psycopg.AsyncConnection.connect(
        url, row_factory=dict_row, connect_timeout=15
    ) as connection:
        yield Connection(connection)
