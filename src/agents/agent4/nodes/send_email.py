from agents.agent4.state import Agent4State
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


def send_email_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    if not state.get("reply_body"):
        print("[agent4/send] No reply body — skipping")
        state["sent"] = False
        return state

    to_email = state["contact"].get("email", "")
    if not to_email or "placeholder" in to_email.lower():
        print("[agent4/send] Invalid email — skipping")
        state["sent"] = False
        return state

    body = state.get("reply_body", "")

    # Resolve [ZOOM_LINK] placeholder before sending
    if "[ZOOM_LINK]" in body:
        zoom_url = (
            state.get("teams_meeting_url")
            or (state.get("sequence") or {}).get("zoom_meeting_url")
            or ""
        )
        body = body.replace("[ZOOM_LINK]", zoom_url)
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
        print(f"[agent4/send] ✓ Sent to {to_email}")
    else:
        state["sent"] = False
        state["run_status"] = "failed"
        state["errors"].append(f"email_service failed to send to {to_email}")

    return state
