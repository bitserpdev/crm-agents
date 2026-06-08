from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from typing import List 


class EmailCampaignCreate(BaseModel):
    campaign_name: str
    service_description: Optional[str] = None
    from_address: str
    filter_region: Optional[str] = None
    filter_industry: Optional[str] = None
    filter_company_size: Optional[str] = None
    filter_min_score: Optional[int] = 0
    filter_max_score: Optional[int] = 100
    filter_stage: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class EmailCampaignResponse(BaseModel):
    campaign_id: str
    campaign_name: str
    campaign_status: str
    from_address: str
    service_description: Optional[str]
    filter_region: Optional[str]
    filter_industry: Optional[str]
    filter_company_size: Optional[str]
    filter_min_score: Optional[int]
    filter_max_score: Optional[int]
    filter_stage: Optional[str]
    scheduled_at: Optional[datetime]
    created_at: datetime


class DeleteResponse(BaseModel):
    deleted: str

class SendCustomizedEmailRequest(BaseModel):
    campaign_id: str
    contact_ids: List[str]
    subject:     str
    body:        str
    html_body:   str


class PreviewStartRequest(BaseModel):
    contact_id: Optional[str] = None


class PreviewJob(BaseModel):
    status: str
    email:  Optional[dict] = None