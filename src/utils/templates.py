from pathlib import Path
from core.logger import logger

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def load_template(template_name: str) -> str:
    path = TEMPLATES_DIR / template_name
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("[templates] Template not found", path=str(path))
        raise
    except Exception as e:
        logger.error("[templates] Failed to load template",
                     name=template_name, error=str(e))
        raise


def render(template_name: str, context: dict) -> str:
    """
    Load a template and replace all {{KEY}} placeholders from context.

    Usage:
        html = render("upwork_digest.html", {
            "DATE":       "January 15, 2024",
            "TOTAL_JOBS": "12",
            "JOBS_LIST":  jobs_html,
        })
    """
    html = load_template(template_name)
    for key, value in context.items():
        html = html.replace(f"{{{{{key}}}}}", str(value) if value is not None else "")
    return html


def render_job_card(job: dict) -> str:
    """
    Render a single Upwork job card.
    Moved here from scheduler/cron.py — reusable by agent6 and digest email.
    """
    budget = job.get("budget", "Not specified")
    if isinstance(budget, dict):
        budget_str = (
            f"{budget.get('min', '?')} - "
            f"{budget.get('max', '?')} "
            f"{budget.get('type', 'USD')}"
        )
    else:
        budget_str = str(budget) if budget else "Not specified"

    skills_html = "".join(
        f'<span class="skill">{s}</span>'
        for s in job.get("skills", [])[:8]
    )

    return render("upwork_job_card.html", {
        "JOB_TITLE":        job.get("title", "Untitled"),
        "JOB_URL":          job.get("url", "#"),
        "BUDGET":           budget_str,
        "CAMPAIGN_NAME":    job.get("campaign_name", "Unknown"),
        "EXPERIENCE_LEVEL": job.get("experience_level") or "",
        "SKILLS_HTML":      skills_html,
        "DESCRIPTION":      job.get("description", "")[:250].replace("\n", " "),
    })