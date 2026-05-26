import os, smtplib, requests
import psycopg2, psycopg2.extras
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from agent4.state import Agent4State
from agent3.graph_auth import get_access_token

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def _create_teams_meeting(token: str, contact: dict, subject: str) -> str:
    """Create a Teams meeting via Microsoft Graph and return join URL."""
    try:
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/me/onlineMeetings",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={
                "subject": subject,
                "lobbyBypassSettings": {"scope": "everyone"},
            },
            timeout=15
        )
        if resp.status_code in (200, 201):
            return resp.json().get("joinWebUrl", "")
        else:
            print(f"[agent4/send] Teams meeting error: {resp.status_code} {resp.text}")
            return ""
    except Exception as e:
        print(f"[agent4/send] Teams meeting exception: {e}")
        return ""

def _send_smtp(to: str, subject: str, body: str) -> bool:
    """Send email via SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = os.getenv("SMTP_USER")
        msg["To"]      = to

        html = body.replace("\n", "<br>")
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(f"<html><body>{html}</body></html>", "html"))

        with smtplib.SMTP(os.getenv("SMTP_HOST"),
                          int(os.getenv("SMTP_PORT", 587))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
            server.sendmail(os.getenv("SMTP_USER"), to, msg.as_string())
        return True
    except Exception as e:
        print(f"[agent4/send] SMTP error: {e}")
        return False

def send_reply_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    contact   = state["contact"]
    situation = state.get("call_situation", state["intent_label"])
    to_email  = contact.get("email", "")

    if not to_email or "@placeholder.bits" in to_email:
        print(f"[agent4/send] Skipping placeholder email: {to_email}")
        state["sent"]       = False
        state["run_status"] = "skipped"
        return state

    # Suppress contact if unsubscribe
    if situation == "unsubscribe":
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE crm.crm_contacts SET is_suppressed = TRUE
            WHERE contact_id = %s
        """, (state["contact_id"],))
        conn.commit()
        cur.close(); conn.close()
        print(f"[agent4/send] Contact {to_email} suppressed (unsubscribe)")

    # ── Create Teams meeting ONLY when we have availability confirmed ────────
    teams_url = ""
    if situation == "send_teams":
        try:
            token = get_access_token(state["campaign_id"])
            teams_url = _create_teams_meeting(
                token, contact,
                f"BITS Consulting Call — {contact.get('first_name','')} {contact.get('last_name','')}"
            )
            if teams_url:
                state["teams_meeting_url"] = teams_url
                print(f"[agent4/send] ✓ Teams meeting created: {teams_url}")
            else:
                print(f"[agent4/send] Teams meeting creation failed — sending without link")
        except Exception as e:
            print(f"[agent4/send] Could not create Teams meeting: {e}")

    # Replace [TEAMS_LINK] placeholder in body
    body = state.get("reply_body", "")
    if teams_url:
        body = body.replace("[TEAMS_LINK]", teams_url)
    elif "[TEAMS_LINK]" in body:
        body = body.replace("[TEAMS_LINK]", "I'll send you a calendar invite shortly.")
    state["reply_body"] = body

    # Send the email
    success = _send_smtp(to_email, state["reply_subject"], body)

    if success:
        print(f"[agent4/send] ✓ Reply sent to {to_email} (situation={situation})")
        state["sent"] = True
    else:
        state["sent"] = False
        state["errors"].append(f"Failed to send email to {to_email}")
        state["run_status"] = "failed"

    return state
