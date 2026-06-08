from typing import Optional
from fastapi import HTTPException

from .repository import repo
from .model import (
    ConversationSummary, ConversationStats,
    ThreadDetail, ThreadMessage, MeetingDetail,
    FollowupSummary, FollowupStats,
)


class SequenceService:

    # ── Conversations ─────────────────────────────────────────────────────────

    def list_conversations(
        self,
        campaign_id: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[ConversationSummary]:
        return repo.list_conversations(campaign_id, intent)

    def get_conversation_stats(
        self, campaign_id: Optional[str] = None
    ) -> ConversationStats:
        return ConversationStats(**repo.get_conversation_stats(campaign_id))

    def get_thread(self, sequence_id: str) -> ThreadDetail:
        data = repo.get_thread(sequence_id)
        if not data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        messages = []
        for m in data["initial"]:
            messages.append(ThreadMessage(
                direction="outbound",
                body=m["body"] or "",
                subject=m["subject"] or "",
                ts=str(m["ts"]) if m["ts"] else None,
                intent_label=None,
                step=0,
                type="initial",
            ))
        for m in data["followups"]:
            messages.append(ThreadMessage(
                direction=m["direction"],
                body=m["body"] or "",
                subject=m["subject"] or "",
                ts=str(m["ts"]) if m["ts"] else None,
                intent_label=m["intent_label"],
                step=m["step"],
                type="followup",
            ))

        messages.sort(key=lambda x: x.ts or "")

        return ThreadDetail(
            sequence=data["sequence"],
            messages=messages,
            meeting=MeetingDetail(**data["meeting"]) if data["meeting"] else None,
        )

    # ── Follow-ups ────────────────────────────────────────────────────────────

    def list_followups(
        self,
        campaign_id: Optional[str] = None,
        tab: str = "all",
    ) -> list[FollowupSummary]:
        return repo.list_followups(campaign_id, tab)

    def get_followup_stats(
        self, campaign_id: Optional[str] = None
    ) -> FollowupStats:
        return FollowupStats(**repo.get_followup_stats(campaign_id))


service = SequenceService()