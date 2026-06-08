from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ContactSummary(BaseModel):
    contact_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    job_title: Optional[str]
    contact_type: Optional[str]
    lifecycle_stage: Optional[str]
    source_platform: Optional[str]
    linkedin_url: Optional[str]
    created_at: datetime
    company_name: Optional[str]
    city: Optional[str]
    country: Optional[str]
    intent_score: Optional[float]
    lead_score: Optional[float]
    overall_score: Optional[float]
    tags: Optional[list[str]]


class ContactDetail(ContactSummary):
    fit_score: Optional[float]
    engagement_score: Optional[float]
    score_breakdown: Optional[Any]
    industry: Optional[str]
    website_url: Optional[str]
    company_linkedin: Optional[str]


class ContactList(BaseModel):
    total: int
    records: list[ContactSummary]


class CrmStats(BaseModel):
    total_contacts: int
    total_leads: int
    total_companies: int
    new_leads: int
    qualified_leads: int
    avg_score: Optional[float]
    subscribers: int
    high_intent: int