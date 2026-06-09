from agents.agent4.state import Agent4State
from services.email import EmailMessage, email_service
from utils.email_format import format_context_from_contact, format_email_body


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
    sequence = state.get("sequence") or {}
    zoom_url = (
        state.get("teams_meeting_url")
        or sequence.get("zoom_meeting_url")
        or sequence.get("teams_meeting_url")
        or ""
    )

    if "[ZOOM_LINK]" in body:
        body = body.replace("[ZOOM_LINK]", zoom_url)
    elif state.get("call_situation") == "send_zoom" and zoom_url and zoom_url not in body:
        body = f"{body.rstrip()}\n\nJoin the call here:\n{zoom_url}\n"

    if state.get("call_situation") == "send_zoom" and not zoom_url:
        print("[agent4/send] Warning — send_zoom but no Zoom URL available")

    ctx = format_context_from_contact(state.get("contact", {}))
    body_text, body_html = format_email_body(body, ctx)
    state["reply_body"] = body_text

    success = email_service.send(
        EmailMessage(
            to=to_email,
            subject=state.get("reply_subject", "Following up"),
            body_text=body_text,
            body_html=body_html,
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
