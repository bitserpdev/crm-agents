from typing import TypedDict, List, Optional, Dict, Any

class Agent6State(TypedDict):
    """State for Agent 6 – Upwork Daily Digest Agent."""
    
    # Input
    filters: Dict[str, Any]           # Global filters for job search
    recipient_email: str              # Email address to send digest to
    
    # Processing
    jobs: List[Dict[str, Any]]        # Fetched jobs from Upwork
    unique_jobs: List[Dict[str, Any]] # After deduplication
    
    # Output
    email_sent: bool
    email_html: str
    email_text: str
    jobs_count: int
    
    # Tracking
    last_run_date: str                # To avoid duplicate sends
    sent_emails: List[str]            # Track which jobs were sent
    
    # Status
    errors: List[str]
    run_status: str                   # running | done | failed