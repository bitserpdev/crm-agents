import os
import uuid
from datetime import datetime, timedelta, timezone

from core.database import get_conn
from agents.agent4.state import Agent4State
from utils.zoom_meeting import create_zoom_meeting
from utils.email_reply import has_proposed_meeting_time, strip_quoted_reply


def create_meeting_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state
    if state.get("call_situation") != "send_zoom":
        return state

    reply_body = strip_quoted_reply(
        (state.get("response") or {}).get("reply_body", "")
    )
    if not has_proposed_meeting_time(reply_body):
        print("[agent4/meeting] Skipped — reply has no confirmed date/time")
        return state

    # Reuse existing URL if already scheduled
    sequence = state.get("sequence") or {}
    existing_url = sequence.get("teams_meeting_url") or sequence.get("zoom_meeting_url")
    if existing_url:
        state["teams_meeting_url"] = existing_url
        return state

    contact = state["contact"]
    campaign = state["campaign"]
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    title = f"BITS Global Consulting — {campaign.get('campaign_name', 'Meeting')} with {name}"
    start_dt = datetime.now(timezone.utc) + timedelta(days=1)

    try:
        meeting = create_zoom_meeting(
            title=title,
            start_time=start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            duration_minutes=60,
        )

        join_url = meeting["join_url"]
        meeting_id = meeting["meeting_id"]

        sequence_id = (state.get("sequence") or {}).get("sequence_id")

        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO crm.crm_teams_meetings
                (meeting_id, sequence_id, contact_id, campaign_id,
                 teams_meeting_id, join_url, subject, scheduled_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
            """,
            (
                str(uuid.uuid4()),
                sequence_id,
                state["contact_id"],
                state["campaign_id"],
                meeting_id,
                join_url,
                title,
                start_dt,
            ),
        )

        if sequence_id:
            cur.execute(
                """
                UPDATE crm.crm_follow_up_sequences
                SET teams_meeting_url = %s, status = 'call_scheduled', updated_at = NOW()
                WHERE sequence_id = %s
                """,
                (join_url, sequence_id),
            )

        conn.commit()
        cur.close()
        conn.close()

        state["teams_meeting_url"] = join_url
        print(f"[agent4/meeting] ✓ Zoom meeting created: {meeting_id}")

    except Exception as e:
        print(f"[agent4/meeting] Error: {e}")
        fallback = os.getenv("DEFAULT_MEETING_LINK", "")
        if fallback:
            state["teams_meeting_url"] = fallback

    return state
