from typing import Any, Optional
from pydantic import BaseModel


class DigestFilters(BaseModel):
    query: str = "python developer data engineer"
    jobType: list[str] = ["hourly", "fixed"]
    experienceLevel: list[str] = ["intermediate", "expert"]
    minBudget: Optional[float] = None
    maxBudget: Optional[float] = None
    location: Optional[str] = None
    paymentVerified: bool = False
    maxJobAgeHours: int = 24
    maxResults: int = 50


class DigestConfig(BaseModel):
    enabled: bool = True
    recipient_email: str
    filters: DigestFilters
    send_time_hour: int = 0
    send_time_minute: int = 5


class ManualTriggerRequest(BaseModel):
    recipient_email: Optional[str] = None
    filters: Optional[DigestFilters] = None


class TriggerResponse(BaseModel):
    status: str
    message: str


class PreviewResponse(BaseModel):
    jobs: list[dict]
    count: int
    filters: Optional[dict] = None


class Dailystat(BaseModel):
    date: str
    jobs_count: int


class DigestStatus(BaseModel):
    last_run_date: Optional[str]
    today_jobs_count: int
    last_manual: Optional[dict]
    weekly_stats: list[Dailystat]
    config: dict


class ConfigSaveResponse(BaseModel):
    status: str
    config: dict