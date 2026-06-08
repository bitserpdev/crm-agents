import os
from contextlib import contextmanager
from psycopg2 import pool, extras
from core.logger import logger

DATABASE_URL = os.getenv("DATABASE_URL")
MIN_CONN = int(os.getenv("DB_POOL_MIN", 2))
MAX_CONN = int(os.getenv("DB_POOL_MAX", 10))

_pool = None


def get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        logger.info(
            f"[db] Initializing connection pool (min={MIN_CONN}, max={MAX_CONN})"
        )
        _pool = pool.ThreadedConnectionPool(MIN_CONN, MAX_CONN, DATABASE_URL)
    return _pool


def get_conn():
    conn = get_pool().getconn()
    logger.debug("[db] Connection acquired from pool")
    return conn


def release_conn(conn):
    get_pool().putconn(conn)
    logger.debug("[db] Connection returned to pool")


def get_dict_cursor(conn):
    """Returns a RealDictCursor from a pooled connection."""
    return conn.cursor(cursor_factory=extras.RealDictCursor)


def close_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        logger.info("[db] Connection pool closed")


@contextmanager
def get_db():
    """
    Always use this in repositories instead of get_conn() / release_conn().
    Guarantees the connection is returned to the pool even if an exception occurs.

    Usage:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(...)
    """
    conn = get_conn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)