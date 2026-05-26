import os
from datetime import datetime, timedelta, timezone
import psycopg2, psycopg2.extras
from agent4.state import Agent4State

FOLLOWUP_INTERVAL_DAYS = 3
MAX_STEPS = 5

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def schedule_followups_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    intent   = state["intent_label"]
    sequence = state.get("sequence")

    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    now = datetime.now(timezone.utc)

    # Determine new sequence status based on intent
    if intent == "unsubscribe":
        new_status = "unsubscribed"
        next_followup = None
    elif intent in ("hot", "call_requested"):
        new_status = "call_scheduled"
        next_followup = None  # no more follow-ups needed
    elif intent == "cold":
        # one more follow-up then pause
        current_step = (sequence or {}).get("current_step", 0)
        if current_step >= MAX_STEPS:
            new_status = "exhausted"
            next_followup = None
        else:
            new_status = "active"
            next_followup = now + timedelta(days=FOLLOWUP_INTERVAL_DAYS)
    else:  # warm
        current_step = (sequence or {}).get("current_step", 0)
        if current_step >= MAX_STEPS:
            new_status = "exhausted"
            next_followup = None
        else:
            new_status = "active"
            next_followup = now + timedelta(days=FOLLOWUP_INTERVAL_DAYS)

    if sequence:
        # Update existing sequence
        current_step = sequence.get("current_step", 0) + 1
        cur.execute("""
            UPDATE crm.crm_follow_up_sequences SET
                current_step      = %s,
                status            = %s,
                next_followup_at  = %s,
                last_reply_at     = %s,
                last_intent_label = %s,
                teams_meeting_url = COALESCE(%s, teams_meeting_url),
                updated_at        = NOW()
            WHERE sequence_id = %s
        """, (
            current_step, new_status, next_followup, now,
            intent, state.get("teams_meeting_url"),
            sequence["sequence_id"]
        ))
        sequence_id = sequence["sequence_id"]
        print(f"[agent4/schedule] Updated sequence step={current_step} status={new_status}")
    else:
        # Create new sequence
        current_step = 1
        cur.execute("""
            INSERT INTO crm.crm_follow_up_sequences
                (campaign_id, contact_id, run_id,
                 original_response_id, current_step,
                 max_steps, status, next_followup_at,
                 last_reply_at, last_intent_label, teams_meeting_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING sequence_id
        """, (
            state["campaign_id"], state["contact_id"], state["run_id"],
            state["response_id"], current_step,
            MAX_STEPS, new_status, next_followup,
            now, intent, state.get("teams_meeting_url")
        ))
        sequence_id = str(cur.fetchone()["sequence_id"])
        print(f"[agent4/schedule] Created new sequence {sequence_id} status={new_status}")

    state["sequence"] = {"sequence_id": sequence_id,
                         "current_step": current_step,
                         "status": new_status}

    # Save Teams meeting record if created
    if state.get("teams_meeting_url"):
        cur.execute("""
            INSERT INTO crm.crm_teams_meetings
                (sequence_id, contact_id, campaign_id,
                 join_url, subject, scheduled_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
        """, (
            sequence_id, state["contact_id"], state["campaign_id"],
            state["teams_meeting_url"],
            f"BITS Consulting Call — {state['contact'].get('first_name','')} {state['contact'].get('last_name','')}"
        ))

    conn.commit()
    cur.close(); conn.close()

    if next_followup:
        print(f"[agent4/schedule] Next follow-up at {next_followup.strftime('%Y-%m-%d')}")
    else:
        print(f"[agent4/schedule] No further follow-ups — status={new_status}")

    return state
