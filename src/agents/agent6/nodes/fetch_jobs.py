from datetime import datetime
from agents.agent6.state import Agent6State
from connectors.registry import get_connector
from config.logger import get_logger

logger = get_logger("agent6.fetch")

def fetch_jobs_node(state: Agent6State) -> Agent6State:
    """Fetch fresh Upwork jobs using the provided filters."""
    logger.info("Fetching Upwork jobs for daily digest...")
    
    filters = state.get("filters", {})
    recipient = state.get("recipient_email")
    
    if not filters:
        logger.warning("No filters provided, using default filters")
        filters = {
            "query": "python developer data engineer",
            "jobType": ["hourly", "fixed"],
            "experienceLevel": ["intermediate", "expert"],
            "maxJobAge": {"value": 24, "unit": "hours"},
            "limit": 50
        }
    
    # Add count limit
    filters["count"] = 50
    
    try:
        connector = get_connector("upwork")
        jobs = connector.poll({"filters": filters})
        
        logger.info(f"Fetched {len(jobs)} jobs from Upwork")
        
        # Add received date for tracking
        for job in jobs:
            job["fetched_at"] = datetime.now().isoformat()
        
        state["jobs"] = jobs
        state["jobs_count"] = len(jobs)
        state["run_status"] = "running"
        
    except Exception as e:
        logger.error(f"Failed to fetch jobs: {e}")
        state["errors"].append(str(e))
        state["run_status"] = "failed"
    
    return state