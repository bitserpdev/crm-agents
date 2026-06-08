from datetime import datetime, timedelta, timezone

from core.database import get_conn, get_dict_cursor
from agent4.state import Agent4State

FOLLOWUP_INTERVAL_DAYS = 3
MAX_STEPS = 5


def schedule_followups_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    situation = state.get("call_situation", state["intent_label"])
    sequence  = state.get("sequence")
    now       = datetime.now(timezone.utc)

    current_step       = (sequence or {}).get("current_step", 0)
    asked_availability = (sequence or {}).get("asked_availability", False)

    # Determine new sequence status + next follow-up
    if situation == "unsubscribe":
        new_status      = "unsubscribed"
        next_followup   = None
        new_asked_avail = False

    elif situation == "send_zoom":
        new_status      = "call_scheduled"
        next_followup   = None
        new_asked_avail = True

    elif situation == "ask_availability":
        new_status      = "awaiting_availability"
        next_followup   = None
        new_asked_avail = True

    elif situation == "general_reply":
        new_status      = "call_scheduled"
        next_followup   = None
        new_asked_avail = True

    else:  # cold, warm, or other
        if current_step >= MAX_STEPS:
            new_status    = "exhausted"
            next_followup = None
        else:
            new_status    = "active"
            next_followup = now + timedelta(days=FOLLOWUP_INTERVAL_DAYS)
        new_asked_avail = False

    new_step     = current_step + 1
    zoom_meeting = state.get("teams_meeting_url")  # rename to zoom_meeting_url once state schema updated

    conn = get_conn()
    cur  = get_dict_cursor(conn)

    if sequence:
        cur.execute(
            """
            UPDATE crm.crm_follow_up_sequences SET
                current_step       = %s,
                status             = %s,
                next_followup_at   = %s,
                last_reply_at      = %s,
                last_intent_label  = %s,
                asked_availability = %s,
                zoom_meeting_url   = COALESCE(%s, zoom_meeting_url),
                updated_at         = NOW()
            WHERE sequence_id = %s
            """,
            (
                new_step, new_status, next_followup, now,
                situation, new_asked_avail,
                zoom_meeting,
                sequence["sequence_id"],
            ),
        )
        sequence_id = sequence["sequence_id"]
        print(f"[agent4/schedule] Updated sequence step={new_step} status={new_status} asked_avail={new_asked_avail}")

    else:
        cur.execute(
            """
            INSERT INTO crm.crm_follow_up_sequences
                (campaign_id, contact_id, run_id,
                 original_response_id, current_step, max_steps,
                 status, next_followup_at, last_reply_at,
                 last_intent_label, asked_availability, zoom_meeting_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING sequence_id
            """,
            (
                state["campaign_id"], state["contact_id"], state["run_id"],
                state["response_id"], new_step, MAX_STEPS,
                new_status, next_followup, now,
                situation, new_asked_avail,
                zoom_meeting,
            ),
        )
        sequence_id = str(cur.fetchone()["sequence_id"])
        print(f"[agent4/schedule] Created sequence {sequence_id} status={new_status}")

    state["sequence"] = {
        "sequence_id":        sequence_id,
        "current_step":       new_step,
        "status":             new_status,
        "asked_availability": new_asked_avail,
        "zoom_meeting_url":   zoom_meeting or (sequence or {}).get("zoom_meeting_url"),
    }

    # Save Zoom meeting record
    if zoom_meeting:
        contact = state["contact"]
        cur.execute(
            """
            INSERT INTO crm.crm_zoom_meetings
                (sequence_id, contact_id, campaign_id, join_url, subject, scheduled_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
            """,
            (
                sequence_id, state["contact_id"], state["campaign_id"],
                zoom_meeting,
                f"BITS Consulting Call — {contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
            ),
        )

    conn.commit()
    cur.close()
    conn.close()

    if next_followup:
        print(f"[agent4/schedule] Next follow-up at {next_followup.strftime('%Y-%m-%d')}")
    else:
        print(f"[agent4/schedule] No further follow-ups — status={new_status}")

    return state