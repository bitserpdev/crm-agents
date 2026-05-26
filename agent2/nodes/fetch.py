import os
import redis
import psycopg2
import psycopg2.extras
from agent2.state import Agent2State

r = redis.from_url(os.getenv("REDIS_URL"))
PROMOTED_SET = "op:promoted_events"
BATCH_SIZE   = 50

def fetch_node(state: Agent2State) -> Agent2State:
    print(f"[agent2/fetch] Trigger: {state['trigger_type']}")
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if state["trigger_type"] == "realtime":
        # Pop high-intent event IDs from Redis sorted set
        items = r.zpopmin("op:lead_score_queue", count=10)
        event_ids = [item[0].decode() if isinstance(item[0], bytes)
                     else item[0] for item, _ in items] if items else []
        # Also pop any tuples
        if items and isinstance(items[0], tuple):
            event_ids = [i[0].decode() if isinstance(i[0], bytes) else i[0]
                         for i in items]

        if not event_ids:
            print("[agent2/fetch] No high-intent events in queue")
            state["raw_events"] = []
            state["run_status"] = "done"
            return state

        # Filter out already promoted
        new_ids = [eid for eid in event_ids
                   if not r.sismember(PROMOTED_SET, eid)]

        if not new_ids:
            print("[agent2/fetch] All events already promoted")
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

    else:
        # Batch: fetch all done events not yet promoted
        # Get already promoted set from Redis
        promoted = r.smembers(PROMOTED_SET)
        promoted_ids = [p.decode() if isinstance(p, bytes) else p
                        for p in promoted]

        cur.execute("""
            SELECT event_id, source_platform, raw_payload,
                   dedup_key, campaign_id, received_at
            FROM lz_raw_events
            WHERE processing_status = 'done'
            ORDER BY received_at DESC
            LIMIT %s
        """, (BATCH_SIZE,))

        all_rows = cur.fetchall()
        # Filter out already promoted
        rows = [r for r in all_rows
                if str(r["event_id"]) not in promoted_ids]
        cur.close(); conn.close()
        state["raw_events"] = [dict(r) for r in rows]
        print(f"[agent2/fetch] Batch: {len(state['raw_events'])} new events to process")
        return state

    rows = cur.fetchall()
    cur.close(); conn.close()
    state["raw_events"] = [dict(r) for r in rows]
    print(f"[agent2/fetch] Got {len(state['raw_events'])} events")
    return state
