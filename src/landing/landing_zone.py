import uuid
import time
from psycopg2.extras import Json
from core.database import get_conn, release_conn, get_dict_cursor
from core.redis import check_dedup, set_dedup
from core.qdrant import embed_and_store
from core.logger import logger


def write_to_landing_zone(record: dict, campaign_id: str, trace_id: str):
    dedup_key = record.get("dedup_key", "")
    start = time.time()
    event_id = str(uuid.uuid4())

    # 1. Hot dedup check via Redis — before touching DB
    if check_dedup(dedup_key):
        logger.info(
            f"[landing] Duplicate via Redis — skipping", dedup_key=dedup_key[:16]
        )
        return

    conn = get_conn()
    cur = conn.cursor()

    try:
        # 2. Insert raw event
        cur.execute(
            """
            INSERT INTO lz_raw_events
                (event_id, received_at, source_platform, raw_payload,
                 dedup_key, processing_status, agent_trace_id, campaign_id)
            VALUES (%s, NOW(), %s, %s, %s, 'new', %s, %s)
        """,
            (
                event_id,
                record.get("platform", "linkedin"),
                Json(record),
                dedup_key,
                trace_id,
                campaign_id,
            ),
        )

        # 3. Insert lead source
        cur.execute(
            """
            INSERT INTO lz_lead_sources
                (source_id, event_id, source_type, source_url,
                 dedup_key, first_seen_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """,
            (
                str(uuid.uuid4()),
                event_id,
                record.get("type", "unknown"),
                record.get("url", ""),
                dedup_key,
            ),
        )

        # 4. Upsert dedup registry
        cur.execute(
            """
            INSERT INTO lz_dedup_registry
                (dedup_id, dedup_key, first_event_id, latest_event_id,
                 occurrence_count, sources_seen)
            VALUES (%s, %s, %s, %s, 1, %s)
            ON CONFLICT (dedup_key) DO UPDATE
                SET latest_event_id  = EXCLUDED.latest_event_id,
                    occurrence_count = lz_dedup_registry.occurrence_count + 1,
                    sources_seen     = array_append(lz_dedup_registry.sources_seen, %s),
                    updated_at       = NOW()
        """,
            (
                str(uuid.uuid4()),
                dedup_key,
                event_id,
                event_id,
                [record.get("platform", "linkedin")],
                record.get("platform", "linkedin"),
            ),
        )

        # 5. Mark done
        cur.execute(
            """
            UPDATE lz_raw_events
            SET processing_status = 'done'
            WHERE event_id = %s
        """,
            (event_id,),
        )

        duration = int((time.time() - start) * 1000)

        # 6. Extraction log
        _write_extraction_log(
            cur, event_id, "success", extracted_fields=record, duration_ms=duration
        )

        conn.commit()

        # 7. Redis dedup key (after commit — so DB is source of truth first)
        set_dedup(dedup_key, event_id)

        # 8. Qdrant embedding (after commit — non-critical path)
        embed_and_store(record, event_id)

        logger.info(
            "[landing] ✓ Event written", event_id=event_id, duration_ms=duration
        )

    except Exception as e:
        conn.rollback()
        _write_extraction_log(
            cur,
            event_id,
            "failed",
            error=str(e),
            duration_ms=int((time.time() - start) * 1000),
        )
        conn.commit()
        logger.error("[landing] ✗ Write failed", event_id=event_id, error=str(e))
        raise

    finally:
        cur.close()
        release_conn(conn)  # returns to pool, not closed


def _write_extraction_log(
    cur,
    event_id: str,
    status: str,
    extracted_fields: dict = None,
    error: str = None,
    duration_ms: int = 0,
):
    try:
        cur.execute(
            """
            INSERT INTO lz_extraction_logs
                (log_id, event_id, agent_id, extraction_status,
                 extracted_fields, error_message, duration_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            (
                str(uuid.uuid4()),
                event_id,
                "agent-1-data-extraction",
                status,
                Json(extracted_fields) if extracted_fields else None,
                error,
                duration_ms,
            ),
        )
    except Exception as e:
        logger.error("[landing] Log write error", error=str(e))


def save_oauth_tokens(platform: str, tokens: dict):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE lz_platform_integrations
            SET oauth_access_token  = %s,
                oauth_refresh_token = %s,
                oauth_expires_at    = NOW() + INTERVAL '60 days',
                updated_at          = NOW()
            WHERE platform_name = %s
        """,
            (tokens.get("access_token"), tokens.get("refresh_token"), platform),
        )
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)


def get_oauth_tokens(platform: str) -> dict:
    conn = get_conn()
    cur = get_dict_cursor(conn)
    try:
        cur.execute(
            """
            SELECT oauth_access_token, oauth_refresh_token, oauth_expires_at
            FROM lz_platform_integrations
            WHERE platform_name = %s
        """,
            (platform,),
        )
        row = cur.fetchone()
        return dict(row) if row else {}
    finally:
        cur.close()
        release_conn(conn)
