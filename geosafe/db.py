"""Database connection abstraction supporting SQLite and PostgreSQL."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

try:
    import psycopg2
    from psycopg2 import pool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class DatabaseConnection:
    """Abstract database connection wrapper."""

    def execute(self, query: str, params: tuple = ()) -> "DatabaseCursor":
        raise NotImplementedError

    def executescript(self, script: str) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class DatabaseCursor:
    """Abstract cursor wrapper."""

    def fetchone(self) -> dict | None:
        raise NotImplementedError

    def fetchall(self) -> list[dict]:
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError


class SqliteConnection(DatabaseConnection):
    """SQLite connection wrapper."""

    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection

    def execute(self, query: str, params: tuple = ()) -> SqliteCursor:
        return SqliteCursor(self._conn.execute(query, params))

    def executescript(self, script: str) -> None:
        self._conn.executescript(script)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class SqliteCursor(DatabaseCursor):
    """SQLite cursor wrapper."""

    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor

    def fetchone(self) -> dict | None:
        row = self._cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self) -> list[dict]:
        return [dict(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self._cursor)

    @property
    def lastrowid(self) -> int | None:
        return self._cursor.lastrowid


class PostgresConnection(DatabaseConnection):
    """PostgreSQL connection wrapper."""

    def __init__(self, connection):
        self._conn = connection

    def execute(self, query: str, params: tuple = ()) -> PostgresCursor:
        cursor = self._conn.cursor()
        # Convert SQLite ? placeholders to PostgreSQL %s
        pg_query = query.replace("?", "%s")
        cursor.execute(pg_query, params)
        return PostgresCursor(cursor)

    def executescript(self, script: str) -> None:
        # For PostgreSQL, we need to parse and execute statements
        cursor = self._conn.cursor()
        statements = [s.strip() for s in script.split(";") if s.strip()]
        for statement in statements:
            try:
                cursor.execute(statement)
            except Exception:
                pass  # Skip errors during schema initialization
        cursor.close()

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class PostgresCursor(DatabaseCursor):
    """PostgreSQL cursor wrapper."""

    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self) -> dict | None:
        columns = [desc[0] for desc in self._cursor.description] if self._cursor.description else []
        row = self._cursor.fetchone()
        return dict(zip(columns, row)) if row else None

    def fetchall(self) -> list[dict]:
        columns = [desc[0] for desc in self._cursor.description] if self._cursor.description else []
        rows = self._cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def __iter__(self):
        return iter(self._cursor)

    @property
    def lastrowid(self) -> int | None:
        return getattr(self._cursor, 'lastrowid', None)


class DatabaseProvider:
    """Factory for database connections supporting SQLite and PostgreSQL."""

    def __init__(self, sqlite_path: str | Path | None = None, postgres_url: str | None = None):
        self.sqlite_path = Path(sqlite_path) if sqlite_path else None
        self.postgres_url = postgres_url or os.environ.get("DATABASE_URL")
        self.is_postgres = bool(self.postgres_url)
        self._pool = None

        if self.is_postgres and not PSYCOPG2_AVAILABLE:
            raise RuntimeError(
                "psycopg2 is required for PostgreSQL support. "
                "Install with: pip install psycopg2-binary"
            )

        if self.is_postgres:
            self._init_postgres_pool()

    def _init_postgres_pool(self) -> None:
        """Initialize PostgreSQL connection pool for Vercel's multi-worker environment."""
        # Vercel serverless functions don't need large pools, but we create one per process
        min_conns = 1
        max_conns = 5
        try:
            self._pool = pool.SimpleConnectionPool(
                min_conns,
                max_conns,
                self.postgres_url,
                connect_timeout=5,
                options="-c statement_timeout=30000",  # 30 second statement timeout
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create PostgreSQL connection pool: {e}") from e

    @contextmanager
    def connection(self) -> Iterable[DatabaseConnection]:
        """Get a database connection."""
        if self.is_postgres:
            pg_conn = self._pool.getconn()
            try:
                yield PostgresConnection(pg_conn)
            finally:
                self._pool.putconn(pg_conn)
        else:
            if not self.sqlite_path:
                raise RuntimeError("SQLite path is required when not using PostgreSQL")
            sqlite_conn = sqlite3.connect(
                self.sqlite_path,
                timeout=10,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            sqlite_conn.row_factory = sqlite3.Row
            sqlite_conn.execute("PRAGMA foreign_keys = ON")
            sqlite_conn.execute("PRAGMA busy_timeout = 10000")
            try:
                yield SqliteConnection(sqlite_conn)
            finally:
                sqlite_conn.close()

    def close_pool(self) -> None:
        """Close the connection pool (PostgreSQL only)."""
        if self._pool:
            self._pool.closeall()

    def __del__(self):
        """Clean up the pool on deletion."""
        self.close_pool()
