from typing import TypedDict, Dict, List, Optional, Any

class Agent5State(TypedDict):
    event_id: str
    raw_payload: Dict[str, Any]
    title: str
    description: str
    url: str
    budget: Optional[float]
    skills: List[str]
    client: Dict
    proposal_id: Optional[str]
    proposal_text: str
    proposal_version: int
    review_status: str
    review_feedback: str
    iteration_count: int
    submitted: bool
    accepted: bool
    email_campaign_triggered: bool
    errors: List[str]
    run_status: str