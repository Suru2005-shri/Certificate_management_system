from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import DATABASE_URL

# Least-privilege DB role should be used in DATABASE_URL (no superuser).
pool = ConnectionPool(
    DATABASE_URL or "postgresql://unset@localhost/unset",
    kwargs={"row_factory": dict_row},
    min_size=1, max_size=10, open=False,
)


def open_pool() -> None:
    pool.open()


def close_pool() -> None:
    pool.close()


def fetch_all(sql: str, params: Any = None) -> list[dict]:
    with pool.connection() as c:
        return c.execute(sql, params).fetchall()


def fetch_one(sql: str, params: Any = None) -> dict | None:
    with pool.connection() as c:
        return c.execute(sql, params).fetchone()


def execute(sql: str, params: Any = None) -> None:
    with pool.connection() as c:
        c.execute(sql, params)
