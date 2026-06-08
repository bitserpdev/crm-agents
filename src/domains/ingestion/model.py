from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class RawEvent(BaseModel):
    event_id: str
    received_at: datetime
    source_platform: Optional[str]
    raw_payload: Optional[Any]
    dedup_key: Optional[str]
    processing_status: Optional[str]
    campaign_id: Optional[str]
    created_at: datetime


class RawEventList(BaseModel):
    total: int
    records: list[RawEvent]


class SemanticHit(BaseModel):
    event_id: Optional[str]
    score: float
    source_platform: Optional[str]
    received_at: Optional[str]
    dedup_key: Optional[str]


class SemanticSearchResult(BaseModel):
    query: str
    results: list[SemanticHit]
    error: Optional[str] = None


class PlatformStat(BaseModel):
    source_platform: Optional[str]
    total_events: int
    done: int
    duplicates: int