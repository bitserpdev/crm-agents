from typing import Optional
from fastapi import APIRouter

from .model import (
    ConversationSummary, ConversationStats,
    ThreadDetail, FollowupSummary, FollowupStats,
)
from .service import service

router = APIRouter()

# ── Conversations ─────────────────────────────────────────────────────────────

@router.get("/conversations",       response_model=list[ConversationSummary])
def get_conversations(
    campaign_id: Optional[str] = None,
    intent:      Optional[str] = None,
):
    return service.list_conversations(campaign_id, intent)


@router.get("/conversations/stats", response_model=ConversationStats)
def get_conversation_stats(campaign_id: Optional[str] = None):
    return service.get_conversation_stats(campaign_id)


@router.get("/conversations/{sequence_id}/thread", response_model=ThreadDetail)
def get_thread(sequence_id: str):
    return service.get_thread(sequence_id)


# ── Follow-ups ────────────────────────────────────────────────────────────────

@router.get("/followups",       response_model=list[FollowupSummary])
def get_followups(
    campaign_id: Optional[str] = None,
    tab:         str = "all",
):
    return service.list_followups(campaign_id, tab)


@router.get("/followups/stats", response_model=FollowupStats)
def get_followup_stats(campaign_id: Optional[str] = None):
    return service.get_followup_stats(campaign_id)