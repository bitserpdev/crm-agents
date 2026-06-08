import os
import uuid
import time
import psycopg2
import psycopg2.extras
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()

scheduler = BackgroundScheduler()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def load_template(template_name: str) -> str:
    """Load HTML template from file."""
    template_path = Path(__file__).parent.parent / "templates" / template_name
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def render_job_card(job: dict) -> str:
    """Render a single job card using the template."""
    template = load_template("upwork_job_card.html")

    # Format budget
    budget = job.get("budget", "Not specified")
    if isinstance(budget, dict):
        budget_str = f"{budget.get('min', '?')} - {budget.get('max', '?')} {budget.get('type', 'USD')}"
    else:
        budget_str = str(budget) if budget else "Not specified"

    # Format skills
    skills = job.get("skills", [])
    skills_html = ""
    for skill in skills[:8]:  # Limit to 8 skills
        skills_html += f'<span class="skill">{skill}</span>'

    # Replace placeholders
    html = template
    html = html.replace("{{JOB_TITLE}}", job.get("title", "Untitled"))
    html = html.replace("{{JOB_URL}}", job.get("url", "#"))
    html = html.replace("{{BUDGET}}", budget_str)
    html = html.replace("{{CAMPAIGN_NAME}}", job.get("campaign_name", "Unknown"))
    html = html.replace("{{EXPERIENCE_LEVEL}}", job.get("experience_level") or "")
    html = html.replace("{{SKILLS_HTML}}", skills_html)
    html = html.replace(
        "{{DESCRIPTION}}", (job.get("description", "")[:250]).replace("\n", " ")
    )

    return html


def send_upwork_digest_email(jobs: list):
    """Send email digest with Upwork jobs using HTML templates."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    # Email configuration
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    recipient = os.getenv("UPWORK_DIGEST_EMAIL", smtp_user)

    # Load main template
    main_template = load_template("upwork_digest.html")

    # Generate jobs HTML
    jobs_html = ""
    for job in jobs[:25]:  # Limit to 25 jobs per email
        jobs_html += render_job_card(job)

    if len(jobs) > 25:
        jobs_html += f"""
        <div style="text-align: center; padding: 20px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
            <p style="color: #64748b;">... and {len(jobs) - 25} more jobs. 
            <a href="{os.getenv('UPWORK_DASHBOARD_URL', '#')}" style="color: #4f46e5;">View all in dashboard →</a></p>
        </div>
        """

        # Replace placeholders in main template
        html = main_template
        html = html.replace("{{DATE}}", datetime.now().strftime("%B %d, %Y"))
        html = html.replace("{{YEAR}}", str(datetime.now().year))
        html = html.replace("{{TOTAL_JOBS}}", str(len(jobs)))
        html = html.replace("{{JOBS_LIST}}", jobs_html)
        html = html.replace("{{MANAGE_URL}}", os.getenv("UPWORK_DASHBOARD_URL", "#"))
        html = html.replace(
            "{{UNSUBSCRIBE_URL}}", os.getenv("UPWORK_UNSUBSCRIBE_URL", "#")
        )

    # Plain text version
    text = f"Upwork Daily Job Digest\nDate: {datetime.now().strftime('%Y-%m-%d')}\n"
    text += f"Total jobs: {len(jobs)}\n\n"
    for job in jobs[:25]:
        text += f"\n- {job.get('title', 'Untitled')}\n"
        text += f"  Budget: {job.get('budget', 'N/A')}\n"
        text += f"  URL: {job.get('url', '#')}\n"
        text += f"  Campaign: {job.get('campaign_name', 'Unknown')}\n"

    # Send email
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Upwork Job Digest – {datetime.now().strftime('%Y-%m-%d')}"
        msg["From"] = smtp_user
        msg["To"] = recipient

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient, msg.as_string())

        print(f"[scheduler] Digest email sent to {recipient}")

    except Exception as e:
        print(f"[scheduler] Failed to send digest email: {e}")


def run_daily_digest():
    """Run Agent 6 to fetch and email Upwork jobs digest."""
    print("\n[scheduler] Running daily Upwork digest...")

    from landing.redis_client import get_redis

    r = get_redis()

    today = datetime.now().strftime("%Y-%m-%d")
    last_run = r.get("op:digest:last_run")

    if last_run == today:
        print("[scheduler] Digest already ran today, skipping")
        return

    try:
        from agents.agent6.graph import run_agent6

        result = run_agent6()

        if result.get("run_status") == "done" and result.get("email_sent"):
            print(
                f"[scheduler] Daily digest sent successfully with {result.get('jobs_count', 0)} jobs"
            )
        else:
            print(f"[scheduler] Daily digest failed: {result.get('errors', [])}")

    except Exception as e:
        print(f"[scheduler] Daily digest error: {e}")


def run_campaign(campaign_id: str):
    print(f"\n[scheduler] Starting campaign: {campaign_id}")
    try:
        from agent.graph import build_graph

        graph = build_graph()
        graph.invoke(
            {
                "campaign_id": campaign_id,
                "campaign_config": {},
                "sources_pending": [],
                "current_source": None,
                "raw_records": [],
                "validated_records": [],
                "errors": [],
                "agent_trace_id": str(uuid.uuid4()),
                "run_status": "running",
            }
        )
        _update_last_run(campaign_id)
        print(f"[scheduler] ✓ Campaign {campaign_id} completed")
    except Exception as e:
        print(f"[scheduler] ✗ Campaign {campaign_id} failed: {e}")


def _update_last_run(campaign_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE lz_campaigns
        SET last_run_at = NOW(), updated_at = NOW()
        WHERE campaign_id = %s
    """,
        (campaign_id,),
    )
    conn.commit()
    cur.close()
    conn.close()


