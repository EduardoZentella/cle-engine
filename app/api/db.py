"""Database pool utilities for PostgreSQL access.

The `DatabasePool` wrapper provides:

- explicit pool open/close lifecycle
- per-operation transactional context management
- automatic commit/rollback behavior
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from psycopg2.extensions import connection as PgConnection
from psycopg2.pool import ThreadedConnectionPool


class DatabasePool:
    """Small wrapper around psycopg2 pool with transaction handling."""

    def __init__(self, dsn: str, min_size: int, max_size: int) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: ThreadedConnectionPool | None = None

    def open(self) -> None:
        """Initialize the connection pool if it is not already open."""

        if self._pool is None:
            self._pool = ThreadedConnectionPool(self._min_size, self._max_size, self._dsn)

    def close(self) -> None:
        """Close all pooled connections and reset pool state."""

        if self._pool is not None:
            self._pool.closeall()
            self._pool = None

    @contextmanager
    def connection(self) -> Iterator[PgConnection]:
        """Provide a transaction-scoped database connection.

        Behavior:

        - yields one connection from the pool
        - commits on success
        - rolls back on exception
        - returns connection to pool in all cases
        """

        if self._pool is None:
            raise RuntimeError("Database pool is not initialized.")

        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)