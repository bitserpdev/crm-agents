from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


# ── Conversations ─────────────────────────────────────────────────────────────

class ConversationSummary(BaseModel):
    sequence_id: str
    campaign_id: Optional[str]
    contact_id: Optional[str]
    current_step: Optional[int]
    max_steps: Optional[int]
    status: Optional[str]
    last_reply_at: Optional[datetime]
    last_intent_label: Optional[str]
    asked_availability: Optional[bool]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    job_title: Optional[str]
    company_name: Optional[str]
    industry: Optional[str]
    overall_score: Optional[float]
    campaign_name: Optional[str]
    teams_join_url: Optional[str]
    last_reply_preview: Optional[str]
    total_messages: Optional[int]


class ConversationStats(BaseModel):
    total: int
    hot: int
    warm: int
    cold: int
    call_scheduled: int
    unsubscribed: int


class ThreadMessage(BaseModel):
    direction: str
    body: str
    subject: str
    ts: Optional[str]
    intent_label: Optional[str]
    step: int
    type: str


class MeetingDetail(BaseModel):
    join_url: Optional[str]
    subject: Optional[str]
    scheduled_at: Optional[datetime]


class ThreadDetail(BaseModel):
    sequence: dict
    messages: list[ThreadMessage]
    meeting: Optional[MeetingDetail]


# ── Follow-ups ────────────────────────────────────────────────────────────────

class FollowupSummary(BaseModel):
    sequence_id: str
    campaign_id: Optional[str]
    contact_id: Optional[str]
    current_step: Optional[int]
    max_steps: Optional[int]
    status: Optional[str]
    next_followup_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    job_title: Optional[str]
    company_name: Optional[str]
    industry: Optional[str]
    campaign_name: Optional[str]
    opened_at: Optional[datetime]
    initial_sent_at: Optional[datetime]
    followups_sent: Optional[int]


class FollowupStats(BaseModel):
    total: int
    no_open: int
    opened: int
    fu1: int
    fu2: int
    fu3: int
    fu4: int
    fu5: int
    exhausted: int