def register_campaign(campaign: dict):
    parts = campaign["cron_expression"].split()
    if len(parts) != 5:
        print(f"[scheduler] Invalid CRON: {campaign['cron_expression']}")
        return
    scheduler.add_job(
        func=run_campaign,
        trigger=CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        ),
        id=str(campaign["campaign_id"]),
        replace_existing=True,
        args=[str(campaign["campaign_id"])],
    )
    print(
        f"[scheduler] Registered: {campaign['campaign_name']} ({campaign['cron_expression']})"
    )


def process_retry_queue():
    from landing.redis_client import pop_retry_queue

    items = pop_retry_queue()
    for campaign_id in items:
        print(f"[scheduler] Retrying campaign: {campaign_id}")
        run_campaign(campaign_id)


def load_all_campaigns():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT campaign_id, campaign_name, cron_expression
        FROM lz_campaigns
        WHERE is_active = TRUE
    """)
    campaigns = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(c) for c in campaigns]


def send_due_followups():
    """Send proactive follow-ups for sequences due today."""
    try:
        from agent4.nodes.followup_sender import send_due_followups as _send

        _send()
    except Exception as e:
        print(f"[scheduler] Followup sender error: {e}")


def run_agent4_worker():
    """Process all pending replies in the queue."""
    try:
        import redis
        from agent4.graph import run_agent4

        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        count = 0
        while r.llen("op:reply_queue") > 0:
            result = run_agent4()
            if result.get("run_status") == "skipped":
                break
            count += 1
        if count:
            print(f"[scheduler] Agent 4 processed {count} replies")
    except Exception as e:
        print(f"[scheduler] Agent 4 worker error: {e}")


def run_agent2_batch():
    print("\n[scheduler] Agent 2 batch starting...")
    try:
        from agent2.graph import build_agent2_graph

        graph = build_agent2_graph()
        result = graph.invoke(
            {
                "trigger_type": "batch",
                "raw_events": [],
                "extracted_records": [],
                "enriched_records": [],
                "loaded_records": [],
                "errors": [],
                "agent_trace_id": str(uuid.uuid4()),
                "run_status": "running",
                "stats": {},
            }
        )
        print(f"[scheduler] Agent 2 batch done. Stats: {result.get('stats')}")
    except Exception as e:
        print(f"[scheduler] Agent 2 batch error: {e}")


def run_agent2_realtime():
    """Called when high-intent events are in op:lead_score_queue."""
    from agent2.graph import build_agent2_graph

    graph = build_agent2_graph()
    graph.invoke(
        {
            "trigger_type": "realtime",
            "raw_events": [],
            "extracted_records": [],
            "enriched_records": [],
            "loaded_records": [],
            "errors": [],
            "agent_trace_id": str(uuid.uuid4()),
            "run_status": "running",
            "stats": {},
        }
    )


def monitor_campaign_replies():
    """Check Outlook inbox for replies to all active campaigns."""
    from agent3.nodes.monitor import monitor_replies

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT campaign_id FROM crm.crm_campaigns
        WHERE campaign_type = 'email' AND campaign_status = 'draft'
    """)
    campaigns = cur.fetchall()
    cur.close()
    conn.close()

    for c in campaigns:
        monitor_replies(str(c["campaign_id"]))


def start():
    print("[scheduler] Loading campaigns from DB...")
    campaigns = load_all_campaigns()

    if not campaigns:
        print("[scheduler] No active campaigns found — scheduler waiting")
    else:
        for c in campaigns:
            register_campaign(c)

    # Retry queue consumer every 30 seconds
    scheduler.add_job(
        func=process_retry_queue,
        trigger="interval",
        minutes=60,
        id="retry_queue_consumer",
        max_instances=1,
        coalesce=True,
    )

    # Agent 4 reply worker every 10 seconds
    scheduler.add_job(
        func=run_agent4_worker,
        trigger="interval",
        seconds=10000,
        id="agent4_reply_worker",
        max_instances=1,
        coalesce=True,
    )

    # Agent 4 proactive follow-up sender — check every hour
    scheduler.add_job(
        func=send_due_followups,
        trigger="interval",
        minutes=60,
        id="agent4_followup_sender",
    )

    # Agent 3 reply monitor every 2 minutes
    scheduler.add_job(
        func=monitor_campaign_replies,
        trigger="interval",
        seconds=100000,
        id="agent3_reply_monitor",
        max_instances=1,
        coalesce=True,
    )

    # Add daily digest job at midnight
    scheduler.add_job(
        func=run_daily_digest,
        trigger=CronTrigger(hour=0, minute=5),  # 12:05 AM
        id="daily_upwork_digest",
        replace_existing=True,
    )
    print("[scheduler] Registered daily Upwork digest (12:05 AM)")

    scheduler.start()
    print(f"[scheduler] Started with {len(campaigns)} campaign(s)")
    print("[scheduler] Agent 3 reply monitor will run every 2 minutes")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("[scheduler] Stopped")


if __name__ == "__main__":
    start()


# ── Agent 4 — reply processor every 5 minutes ────────────────────────────────
def run_agent4_replies():
    try:
        from agent4.monitor import process_new_replies

        process_new_replies()
    except Exception as e:
        print(f"[scheduler] Agent4 replies error: {e}")


# ── Agent 4 — follow-up sender every hour ────────────────────────────────────
def run_agent4_followups():
    try:
        from agent4.monitor import send_followups

        send_followups()
    except Exception as e:
        print(f"[scheduler] Agent4 followups error: {e}")

    scheduler.add_job(
        func=run_agent4_replies,
        trigger="interval",
        minutes=5,
        id="agent4_reply_processor",
    )
    scheduler.add_job(
        func=run_agent4_followups,
        trigger="interval",
        hours=1,
        id="agent4_followup_sender",
    )
