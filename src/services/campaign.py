import uuid
from core.database import get_conn, release_conn, get_dict_cursor
from core.logger import logger
from utils.uuid import new_id, new_trace_id


def run_campaign(campaign_id: str):
    logger.info("[campaign] Starting", campaign_id=campaign_id)
    try:
        from agent.graph import build_graph
        graph = build_graph()
        graph.invoke({
            "campaign_id":       campaign_id,
            "campaign_config":   {},
            "sources_pending":   [],
            "current_source":    None,
            "raw_records":       [],
            "validated_records": [],
            "errors":            [],
            "agent_trace_id":    new_trace_id(),
            "run_status":        "running",
        })
        _update_last_run(campaign_id)
        logger.info("[campaign] Complete", campaign_id=campaign_id)
    except Exception as e:
        logger.error("[campaign] Failed", campaign_id=campaign_id, error=str(e))
        raise


def run_agent2_batch():
    logger.info("[campaign] Agent 2 batch starting")
    try:
        from agent2.graph import build_agent2_graph
        result = build_agent2_graph().invoke({
            "trigger_type":      "batch",
            "raw_events":        [],
            "extracted_records": [],
            "enriched_records":  [],
            "loaded_records":    [],
            "errors":            [],
            "agent_trace_id":    new_trace_id(),
            "run_status":        "running",
            "stats":             {},
        })
        logger.info("[campaign] Agent 2 batch done", stats=result.get("stats"))
    except Exception as e:
        logger.error("[campaign] Agent 2 batch error", error=str(e))
        raise


def run_agent2_realtime():
    logger.info("[campaign] Agent 2 realtime starting")
    try:
        from agent2.graph import build_agent2_graph
        build_agent2_graph().invoke({
            "trigger_type":      "realtime",
            "raw_events":        [],
            "extracted_records": [],
            "enriched_records":  [],
            "loaded_records":    [],
            "errors":            [],
            "agent_trace_id":    new_trace_id(),
            "run_status":        "running",
            "stats":             {},
        })
        logger.info("[campaign] Agent 2 realtime done")
    except Exception as e:
        logger.error("[campaign] Agent 2 realtime error", error=str(e))
        raise


# ── DB helpers ────────────────────────────────────────────────────────────────

def _update_last_run(campaign_id: str):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE lz_campaigns
            SET last_run_at = NOW(), updated_at = NOW()
            WHERE campaign_id = %s
        """, (campaign_id,))
        conn.commit()
    finally:
        cur.close()
        release_conn(conn)


def load_all_campaigns() -> list:
    conn = get_conn()
    cur  = get_dict_cursor(conn)
    try:
        cur.execute("""
            SELECT campaign_id, campaign_name, cron_expression
            FROM lz_campaigns
            WHERE is_active = TRUE
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close()
        release_conn(conn)