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

    situation = state.get("call_situation", state["intent_label"])
    sequence  = state.get("sequence")
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now  = datetime.now(timezone.utc)

    # ── Determine new sequence status + next follow-up ───────────────────────
    current_step       = (sequence or {}).get("current_step", 0)
    asked_availability = (sequence or {}).get("asked_availability", False)

    if situation == "unsubscribe":
        new_status         = "unsubscribed"
        next_followup      = None
        new_asked_avail    = False

    elif situation == "send_teams":
        # Teams meeting link sent — call is being scheduled, stop follow-ups
        new_status         = "call_scheduled"
        next_followup      = None
        new_asked_avail    = True  # keep True

    elif situation == "ask_availability":
        # Asked for availability — pause follow-ups, wait for their reply
        new_status         = "awaiting_availability"
        next_followup      = None
        new_asked_avail    = True

    elif situation == "general_reply":
        # Post-Teams-link reply — just log, no more follow-ups
        new_status         = "call_scheduled"
        next_followup      = None
        new_asked_avail    = True

    elif situation == "cold":
        if current_step >= MAX_STEPS:
            new_status     = "exhausted"
            next_followup  = None
        else:
            new_status     = "active"
            next_followup  = now + timedelta(days=FOLLOWUP_INTERVAL_DAYS)
        new_asked_avail    = False

    else:  # warm or other
        if current_step >= MAX_STEPS:
            new_status     = "exhausted"
            next_followup  = None
        else:
            new_status     = "active"
            next_followup  = now + timedelta(days=FOLLOWUP_INTERVAL_DAYS)
        new_asked_avail    = False

    new_step = current_step + 1

    if sequence:
        cur.execute("""
            UPDATE crm.crm_follow_up_sequences SET
                current_step       = %s,
                status             = %s,
                next_followup_at   = %s,
                last_reply_at      = %s,
                last_intent_label  = %s,
                asked_availability = %s,
                teams_meeting_url  = COALESCE(%s, teams_meeting_url),
                updated_at         = NOW()
            WHERE sequence_id = %s
        """, (
            new_step, new_status, next_followup, now,
            situation, new_asked_avail,
            state.get("teams_meeting_url"),
            sequence["sequence_id"]
        ))
        sequence_id = sequence["sequence_id"]
        print(f"[agent4/schedule] Updated sequence step={new_step} status={new_status} asked_avail={new_asked_avail}")
    else:
        cur.execute("""
            INSERT INTO crm.crm_follow_up_sequences
                (campaign_id, contact_id, run_id,
                 original_response_id, current_step, max_steps,
                 status, next_followup_at, last_reply_at,
                 last_intent_label, asked_availability, teams_meeting_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING sequence_id
        """, (
            state["campaign_id"], state["contact_id"], state["run_id"],
            state["response_id"], new_step, MAX_STEPS,
            new_status, next_followup, now,
            situation, new_asked_avail,
            state.get("teams_meeting_url")
        ))
        sequence_id = str(cur.fetchone()["sequence_id"])
        print(f"[agent4/schedule] Created sequence {sequence_id} status={new_status}")

    state["sequence"] = {
        "sequence_id":       sequence_id,
        "current_step":      new_step,
        "status":            new_status,
        "asked_availability": new_asked_avail,
        "teams_meeting_url": state.get("teams_meeting_url") or (sequence or {}).get("teams_meeting_url"),
    }

    # Save Teams meeting record
    if state.get("teams_meeting_url"):
        contact = state["contact"]
        cur.execute("""
            INSERT INTO crm.crm_teams_meetings
                (sequence_id, contact_id, campaign_id, join_url, subject, scheduled_at)
            VALUES (%s,%s,%s,%s,%s,NOW())
            ON CONFLICT DO NOTHING
        """, (
            sequence_id, state["contact_id"], state["campaign_id"],
            state["teams_meeting_url"],
            f"BITS Consulting Call — {contact.get('first_name','')} {contact.get('last_name','')}"
        ))

    conn.commit()
    cur.close(); conn.close()

    if next_followup:
        print(f"[agent4/schedule] Next follow-up at {next_followup.strftime('%Y-%m-%d')}")
    else:
        print(f"[agent4/schedule] No further follow-ups — status={new_status}")

    return state
