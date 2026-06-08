import hashlib
from agents.agent6.state import Agent6State
from config.logger import get_logger

logger = get_logger("agent6.dedup")

def deduplicate_jobs_node(state: Agent6State) -> Agent6State:
    """Remove jobs that were already sent in previous digests."""
    logger.info("Deduplicating jobs...")
    
    jobs = state.get("jobs", [])
    
    if not jobs:
        logger.info("No jobs to deduplicate")
        state["unique_jobs"] = []
        return state
    
    # Get last 7 days of sent job URLs from database or state
    last_run_date = state.get("last_run_date")
    
    # Check against previously sent jobs (from Redis or DB)
    import redis
    import os
    r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    
    unique_jobs = []
    for job in jobs:
        job_url = job.get("url", "")
        if not job_url:
            continue
        
        # Check if this job was sent in last 7 days
        sent_key = f"op:digest:sent:{hashlib.md5(job_url.encode()).hexdigest()}"
        if not r.get(sent_key):
            unique_jobs.append(job)
            # Mark as sent with 7 days expiry
            r.setex(sent_key, 604800, "sent")  # 7 days
    
    logger.info(f"After deduplication: {len(unique_jobs)} unique jobs (removed {len(jobs) - len(unique_jobs)} duplicates)")
    
    state["unique_jobs"] = unique_jobs
    state["jobs_count"] = len(unique_jobs)
    
    return state