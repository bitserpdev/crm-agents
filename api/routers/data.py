import os
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Query
from typing import Optional
from landing.qdrant_client import get_qdrant, get_embedder

router = APIRouter()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@router.get("/raw")
def get_raw_events(
    platform: Optional[str] = None,
    status:   Optional[str] = None,
    limit:    int = 50,
    offset:   int = 0
):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    filters = []
    values  = []
    if platform:
        filters.append("source_platform = %s"); values.append(platform)
    if status:
        filters.append("processing_status = %s"); values.append(status)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    values += [limit, offset]
    cur.execute(f"""
        SELECT event_id, received_at, source_platform,
               raw_payload, dedup_key, processing_status,
               campaign_id, created_at
        FROM lz_raw_events
        {where}
        ORDER BY received_at DESC
        LIMIT %s OFFSET %s
    """, values)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return {"total": len(rows), "records": [dict(r) for r in rows]}

@router.get("/search")
def semantic_search(
    q:        str = Query(..., description="Search query"),
    limit:    int = 10,
    platform: Optional[str] = None
):
    try:
        vector = get_embedder().embed_query(q)
        client = get_qdrant()

        # Build filter
        qf = None
        if platform:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            qf = Filter(must=[
                FieldCondition(key="source_platform",
                               match=MatchValue(value=platform))
            ])

        # Use query_points (newer qdrant-client API)
        results = client.query_points(
            collection_name="lz_raw_message_embeddings",
            query=vector,
            limit=limit,
            query_filter=qf
        )
        hits = results.points if hasattr(results, "points") else list(results)

        output = []
        for h in hits:
            output.append({
                "event_id":        h.payload.get("point_id"),
                "score":           round(h.score, 4),
                "source_platform": h.payload.get("source_platform"),
                "received_at":     h.payload.get("received_at"),
                "dedup_key":       h.payload.get("dedup_key"),
            })
        return {"query": q, "results": output}

    except Exception as e:
        return {"query": q, "error": str(e), "results": []}

@router.get("/stats")
def data_stats():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            source_platform,
            COUNT(*)                                            AS total_events,
            COUNT(*) FILTER (WHERE processing_status='done')   AS done,
            COUNT(*) FILTER (WHERE processing_status='duplicate') AS duplicates
        FROM lz_raw_events
        GROUP BY source_platform
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]
