from datetime import datetime
from agents.agent6.state import Agent6State
from agents.agent6.prompts import DAILY_DIGEST_HTML_TEMPLATE, DAILY_DIGEST_SUBJECT
from config.logger import get_logger
from utils.templates import load_template

logger = get_logger("agent6.email")

# Load templates once at module level
MAIN_TEMPLATE = load_template("upwork_digest.html")
JOB_CARD_TEMPLATE = load_template("upwork_job_card.html")


def safe_str(value, default="Not specified"):
    """Convert value to string safely, handling None."""
    if value is None:
        return default
    return str(value)


def render_job_card(job: dict) -> str:
    """Render a single job card using the template."""
    
    # Format budget
    budget = job.get("budget", {})
    if isinstance(budget, dict):
        if budget.get("type") == "hourly":
            budget_str = f"${safe_str(budget.get('min', '?'))} - ${safe_str(budget.get('max', '?'))}/hr"
        elif budget.get("type") == "fixed":
            budget_str = f"${safe_str(budget.get('min', '?'))} - ${safe_str(budget.get('max', '?'))} fixed"
        else:
            budget_str = f"${safe_str(budget.get('min', '?'))} - ${safe_str(budget.get('max', '?'))}"
    elif isinstance(budget, str):
        budget_str = budget if budget else "Not specified"
    else:
        budget_str = "Not specified"
    
    # Get job title safely
    title = safe_str(job.get("title"), "Untitled")
    
    # Get URL safely
    url = safe_str(job.get("url"), "#")
    
    # Get experience level safely
    experience_level = safe_str(job.get("experience_level"), "Any")
    
    # Get campaign name safely
    campaign_name = safe_str(job.get("campaign_name"), "Daily Digest")
    
    # Generate skills HTML
    skills = job.get("skills", [])
    if not skills:
        skills = []
    
    skills_html = ""
    for skill in skills[:8]:
        if skill:
            skills_html += f'<span class="skill">{safe_str(skill)}</span>'
    
    if not skills_html:
        skills_html = '<span class="skill">No skills listed</span>'
    
    # Get description safely
    description = safe_str(job.get("description", ""))
    description = description.replace("\n", " ")[:250]
    
    # Render template by replacing placeholders
    html = JOB_CARD_TEMPLATE
    html = html.replace("{{JOB_TITLE}}", title)
    html = html.replace("{{JOB_URL}}", url)
    html = html.replace("{{BUDGET}}", budget_str)
    html = html.replace("{{CAMPAIGN_NAME}}", campaign_name)
    html = html.replace("{{EXPERIENCE_LEVEL}}", experience_level)
    html = html.replace("{{SKILLS_HTML}}", skills_html)
    html = html.replace("{{DESCRIPTION}}", description)
    
    return html


def build_email_node(state: Agent6State) -> Agent6State:
    """Build HTML and plain text email from jobs."""
    logger.info("Building email digest...")

    jobs = state.get("unique_jobs", [])

    if not jobs:
        logger.info("No jobs to include in email")
        state["email_sent"] = False
        state["run_status"] = "done"
        return state

    date_str = datetime.now().strftime("%B %d, %Y")
    current_year = str(datetime.now().year)

    # Build jobs HTML using the job card template
    jobs_html = ""
    for job in jobs[:30]:  # Limit to 30 jobs per email
        try:
            jobs_html += render_job_card(job)
        except Exception as e:
            logger.error(f"Error rendering job card: {e}")
            continue

    if len(jobs) > 30:
        jobs_html += f"""
        <div style="text-align: center; padding: 20px; background: #f8fafc; border-radius: 8px; margin-top: 20px;">
            <p>... and {len(jobs) - 30} more jobs. Check the dashboard for full list.</p>
        </div>
        """

    # Build HTML email using main template
    html_email = MAIN_TEMPLATE
    html_email = html_email.replace("{{DATE}}", date_str)
    html_email = html_email.replace("{{YEAR}}", current_year)
    html_email = html_email.replace("{{TOTAL_JOBS}}", str(len(jobs)))
    html_email = html_email.replace("{{JOBS_LIST}}", jobs_html)
    html_email = html_email.replace("{{MANAGE_URL}}", "#")
    html_email = html_email.replace("{{UNSUBSCRIBE_URL}}", "#")

    # Build plain text email
    text_email = f"Upwork Daily Job Digest - {date_str}\n"
    text_email += f"Found {len(jobs)} new jobs.\n\n"

    for job in jobs[:30]:
        # Format budget for text
        budget = job.get("budget", {})
        if isinstance(budget, dict):
            if budget.get("type") == "hourly":
                budget_str = f"${safe_str(budget.get('min', '?'))} - ${safe_str(budget.get('max', '?'))}/hr"
            else:
                budget_str = f"${safe_str(budget.get('min', '?'))} - ${safe_str(budget.get('max', '?'))}"
        else:
            budget_str = safe_str(budget, "Not specified")
        
        title = safe_str(job.get("title"), "Untitled")
        url = safe_str(job.get("url"), "#")
        
        text_email += f"\n- {title}\n"
        text_email += f"  Budget: {budget_str}\n"
        text_email += f"  URL: {url}\n"

    state["email_html"] = html_email
    state["email_text"] = text_email

    subject = DAILY_DIGEST_SUBJECT.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        job_count=len(jobs)
    )
    state["subject"] = subject

    logger.info(f"Email built with {len(jobs)} jobs")
    return state