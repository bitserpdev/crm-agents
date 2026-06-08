import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from agent4.state import Agent4State

def send_email_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state
    if not state.get("reply_body"):
        print("[agent4/send] No reply body — skipping")
        state["sent"] = False
        return state

    contact  = state["contact"]
    to_email = contact.get("email", "")

    if not to_email or "placeholder" in to_email.lower():
        print(f"[agent4/send] Invalid email — skipping")
        state["sent"] = False
        return state

    body = state.get("reply_body", "")
    if "[TEAMS_LINK]" in body:
        meeting_url = state.get("teams_meeting_url") or \
                      (state.get("sequence") or {}).get("teams_meeting_url") or \
                      os.getenv("DEFAULT_MEETING_LINK", "https://teams.microsoft.com/meet")
        body = body.replace("[TEAMS_LINK]", meeting_url)
        state["reply_body"] = body

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = state.get("reply_subject", "Following up")
        msg["From"]    = os.getenv("SMTP_USER")
        msg["To"]      = to_email
        msg.attach(MIMEText(body, "plain"))
        html_body = body.replace("\n", "<br>")
        html = f"""<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:600px;margin:0 auto;padding:20px;">
<p>{html_body}</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
<p style="font-size:12px;color:#999;">BITS Global Consulting | erp@bitsglobalconsulting.com</p>
</body></html>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
            server.sendmail(os.getenv("SMTP_USER"), to_email, msg.as_string())
        state["sent"] = True
        print(f"[agent4/send] ✓ Sent to {to_email}")
    except Exception as e:
        print(f"[agent4/send] Failed: {e}")
        state["sent"]       = False
        state["run_status"] = "failed"
        state["errors"].append(str(e))
    return state
