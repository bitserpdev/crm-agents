import os
import psycopg2
import psycopg2.extras
from agent.state import AgentState

def plan_node(state: AgentState) -> AgentState:
    print(f"[plan] Loading campaign: {state['campaign_id']}")
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT campaign_id, campaign_name, cron_expression,
               source_configs, is_active
        FROM lz_campaigns
        WHERE campaign_id = %s AND is_active = TRUE
    """, (state["campaign_id"],))
    campaign = cur.fetchone()
    cur.close()
    conn.close()

    if not campaign:
        state["run_status"] = "failed"
        state["errors"].append(f"Campaign {state['campaign_id']} not found or inactive")
        return state

    state["campaign_config"]  = dict(campaign)
    state["sources_pending"]  = [
        s["type"] for s in campaign["source_configs"]
    ]
    state["run_status"] = "running"
    print(f"[plan] Sources to process: {state['sources_pending']}")
    return state
