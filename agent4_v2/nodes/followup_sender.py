import os, json, smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import psycopg2, psycopg2.extras
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="llama3.2",
    base_url="http://localhost:11434",
    temperature=0.3,
    timeout=60,
    num_predict=400,
)

SYSTEM_PROMPT = """You are a professional B2B sales representative at BITS Global Consulting.
Write a short follow-up email based on the situation.

Situations:
- no_open: Contact never opened the email. Subject line: make it compelling. Body: brief, curious, not pushy. 
- opened_no_reply: Contact opened but didn't reply. Acknowledge subtly, add new value, ask one question.
- warm_followup: Contact replied warmly before but went quiet. Reference previous conversation, nudge gently.

Rules:
- Under 100 words
- Professional, human, not salesy
- One clear call to action
- Sign off: BITS Global Consulting Team

Return ONLY valid JSON:
{
  "subject": "subject line here",
  "body": "email body here"
}"""

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def _send_smtp(to: str, subject: str, body: str) -> bool:
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
        print(f"[followup_sender] SMTP error: {e}")
        return False

def _get_open_status(contact_id: str, campaign_id: str, cur) -> str:
    """Check if contact opened the initial email."""
    cur.execute("""
        SELECT r.opened_at
        FROM crm.crm_campaign_recipients r
        JOIN crm.crm_campaign_runs rn ON rn.run_id = r.run_id
        WHERE r.contact_id = %s AND rn.campaign_id = %s
        ORDER BY r.sent_at DESC LIMIT 1
    """, (contact_id, campaign_id))
    row = cur.fetchone()
    if not row:
        return "no_open"
    return "opened_no_reply" if row["opened_at"] else "no_open"

def _generate_followup(contact: dict, campaign: dict, situation: str,
                        prev_subject: str, step: int) -> dict:
    """Generate follow-up email using LLM."""
    name    = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
    company = contact.get("company_name", "")
    service = campaign.get("service_description", "our services")

    ctx = f"""
Contact: {name} at {company}
Service: {service}
Situation: {situation}
Follow-up number: {step}
Original email subject: {prev_subject}
"""
    try:
        resp = llm.invoke([("system", SYSTEM_PROMPT), ("human", ctx)])
        text = resp.content.strip()
        import re
        text = re.sub(r"```json\s*|\s*```", "", text).strip()
        return json.loads(text)
    except Exception as e:
        print(f"[followup_sender] LLM error: {e}")
        return {
            "subject": f"Following up — {prev_subject}",
            "body": f"""Hi {name},

Just wanted to follow up on my previous email about how BITS Global Consulting can support {company or 'your team'}.

Would you have 20 minutes for a quick call this week?

Best regards,
BITS Global Consulting Team"""
        }

def send_due_followups():
    """Called by scheduler — find all sequences due for follow-up and send."""
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    now  = datetime.now(timezone.utc)

    # Find sequences due for follow-up
    cur.execute("""
        SELECT s.*, c.first_name, c.last_name, c.email, c.job_title,
               co.company_name, co.industry,
               camp.campaign_name, camp.service_description, camp.from_address,
               (SELECT em.subject FROM crm.crm_email_messages em
                JOIN crm.crm_email_threads et ON et.thread_id = em.thread_id
                WHERE et.contact_id = s.contact_id
                ORDER BY em.sent_at ASC LIMIT 1) AS original_subject
        FROM crm.crm_follow_up_sequences s
        JOIN crm.crm_contacts c ON c.contact_id = s.contact_id
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        LEFT JOIN crm.crm_campaigns camp ON camp.campaign_id = s.campaign_id
        WHERE s.status = 'active'
          AND s.next_followup_at <= %s
          AND c.is_suppressed = FALSE
          AND c.email NOT LIKE '%%@placeholder.bits'
    """, (now,))

    due = cur.fetchall()
    print(f"[followup_sender] {len(due)} sequences due for follow-up")

    for seq in due:
        try:
            contact  = dict(seq)
            campaign = {
                "service_description": seq["service_description"],
                "campaign_name":       seq["campaign_name"],
            }

            # Determine situation based on open status
            has_replied = seq["last_reply_at"] is not None
            if has_replied:
                situation = "warm_followup"
            else:
                situation = _get_open_status(seq["contact_id"], seq["campaign_id"], cur)

            step = seq["current_step"] + 1
            prev_subject = seq["original_subject"] or "our previous email"

            # Generate follow-up email
            result = _generate_followup(contact, campaign, situation, prev_subject, step)
            subject = result["subject"]
            body    = result["body"]

            # Send
            success = _send_smtp(seq["email"], subject, body)
            if not success:
                print(f"[followup_sender] Failed to send to {seq['email']}")
                continue

            # Log in crm_follow_up_emails
            cur.execute("""
                INSERT INTO crm.crm_follow_up_emails
                    (sequence_id, contact_id, campaign_id,
                     step_number, direction, subject, body,
                     sent_at, delivery_status)
                VALUES (%s,%s,%s,%s,'outbound',%s,%s,NOW(),'sent')
            """, (
                seq["sequence_id"], seq["contact_id"], seq["campaign_id"],
                step, subject, body
            ))

            # Update sequence
            new_step = step
            if new_step >= seq["max_steps"]:
                new_status    = "exhausted"
                next_followup = None
            else:
                new_status    = "active"
                from datetime import timedelta
                next_followup = now + timedelta(days=3)

            cur.execute("""
                UPDATE crm.crm_follow_up_sequences SET
                    current_step     = %s,
                    status           = %s,
                    next_followup_at = %s,
                    updated_at       = NOW()
                WHERE sequence_id = %s
            """, (new_step, new_status, next_followup, seq["sequence_id"]))

            conn.commit()
            print(f"[followup_sender] ✓ FU{step} sent to {seq['email']} ({situation}) status={new_status}")

        except Exception as e:
            print(f"[followup_sender] Error for {seq.get('email')}: {e}")
            conn.rollback()

    cur.close()
    conn.close()
