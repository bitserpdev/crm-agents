from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ReviewRequest(BaseModel):
    status: str  # approved | revision | rejected
    feedback: str = ""


class ProposalStatus(BaseModel):
    event_id: str
    status: str
    proposal: Optional[dict] = None
    message: Optional[str] = None


class JobSummary(BaseModel):
    event_id: str
    title: str
    budget: Optional[str]
    experience_level: Optional[str]
    url: Optional[str]
    posted_date: Optional[datetime]
    proposal_status: str
    proposal_id: Optional[str]


class JobList(BaseModel):
    data: list[JobSummary]


class TriggerResult(BaseModel):
    status: str
    event_id: str
    proposal_text: Optional[str]
    subject: Optional[str]
    review_status: Optional[str]
    errors: list[str] = []


class ReviewResult(BaseModel):
    status: str
    proposal_id: str