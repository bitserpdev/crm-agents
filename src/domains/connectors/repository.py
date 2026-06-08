from core.database import get_conn, release_conn, get_dict_cursor
from core.logger import logger


def get_all_integrations() -> list:
    conn = get_conn()
    cur  = get_dict_cursor(conn)
    try:
        cur.execute("""
            SELECT platform_name, auth_type, is_active,
                   last_synced_at, polling_interval_sec,
                   CASE WHEN oauth_access_token IS NOT NULL
                        THEN 'connected' ELSE 'disconnected'
                   END AS auth_status,
                   oauth_expires_at
            FROM lz_platform_integrations
            ORDER BY platform_name
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        release_conn(conn)


def get_integration(platform: str) -> dict | None:
    conn = get_conn()
    cur  = get_dict_cursor(conn)
    try:
        cur.execute("""
            SELECT * FROM lz_platform_integrations
            WHERE platform_name = %s
        """, (platform,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()
        release_conn(conn)


def update_last_synced(platform: str):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE lz_platform_integrations
            SET last_synced_at = NOW()
            WHERE platform_name = %s
        """, (platform,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("[connectors.repo] update_last_synced failed",
                     platform=platform, error=str(e))
        raise
    finally:
        cur.close()
        release_conn(conn)