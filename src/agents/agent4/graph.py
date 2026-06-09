import os
import json
from langgraph.graph import StateGraph, END
from agents.agent4.state import Agent4State
from agents.agent4.nodes.load_thread import load_thread_node
from agents.agent4.nodes.generate_response import generate_response_node
from agents.agent4.nodes.create_meeting import create_meeting_node
from agents.agent4.nodes.send_email import send_email_node
from agents.agent4.nodes.schedule_followups import schedule_followups_node
from agents.agent4.nodes.record import record_node
from core.redis import get_redis

r = get_redis()


def build_agent4_graph():
    g = StateGraph(Agent4State)
    g.add_node("load_thread", load_thread_node)
    g.add_node("generate_response", generate_response_node)
    g.add_node("create_meeting", create_meeting_node)
    g.add_node("send_email", send_email_node)
    g.add_node("schedule_followups", schedule_followups_node)
    g.add_node("record", record_node)
    g.set_entry_point("load_thread")
    g.add_edge("load_thread", "generate_response")
    g.add_edge("generate_response", "create_meeting")
    g.add_edge("create_meeting", "send_email")
    g.add_edge("send_email", "schedule_followups")
    g.add_edge("schedule_followups", "record")
    g.add_edge("record", END)
    return g.compile()


def run_agent4():
    """Entry point for scheduler – creates initial state and runs the graph once."""

    print(f"[DEBUG] Agent4 STARTED - Checking queue")
    # Get queue length
    queue_len = r.llen("op:reply_queue")
    print(f"[DEBUG] Agent4 - Queue length: {queue_len}")

    if queue_len == 0:
        return {"run_status": "skipped"}

    all_items = r.lrange("op:reply_queue", 0, -1)
    print(f"[DEBUG] Agent4 - All items: {all_items}")

    item = r.lpop("op:reply_queue")
    print(f"[DEBUG] Agent4 - Popped item: {item}")

    print(f"[DEBUG] Item type: {type(item)}")
    print(f"[DEBUG] Item value: {item}")

    if not item:
        print(f"[DEBUG] Agent4 - Item was None")
        return {"run_status": "skipped"}


    try:
        data = json.loads(item)
    except json.JSONDecodeError:
        print(f"[agent4] Invalid JSON in queue, removing corrupted item")
        r.lpop("op:reply_queue")
        return {"run_status": "skipped"}

    # Validate required fields
    required_fields = ["response_id", "contact_id", "campaign_id"]
    missing_fields = [f for f in required_fields if not data.get(f)]

    if missing_fields:
        print(f"[agent4] Queue item missing fields: {missing_fields}, removing item")
        print(f"[agent4] Bad item data: {data}")
        r.lpop("op:reply_queue")
        return {"run_status": "skipped"}

    # Check response exists and was not already handled by Agent 4
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from agents.agent4.processed import agent4_already_replied

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT 1 FROM crm.crm_campaign_responses WHERE response_id = %s",
        (data["response_id"],),
    )
    exists = cur.fetchone()

    if not exists:
        cur.close()
        conn.close()
        print(
            f"[agent4] Response {data['response_id']} not found in database, removing from queue"
        )
        return {"run_status": "skipped"}

    if agent4_already_replied(cur, data["response_id"]):
        cur.close()
        conn.close()
        print(f"[agent4] Response {data['response_id']} already handled — skipping")
        return {"run_status": "skipped"}

    cur.execute(
        "SELECT intent_label FROM crm.crm_campaign_responses WHERE response_id = %s",
        (data["response_id"],),
    )
    intent_row = cur.fetchone()
    if intent_row and intent_row.get("intent_label") == "out_of_office":
        cur.close()
        conn.close()
        print(f"[agent4] Skipping out-of-office response {data['response_id']}")
        return {"run_status": "skipped"}

    cur.close()
    conn.close()

    from agents.agent4.state import Agent4State

    graph = build_agent4_graph()
    initial_state = Agent4State(
        response_id=data["response_id"],  # ← USE THE DATA FROM QUEUE
        contact_id=data["contact_id"],  # ← USE THE DATA FROM QUEUE
        campaign_id=data["campaign_id"],  # ← USE THE DATA FROM QUEUE
        run_id=data.get("run_id", ""),  # ← USE THE DATA FROM QUEUE
        contact={},
        campaign={},
        response={},
        thread_history=[],
        sequence=None,
        reply_subject="",
        reply_body="",
        intent_label="",
        intent_score=0.0,
        teams_meeting_url=None,
        sent=False,
        errors=[],
        run_status="pending",
    )
    result = graph.invoke(initial_state)
    return result
