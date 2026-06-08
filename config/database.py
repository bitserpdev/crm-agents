import os
import psycopg2
import psycopg2.extras
from config.logger import logger

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn() -> psycopg2.extensions.connection:
    logger.debug("[db] Opening connection...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("[db] ✓ Connection established")
        return conn
    except Exception as e:
        logger.error(f"[db] ✗ Connection failed: {e}")
        raise


def get_dict_conn() -> psycopg2.extensions.connection:
    """Returns a connection whose cursors yield RealDictRow results."""
    logger.debug("[db] Opening dict connection...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("[db] ✓ Dict connection established")
        return conn
    except Exception as e:
        logger.error(f"[db] ✗ Dict connection failed: {e}")
        raise
