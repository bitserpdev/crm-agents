from core.database import get_conn
from agent4.state import Agent4State
from services.email import EmailMessage, email_service


def _build_html(body: str) -> str:
    return (
        '<html><body style="font-family:Arial,sans-serif;font-size:14px;'
        'color:#333;max-width:600px;margin:0 auto;padding:20px;">'
        f"<p>{body.replace(chr(10), '<br>')}</p>"
        '<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">'
        '<p style="font-size:12px;color:#999;">BITS Global Consulting | erp@bitsglobalconsulting.com</p>'
        "</body></html>"
    )


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

    # Suppress contact on unsubscribe
    if situation == "unsubscribe":
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "UPDATE crm.crm_contacts SET is_suppressed = TRUE WHERE contact_id = %s",
            (state["contact_id"],),
        )
        conn.commit()
        cur.close()
        conn.close()
        print(f"[agent4/send] Contact {to_email} suppressed (unsubscribe)")

    # Resolve [ZOOM_LINK] placeholder — meeting already created by create_meeting_node
    body = state.get("reply_body", "")
    if "[ZOOM_LINK]" in body:
        zoom_url = (
            state.get("teams_meeting_url")
            or (state.get("sequence") or {}).get("zoom_meeting_url")
            or ""
        )
        body = body.replace("[ZOOM_LINK]", zoom_url if zoom_url else "I'll send you a calendar invite shortly.")
        state["reply_body"] = body

    success = email_service.send(
        EmailMessage(
            to=to_email,
            subject=state.get("reply_subject", "Following up"),
            body_text=body,
            body_html=_build_html(body),
        )
    )

    if success:
        state["sent"] = True
        print(f"[agent4/send] ✓ Reply sent to {to_email} (situation={situation})")
    else:
        state["sent"]       = False
        state["run_status"] = "failed"
        state["errors"].append(f"Failed to send email to {to_email}")

    return state