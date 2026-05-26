import os
import psycopg2, psycopg2.extras
from datetime import datetime, timezone
from agent4.state import Agent4State

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def record_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") == "skipped":
        return state

    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    sequence_id  = (state.get("sequence") or {}).get("sequence_id")
    current_step = (state.get("sequence") or {}).get("current_step", 1)
    sent         = state.get("sent", False)

    # Log the outbound reply in crm_follow_up_emails
    if sent:
        cur.execute("""
            INSERT INTO crm.crm_follow_up_emails
                (sequence_id, contact_id, campaign_id,
                 step_number, direction, subject, body,
                 intent_label, intent_score,
                 sent_at, delivery_status)
            VALUES (%s, %s, %s, %s, 'outbound', %s, %s, %s, %s, NOW(), 'sent')
        """, (
            sequence_id, state["contact_id"], state["campaign_id"],
            current_step,
            state.get("reply_subject", ""),
            state.get("reply_body", ""),
            state.get("intent_label", ""),
            state.get("intent_score", 0.0),
        ))

    # Log inbound reply in crm_follow_up_emails for thread display
    response = state.get("response", {})
    if response and sequence_id:
        cur.execute("""
            INSERT INTO crm.crm_follow_up_emails
                (sequence_id, contact_id, campaign_id,
                 step_number, direction, body,
                 intent_label, intent_score,
                 received_at, delivery_status)
            VALUES (%s, %s, %s, %s, 'inbound', %s, %s, %s, %s::timestamptz, 'received')
            ON CONFLICT DO NOTHING
        """, (
            sequence_id, state["contact_id"], state["campaign_id"],
            current_step,
            response.get("reply_body", ""),
            response.get("intent_label", ""),
            response.get("intent_score", 0.0),
            response.get("responded_at"),
        ))

    # Mark response as processed by agent4
    cur.execute("""
        UPDATE crm.crm_campaign_responses
        SET queued_for_agent4 = TRUE
        WHERE response_id = %s
    """, (state["response_id"],))

    # Activity log
    intent   = state.get("intent_label", "")
    contact  = state.get("contact", {})
    name     = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
    summary  = f"Agent4 replied to {name} (intent={intent})"
    if state.get("teams_meeting_url"):
        summary += " — Teams meeting created"

    cur.execute("""
        INSERT INTO crm.crm_activity_log
            (activity_id, contact_id, activity_type,
             activity_source, source_id, summary)
        VALUES (gen_random_uuid(), %s, 'agent4_reply',
                'agent', 'agent-4', %s)
    """, (state["contact_id"], summary))

    conn.commit()
    cur.close(); conn.close()

    state["run_status"] = "done"
    print(f"[agent4/record] ✓ Recorded — intent={intent} sent={sent}")
    return state
