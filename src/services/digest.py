import os
from datetime import datetime
from core.redis import get_redis
from core.logger import logger
from services.email import email_service, EmailMessage
from utils.date import today_str, now_display_str, now_year_str, is_today
from utils.templates import render, render_job_card


def run_daily_digest():
    logger.info("[digest] Starting daily Upwork digest")
    r = get_redis()

    if is_today(r.get("op:digest:last_run")):
        logger.info("[digest] Already ran today — skipping")
        return

    try:
        from agents.agent6.graph import run_agent6
        result = run_agent6()

        if result.get("run_status") == "done" and result.get("email_sent"):
            logger.info("[digest] Sent successfully",
                        jobs=result.get("jobs_count", 0))
        else:
            logger.error("[digest] Failed", errors=result.get("errors", []))

    except Exception as e:
        logger.error("[digest] Error", error=str(e))
        raise


def send_upwork_digest_email(jobs: list):
    """
    Build and send the Upwork job digest email.
    Called by agent6 after fetching jobs.
    """
    recipient = os.getenv("UPWORK_DIGEST_EMAIL", os.getenv("SMTP_USER"))

    html = _build_digest_html(jobs)
    text = _build_digest_text(jobs)

    success = email_service.send(EmailMessage(
        to=recipient,
        subject=f"Upwork Job Digest – {today_str()}",
        body_text=text,
        body_html=html,
    ))

    if success:
        logger.info("[digest] Email sent", recipient=recipient, jobs=len(jobs))
    else:
        logger.error("[digest] Email failed", recipient=recipient)

    return success


# ── Builders ──────────────────────────────────────────────────────────────────

def _build_digest_html(jobs: list) -> str:
    jobs_html = "".join(render_job_card(j) for j in jobs[:25])

    if len(jobs) > 25:
        dashboard_url = os.getenv("UPWORK_DASHBOARD_URL", "#")
        jobs_html += f"""
        <div style="text-align:center;padding:20px;">
            <p>... and {len(jobs) - 25} more jobs.
            <a href="{dashboard_url}">View all in dashboard →</a></p>
        </div>
        """

    return render("upwork_digest.html", {
        "DATE":            now_display_str(),
        "YEAR":            now_year_str(),
        "TOTAL_JOBS":      str(len(jobs)),
        "JOBS_LIST":       jobs_html,
        "MANAGE_URL":      os.getenv("UPWORK_DASHBOARD_URL", "#"),
        "UNSUBSCRIBE_URL": os.getenv("UPWORK_UNSUBSCRIBE_URL", "#"),
    })


def _build_digest_text(jobs: list) -> str:
    lines = [
        f"Upwork Daily Job Digest — {today_str()}",
        f"Total: {len(jobs)} jobs\n",
    ]
    for job in jobs[:25]:
        lines += [
            f"- {job.get('title', 'Untitled')}",
            f"  Budget:   {job.get('budget', 'N/A')}",
            f"  URL:      {job.get('url', '#')}",
            f"  Campaign: {job.get('campaign_name', 'Unknown')}\n",
        ]
    return "\n".join(lines)