import os, uuid, requests
import psycopg2
from datetime import datetime, timedelta, timezone
from agent4.state import Agent4State

def create_meeting_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state
    if state.get("call_situation") != "send_teams":
        return state

    existing_url = (state.get("sequence") or {}).get("teams_meeting_url")
    if existing_url:
        state["teams_meeting_url"] = existing_url
        return state

    contact  = state["contact"]
    campaign = state["campaign"]
    name     = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
    subject  = f"BITS Global Consulting — {campaign.get('campaign_name','Meeting')} with {name}"
    start_dt = datetime.now(timezone.utc) + timedelta(days=1)
    end_dt   = start_dt + timedelta(hours=1)

    try:
        from agent3.graph_auth import get_access_token
        token   = get_access_token(state["campaign_id"])
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "subject":       subject,
            "startDateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime":   end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/me/onlineMeetings",
            headers=headers, json=payload, timeout=15
        )
        if resp.status_code in (200, 201):
            data       = resp.json()
            join_url   = data.get("joinUrl") or data.get("joinWebUrl", "")
            meeting_id = data.get("id", str(uuid.uuid4()))
            conn = psycopg2.connect(os.getenv("DATABASE_URL"))
            cur  = conn.cursor()
            sequence_id = (state.get("sequence") or {}).get("sequence_id")
            cur.execute("""
                INSERT INTO crm.crm_teams_meetings
                    (meeting_id, sequence_id, contact_id, campaign_id,
                     teams_meeting_id, join_url, subject, scheduled_at, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT DO NOTHING
            """, (str(uuid.uuid4()), sequence_id, state["contact_id"],
                  state["campaign_id"], meeting_id, join_url, subject, start_dt))
            if sequence_id:
                cur.execute("""
                    UPDATE crm.crm_follow_up_sequences
                    SET teams_meeting_url=%s, status='call_scheduled', updated_at=NOW()
                    WHERE sequence_id=%s
                """, (join_url, sequence_id))
            conn.commit(); cur.close(); conn.close()
            state["teams_meeting_url"] = join_url
            print(f"[agent4/meeting] ✓ Teams meeting created")
        else:
            print(f"[agent4/meeting] Graph error {resp.status_code}")
            fallback = os.getenv("DEFAULT_MEETING_LINK", "")
            if fallback:
                state["teams_meeting_url"] = fallback
    except Exception as e:
        print(f"[agent4/meeting] Error: {e}")
        fallback = os.getenv("DEFAULT_MEETING_LINK", "")
        if fallback:
            state["teams_meeting_url"] = fallback
    return state
