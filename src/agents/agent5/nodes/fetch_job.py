import os
import psycopg2
import psycopg2.extras
from config.logger import get_logger
from agents.agent5.state import Agent5State

logger = get_logger("fetch_job")

def fetch_job_node(state: Agent5State) -> Agent5State:

    event_id = state.get("event_id")
    logger.info(f"Starting fetch_job_node for event_id: {event_id}")

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    logger.debug(f"Querying lz_raw_events for event_id: {event_id}")

    cur.execute(
        """
        SELECT event_id, raw_payload
        FROM lz_raw_events
        WHERE event_id = %s AND source_platform = 'upwork'
    """,
        (state["event_id"],),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        state["errors"].append(f"Event {state['event_id']} not found")
        state["run_status"] = "failed"
        return state

    logger.info(f"Found job: {row['event_id']}")
    logger.debug(f"raw_payload keys: {list(row['raw_payload'].keys())}")

    payload = row["raw_payload"]
    state["raw_payload"] = payload
    state["title"] = payload.get("title", "")
    state["description"] = payload.get("description", "")
    state["url"] = payload.get("url", "")
    state["budget"] = payload.get("budget", {})
    state["skills"] = payload.get("skills", [])
    state["client"] = payload.get("client", {})
    logger.info(f"Job details initialized for event_id: {event_id}")
    state["run_status"] = "running"

    return state
