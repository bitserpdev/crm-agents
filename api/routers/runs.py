import os
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException

router = APIRouter()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@router.get("")
def list_runs(limit: int = 50):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            el.log_id, el.event_id, el.agent_id,
            el.extraction_status, el.duration_ms, el.ran_at,
            el.error_message,
            re.source_platform, re.campaign_id, re.processing_status
        FROM lz_extraction_logs el
        JOIN lz_raw_events re ON re.event_id = el.event_id
        ORDER BY el.ran_at DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

@router.get("/campaign/{campaign_id}")
def runs_by_campaign(campaign_id: str, limit: int = 50):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            el.log_id, el.event_id, el.agent_id,
            el.extraction_status, el.duration_ms,
            el.ran_at, el.error_message,
            re.source_platform, re.processing_status
        FROM lz_extraction_logs el
        JOIN lz_raw_events re ON re.event_id = el.event_id
        WHERE re.campaign_id = %s
        ORDER BY el.ran_at DESC
        LIMIT %s
    """, (campaign_id, limit))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

@router.get("/{log_id}")
def get_run_detail(log_id: str):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT el.*, re.raw_payload, re.source_platform,
               re.processing_status, re.campaign_id
        FROM lz_extraction_logs el
        JOIN lz_raw_events re ON re.event_id = el.event_id
        WHERE el.log_id = %s
    """, (log_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return dict(row)

@router.get("/stats/summary")
def run_stats():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            extraction_status,
            COUNT(*)         AS count,
            AVG(duration_ms) AS avg_duration_ms
        FROM lz_extraction_logs
        GROUP BY extraction_status
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]
