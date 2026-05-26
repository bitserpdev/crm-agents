import os
import uuid
import json
import time
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
from landing.redis_client import check_dedup, set_dedup
from landing.qdrant_client import embed_and_store

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def write_to_landing_zone(record: dict, campaign_id: str, trace_id: str):
    dedup_key = record.get("dedup_key", "")
    start     = time.time()
    event_id  = str(uuid.uuid4())

    conn = get_conn()
    cur  = conn.cursor()

    try:
        # 1. Hot dedup check via Redis
        existing = check_dedup(dedup_key)
        if existing:
            print(f"[postgres] Duplicate detected via Redis — skipping {dedup_key[:16]}...")
            conn.close()
            return

        # 2. Insert raw event
        cur.execute("""
            INSERT INTO lz_raw_events
                (event_id, received_at, source_platform, raw_payload,
                 dedup_key, processing_status, agent_trace_id, campaign_id)
            VALUES (%s, NOW(), %s, %s, %s, 'new', %s, %s)
        """, (
            event_id,
            record.get("platform", "linkedin"),
            Json(record),
            dedup_key,
            trace_id,
            campaign_id,
        ))

        # 3. Insert lead source
        cur.execute("""
            INSERT INTO lz_lead_sources
                (source_id, event_id, source_type, source_url,
                 dedup_key, first_seen_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            str(uuid.uuid4()),
            event_id,
            record.get("type", "unknown"),
            record.get("url", ""),
            dedup_key,
        ))

        # 4. Upsert dedup registry
        cur.execute("""
            INSERT INTO lz_dedup_registry
                (dedup_id, dedup_key, first_event_id, latest_event_id,
                 occurrence_count, sources_seen)
            VALUES (%s, %s, %s, %s, 1, %s)
            ON CONFLICT (dedup_key) DO UPDATE
                SET latest_event_id  = EXCLUDED.latest_event_id,
                    occurrence_count = lz_dedup_registry.occurrence_count + 1,
                    sources_seen     = array_append(lz_dedup_registry.sources_seen,
                                       %s),
                    updated_at       = NOW()
        """, (
            str(uuid.uuid4()),
            dedup_key,
            event_id,
            event_id,
            [record.get("platform", "linkedin")],
            record.get("platform", "linkedin"),
        ))

        # 5. Mark event as processing done
        cur.execute("""
            UPDATE lz_raw_events
            SET processing_status = 'done'
            WHERE event_id = %s
        """, (event_id,))

        duration = int((time.time() - start) * 1000)

        # 6. Write extraction log
        _write_extraction_log(
            cur, event_id, "success",
            extracted_fields=record,
            duration_ms=duration
        )

        conn.commit()

        # 7. Set Redis dedup key (24h TTL)
        set_dedup(dedup_key, event_id)

        # 8. Embed and store in Qdrant
        embed_and_store(record, event_id)

        print(f"[postgres] ✓ Wrote event {event_id} ({duration}ms)")

    except Exception as e:
        conn.rollback()
        _write_extraction_log(cur, event_id, "failed",
                              error=str(e),
                              duration_ms=int((time.time()-start)*1000))
        conn.commit()
        raise e
    finally:
        cur.close()
        conn.close()

def _write_extraction_log(cur, event_id, status,
                          extracted_fields=None,
                          error=None, duration_ms=0):
    try:
        cur.execute("""
            INSERT INTO lz_extraction_logs
                (log_id, event_id, agent_id, extraction_status,
                 extracted_fields, error_message, duration_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            str(uuid.uuid4()),
            event_id,
            "agent-1-data-extraction",
            status,
            Json(extracted_fields) if extracted_fields else None,
            error,
            duration_ms,
        ))
    except Exception as e:
        print(f"[postgres] Log write error: {e}")

def save_oauth_tokens(platform: str, tokens: dict):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE lz_platform_integrations
        SET oauth_access_token  = %s,
            oauth_refresh_token = %s,
            oauth_expires_at    = NOW() + INTERVAL '60 days',
            updated_at          = NOW()
        WHERE platform_name = %s
    """, (tokens.get("access_token"), tokens.get("refresh_token"), platform))
    conn.commit()
    cur.close()
    conn.close()

def get_oauth_tokens(platform: str) -> dict:
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT oauth_access_token, oauth_refresh_token, oauth_expires_at
        FROM lz_platform_integrations
        WHERE platform_name = %s
    """, (platform,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else {}
