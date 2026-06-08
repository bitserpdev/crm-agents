import json
import re
from datetime import datetime, timedelta, timezone

from agents.agent4.prompts import SYSTEM_PROMPT
from core.database import get_conn, get_dict_cursor
from core.llm import get_llm, LLMFormat
from services.email import EmailMessage, email_service

llm = get_llm(LLMFormat.TEXT)


def _get_open_status(contact_id: str, campaign_id: str, cur) -> str:
    cur.execute(
        """
        SELECT r.opened_at
        FROM crm.crm_campaign_recipients r
        JOIN crm.crm_campaign_runs rn ON rn.run_id = r.run_id
        WHERE r.contact_id = %s AND rn.campaign_id = %s
        ORDER BY r.sent_at DESC LIMIT 1
        """,
        (contact_id, campaign_id),
    )
    row = cur.fetchone()
    if not row:
        return "no_open"
    return "opened_no_reply" if row["opened_at"] else "no_open"


def _generate_followup(
    contact: dict, campaign: dict, situation: str, prev_subject: str, step: int
) -> dict:
    name    = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
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
        text = re.sub(r"```json\s*|\s*```", "", resp.content.strip()).strip()
        return json.loads(text)
    except Exception as e:
        print(f"[followup_sender] LLM error: {e}")
        return {
            "subject": f"Following up — {prev_subject}",
            "body": (
                f"Hi {name},\n\nJust wanted to follow up on my previous email about how "
                f"BITS Global Consulting can support {company or 'your team'}.\n\n"
                f"Would you have 20 minutes for a quick call this week?\n\n"
                f"Best regards,\nBITS Global Consulting Team"
            ),
        }


def _build_html(body: str) -> str:
    return (
        '<html><body style="font-family:Arial,sans-serif;font-size:14px;'
        'color:#333;max-width:600px;margin:0 auto;padding:20px;">'
        f"<p>{body.replace(chr(10), '<br>')}</p>"
        '<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">'
        '<p style="font-size:12px;color:#999;">BITS Global Consulting | erp@bitsglobalconsulting.com</p>'
        "</body></html>"
    )


def send_due_followups():
    conn = get_conn()
    cur  = get_dict_cursor(conn)
    now  = datetime.now(timezone.utc)

    cur.execute(
        """
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
        """,
        (now,),
    )

    due = cur.fetchall()
    print(f"[followup_sender] {len(due)} sequences due for follow-up")

    for seq in due:
        try:
            campaign = {
                "service_description": seq["service_description"],
                "campaign_name":       seq["campaign_name"],
            }

            situation = (
                "warm_followup"
                if seq["last_reply_at"] is not None
                else _get_open_status(seq["contact_id"], seq["campaign_id"], cur)
            )

            step         = seq["current_step"] + 1
            prev_subject = seq["original_subject"] or "our previous email"

            result  = _generate_followup(seq, campaign, situation, prev_subject, step)
            subject = result["subject"]
            body    = result["body"]

            success = email_service.send(
                EmailMessage(
                    to=seq["email"],
                    subject=subject,
                    body_text=body,
                    body_html=_build_html(body),
                )
            )
            if not success:
                print(f"[followup_sender] Failed to send to {seq['email']}")
                continue

            new_status    = "exhausted" if step >= seq["max_steps"] else "active"
            next_followup = None if new_status == "exhausted" else now + timedelta(days=3)

            cur.execute(
                """
                INSERT INTO crm.crm_follow_up_emails
                    (sequence_id, contact_id, campaign_id,
                     step_number, direction, subject, body,
                     sent_at, delivery_status)
                VALUES (%s, %s, %s, %s, 'outbound', %s, %s, NOW(), 'sent')
                """,
                (seq["sequence_id"], seq["contact_id"], seq["campaign_id"],
                 step, subject, body),
            )

            cur.execute(
                """
                UPDATE crm.crm_follow_up_sequences
                SET current_step     = %s,
                    status           = %s,
                    next_followup_at = %s,
                    updated_at       = NOW()
                WHERE sequence_id = %s
                """,
                (step, new_status, next_followup, seq["sequence_id"]),
            )

            conn.commit()
            print(f"[followup_sender] ✓ FU{step} sent to {seq['email']} ({situation}) status={new_status}")

        except Exception as e:
            print(f"[followup_sender] Error for {seq.get('email')}: {e}")
            conn.rollback()

    cur.close()
    conn.close()