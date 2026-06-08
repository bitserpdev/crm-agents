import redis
import os
from datetime import datetime
from agents.agent6.state import Agent6State
from config.logger import get_logger
from landing.redis_client import get_redis

logger = get_logger("agent6.record")
r = get_redis()

def record_node(state: Agent6State) -> Agent6State:
    """Record the digest run and update last run timestamp."""
    logger.info("Recording digest run...")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Store last run date
    r.set("op:digest:last_run", today)
    
    # Store job count for today
    r.set(f"op:digest:count:{today}", state.get("jobs_count", 0))
    
    logger.info(f"Daily digest recorded for {today}, jobs: {state.get('jobs_count', 0)}")
    
    return state