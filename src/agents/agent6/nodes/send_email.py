import os
import smtplib
import psycopg2
import psycopg2.extras
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from agents.agent6.state import Agent6State
from config.logger import get_logger

logger = get_logger("agent6.send")


def send_email_node(state: Agent6State) -> Agent6State:
    """Send the digest email."""
    logger.info("Sending digest email...")

    recipient = state.get("recipient_email")

    if not recipient:
        logger.error("No recipient email provided")
        state["errors"].append("No recipient email provided")
        state["run_status"] = "failed"
        return state

    jobs_count = state.get("jobs_count", 0)

    if jobs_count == 0:
        logger.info("No jobs to send, skipping email")
        state["email_sent"] = False
        state["run_status"] = "done"
        return state

    # Email configuration
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_host, smtp_user, smtp_password]):
        logger.error("SMTP configuration missing")
        state["errors"].append("SMTP configuration missing")
        state["run_status"] = "failed"
        return state

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = state.get("subject", "Upwork Daily Job Digest")
        msg["From"] = smtp_user
        msg["To"] = recipient

        msg.attach(MIMEText(state["email_text"], "plain"))
        msg.attach(MIMEText(state["email_html"], "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient, msg.as_string())

        logger.info(f"Digest email sent to {recipient} with {jobs_count} jobs")
        state["email_sent"] = True
        state["run_status"] = "done"

        # Store in database for audit
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            INSERT INTO lz_extraction_logs (log_id, event_id, agent_id, extraction_status, extracted_fields, ran_at)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, NOW())
            """,
            (
                f"digest_{datetime.now().strftime('%Y%m%d')}",
                "agent-6-daily-digest",
                "success",
                {"jobs_count": jobs_count, "recipient": recipient},
            ),
        )
        conn.commit()

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        state["errors"].append(str(e))
        state["run_status"] = "failed"

    return state
