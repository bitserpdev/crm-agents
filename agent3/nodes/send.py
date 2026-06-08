from typing import List
import os, uuid, time, requests
import psycopg2, psycopg2.extras, redis as redis_lib
from psycopg2.extras import Json
from agent3.state import Agent3State
from agent3.graph_auth import get_access_token

GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/me/sendMail"
r = redis_lib.from_url(os.getenv("REDIS_URL"))


def _check_rate_limit(user_id: str) -> bool:
    window = int(time.time() // 3600)
    key = f"op:email_throttle:{user_id}:{window}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 3600)
    return count > 200  # max 200 emails/hour


def send_customized_emails(
    campaign_id: str, contact_ids: List[str], subject: str, body: str, html_body: str
):
    """Send customized email to multiple contacts, personalizing each."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import psycopg2

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()

    sent_count = 0
    failed_count = 0

    for contact_id in contact_ids:
        # Get contact details
        cur.execute(
            """
            SELECT c.email, c.first_name, c.last_name, co.company_name
            FROM crm.crm_contacts c
            LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
            WHERE c.contact_id = %s
        """,
            (contact_id,),
        )
        contact = cur.fetchone()

        if not contact or not contact[0]:
            failed_count += 1
            continue

        email = contact[0]
        first_name = contact[1] or ""
        last_name = contact[2] or ""
        company = contact[3] or "your company"
        full_name = f"{first_name} {last_name}".strip()

        # Personalize the email for this contact
        personalized_body = body
        personalized_body = personalized_body.replace("[Name]", full_name)
        personalized_body = personalized_body.replace("[name]", first_name)
        personalized_body = personalized_body.replace("[Company]", company)
        personalized_body = personalized_body.replace("[company]", company)

        personalized_html = html_body
        personalized_html = personalized_html.replace("[Name]", full_name)
        personalized_html = personalized_html.replace("[name]", first_name)
        personalized_html = personalized_html.replace("[Company]", company)
        personalized_html = personalized_html.replace("[company]", company)

        personalized_subject = subject
        personalized_subject = personalized_subject.replace("[Name]", full_name)
        personalized_subject = personalized_subject.replace("[name]", first_name)

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = personalized_subject
            msg["From"] = os.getenv("SMTP_USER")
            msg["To"] = email

            msg.attach(MIMEText(personalized_body, "plain"))
            msg.attach(MIMEText(personalized_html, "html"))

            with smtplib.SMTP(
                os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))
            ) as server:
                server.starttls()
                server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                server.sendmail(os.getenv("SMTP_USER"), email, msg.as_string())

            sent_count += 1
            print(f"✓ Sent to {email}")

        except Exception as e:
            failed_count += 1
            print(f"✗ Failed to send to {email}: {e}")

    cur.close()
    conn.close()

    return {"sent": sent_count, "failed": failed_count}
