from agents.agent2.state import Agent2State
from core.database import get_conn, release_conn, get_dict_cursor
from core.redis import get_redis
from core.logger import logger

PROMOTED_SET = "op:promoted_events"
BATCH_SIZE   = 50


def fetch_node(state: Agent2State) -> Agent2State:
    logger.info("[agent2/fetch] Starting", trigger=state["trigger_type"])
    r    = get_redis()
    conn = get_conn()
    cur  = get_dict_cursor(conn)

    try:
        if state["trigger_type"] == "realtime":
            return _fetch_realtime(state, r, conn, cur)
        return _fetch_batch(state, r, conn, cur)
    finally:
        cur.close()
        release_conn(conn)


def _fetch_realtime(state, r, conn, cur) -> Agent2State:
    items = r.zpopmin("op:lead_score_queue", count=10)
    if not items:
        logger.info("[agent2/fetch] No high-intent events in queue")
        state["raw_events"] = []
        state["run_status"] = "done"
        return state

    event_ids = [
        i[0].decode() if isinstance(i[0], bytes) else i[0]
        for i in items
    ]
    new_ids = [eid for eid in event_ids
               if not r.sismember(PROMOTED_SET, eid)]

    if not new_ids:
        logger.info("[agent2/fetch] All realtime events already promoted")
        state["raw_events"] = []
        state["run_status"] = "done"
        return state

    cur.execute("""
        SELECT event_id, source_platform, raw_payload,
               dedup_key, campaign_id, received_at
        FROM lz_raw_events
        WHERE event_id = ANY(%s)
          AND processing_status = 'done'
    """, (new_ids,))

    rows = cur.fetchall()
    state["raw_events"] = [dict(r) for r in rows]
    logger.info("[agent2/fetch] Realtime events fetched", count=len(rows))
    return state


def _fetch_batch(state, r, conn, cur) -> Agent2State:
    promoted = {
        p.decode() if isinstance(p, bytes) else p
        for p in r.smembers(PROMOTED_SET)
    }

    cur.execute("""
        SELECT event_id, source_platform, raw_payload,
               dedup_key, campaign_id, received_at
        FROM lz_raw_events
        WHERE processing_status = 'done'
        ORDER BY received_at DESC
        LIMIT %s
    """, (BATCH_SIZE,))

    rows = [
        dict(row) for row in cur.fetchall()
        if str(row["event_id"]) not in promoted
    ]
    state["raw_events"] = rows
    logger.info("[agent2/fetch] Batch events fetched", count=len(rows))
    return state