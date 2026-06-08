import os
import json
from landing.redis_client import get_redis
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from connectors.registry import get_connector

router = APIRouter(prefix="/api/agent6", tags=["Agent6"])
r = get_redis()

# ============================================================================
# Pydantic Models
# ============================================================================


class DigestFilters(BaseModel):
    query: str = "python developer data engineer"
    jobType: List[str] = ["hourly", "fixed"]
    experienceLevel: List[str] = ["intermediate", "expert"]
    minBudget: Optional[float] = None
    maxBudget: Optional[float] = None
    location: Optional[str] = None
    paymentVerified: bool = False
    maxJobAgeHours: int = 24
    maxResults: int = 50


class DigestConfig(BaseModel):
    enabled: bool = True
    recipient_email: str
    filters: DigestFilters
    send_time_hour: int = 0
    send_time_minute: int = 5


class ManualTriggerRequest(BaseModel):
    recipient_email: Optional[str] = None
    filters: Optional[DigestFilters] = None


# ============================================================================
# Helper Functions
# ============================================================================


def get_digest_config() -> Dict[str, Any]:
    """Get current digest configuration from Redis."""
    config = r.get("op:digest:config")
    if config:
        return json.loads(config)
    return {
        "enabled": True,
        "recipient_email": os.getenv("UPWORK_DIGEST_EMAIL", ""),
        "filters": {
            "query": os.getenv("UPWORK_DIGEST_QUERY", "python developer data engineer"),
            "jobType": ["hourly", "fixed"],
            "experienceLevel": ["intermediate", "expert"],
            "minBudget": None,
            "maxBudget": None,
            "location": None,
            "paymentVerified": False,
            "maxJobAgeHours": 24,
            "maxResults": 50,
        },
        "send_time_hour": 0,
        "send_time_minute": 5,
    }


def save_digest_config(config: dict):
    """Save digest configuration to Redis."""
    r.set("op:digest:config", json.dumps(config), ex=86400 * 30)  # 30 days


def preview_jobs(filters: DigestFilters) -> List[Dict[str, Any]]:
    """Fetch jobs based on filters for preview."""
    connector = get_connector("upwork")  # Assuming we have a registry of connectors

    # Build filter dict
    filter_dict = {
        "query": filters.query,
        "jobType": filters.jobType,
        "experienceLevel": filters.experienceLevel,
        "paymentVerified": filters.paymentVerified,
        "maxJobAge": {"value": filters.maxJobAgeHours, "unit": "hours"},
        "count": filters.maxResults,
    }

    if filters.minBudget:
        filter_dict["minBudget"] = filters.minBudget
    if filters.maxBudget:
        filter_dict["maxBudget"] = filters.maxBudget
    if filters.location:
        filter_dict["location"] = filters.location

    try:
        jobs = connector.poll({"filters": filter_dict})
        return jobs[: filters.maxResults]
    except Exception as e:
        print(f"[Agent6] Preview error: {e}")
        return []


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/config")
def get_config():
    """Get current digest configuration."""
    return get_digest_config()


@router.post("/config")
def update_config(config: DigestConfig):
    """Update digest configuration."""
    save_digest_config(config.dict())
    return {"status": "saved", "config": config.dict()}


@router.post("/preview")
def preview_digest(filters: DigestFilters):
    """Preview jobs with given filters."""
    jobs = preview_jobs(filters)
    return {"jobs": jobs, "count": len(jobs), "filters": filters.dict()}


@router.post("/trigger")
def trigger_digest(request: ManualTriggerRequest, background_tasks: BackgroundTasks):
    """Manually trigger the digest."""

    print("Trigger => ", request.filters)

    def run_digest():
        from agents.agent6.graph import run_agent6

        recipient = request.recipient_email
        filters = None

        if request.filters:
            filters = request.filters.dict()

        result = run_agent6(filters=filters, recipient_email=recipient)

        # Store last manual trigger result
        r.set(
            "op:digest:last_manual",
            json.dumps(
                {
                    "timestamp": datetime.now().isoformat(),
                    "jobs_count": result.get("jobs_count", 0),
                    "email_sent": result.get("email_sent", False),
                    "errors": result.get("errors", []),
                }
            ),
            ex=86400,
        )  # 24 hours

        print(
            f"[Agent6] Manual digest completed: {result.get('jobs_count')} jobs, sent: {result.get('email_sent')}"
        )

    background_tasks.add_task(run_digest)

    return {
        "status": "started",
        "message": "Digest is being processed. Check logs for results.",
    }


@router.get("/status")
def get_digest_status():
    """Get digest status and history."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Get last run info
    last_run = r.get("op:digest:last_run")
    last_count = r.get(f"op:digest:count:{today}")
    last_manual = r.get("op:digest:last_manual")

    # Get last 7 days stats
    stats = []
    from datetime import timedelta

    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = r.get(f"op:digest:count:{date}")
        stats.append({"date": date, "jobs_count": int(count) if count else 0})

    return {
        "last_run_date": last_run,
        "today_jobs_count": int(last_count) if last_count else 0,
        "last_manual": json.loads(last_manual) if last_manual else None,
        "weekly_stats": stats,
        "config": get_digest_config(),
    }


@router.get("/jobs/preview")
def get_preview_jobs(limit: int = 20):
    """Get sample jobs for preview without triggering digest."""

    connector = get_connector("upwork")  # Assuming we have a registry of connectors
    config = get_digest_config()
    filters = config.get("filters", {})

    filter_dict = {
        "query": filters.get("query", "python developer"),
        "jobType": filters.get("jobType", ["hourly", "fixed"]),
        "experienceLevel": filters.get("experienceLevel", ["intermediate", "expert"]),
        "maxJobAge": {"value": filters.get("maxJobAgeHours", 24), "unit": "hours"},
        "count": limit,
    }

    try:
        jobs = connector.poll({"filters": filter_dict})
        return {"jobs": jobs[:limit], "count": len(jobs[:limit])}
    except Exception as e:
        return {"error": str(e), "jobs": []}
