from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class RunSummary(BaseModel):
    log_id: str
    event_id: str
    agent_id: Optional[str]
    extraction_status: str
    duration_ms: Optional[int]
    ran_at: datetime
    error_message: Optional[str]
    source_platform: Optional[str]
    campaign_id: Optional[str]
    processing_status: Optional[str]


class RunDetail(RunSummary):
    raw_payload: Optional[dict]


class RunStat(BaseModel):
    extraction_status: str
    count: int
    avg_duration_ms: Optional[float]