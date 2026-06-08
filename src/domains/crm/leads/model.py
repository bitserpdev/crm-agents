from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LeadSummary(BaseModel):
    lead_id: str
    lead_status: Optional[str]
    lead_score: Optional[float]
    source_platform: Optional[str]
    source_detail: Optional[str]
    initial_message: Optional[str]
    created_at: datetime
    estimated_value: Optional[float]
    currency: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    job_title: Optional[str]
    email: Optional[str]
    company_name: Optional[str]
    intent_score: Optional[float]
    overall_score: Optional[float]


class LeadList(BaseModel):
    records: list[LeadSummary]