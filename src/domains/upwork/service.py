import json
import traceback
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from core.redis import get_redis
from .model import ReviewRequest, TriggerResult
from .repository import repo

INITIAL_STATE = {
    "raw_payload": {},
    "title": "",
    "description": "",
    "url": "",
    "budget": {},
    "skills": [],
    "client": {},
    "proposal_id": None,
    "proposal_text": "",
    "proposal_version": 0,
    "review_status": "pending",
    "review_feedback": "",
    "iteration_count": 0,
    "submitted": False,
    "accepted": False,
    "email_campaign_triggered": False,
    "errors": [],
    "run_status": "running",
}


class UpworkService:

    def _r(self):
        return get_redis()

    # ── Redis helpers ─────────────────────────────────────────────────────────

    def store_proposal(self, event_id: str, data: dict):
        self._r().setex(f"op:agent5:proposal:{event_id}", 3600, json.dumps(data))

    def get_proposal(self, event_id: str) -> Optional[dict]:
        raw = self._r().get(f"op:agent5:proposal:{event_id}")
        return json.loads(raw) if raw else None

    def update_job_status(self, event_id: str, status: str, data: dict = None):
        self._r().setex(
            f"op:agent5:status:{event_id}",
            3600,
            json.dumps({
                "status": status,
                "updated_at": datetime.now().isoformat(),
                "data": data or {},
            }),
        )

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def get_pending_jobs(self, limit: int = 20) -> dict:
        jobs = repo.get_pending_jobs(limit)
        return {
            "data": [
                {
                    "event_id":         j["event_id"],
                    "title":            j["title"] or "Untitled",
                    "budget":           j.get("budget"),
                    "experience_level": j.get("experience_level"),
                    "url":              j.get("url"),
                    "posted_date":      j.get("received_at"),
                    "proposal_status":  "pending",
                    "proposal_id":      None,
                }
                for j in jobs
            ]
        }

    def trigger_job(self, event_id: str) -> TriggerResult:
        from agents.agent5.graph import build_agent5_graph

        graph = build_agent5_graph()
        state = {**INITIAL_STATE, "event_id": event_id}

        try:
            self.update_job_status(event_id, "running")
            final = graph.invoke(state)

            proposal_data = {
                "event_id":      event_id,
                "proposal_text": final.get("proposal_text", ""),
                "subject":       final.get("subject", ""),
                "review_status": final.get("review_status", "pending_review"),
                "proposal_id":   final.get("proposal_id"),
                "errors":        final.get("errors", []),
            }
            self.store_proposal(event_id, proposal_data)
            self.update_job_status(event_id, "completed", proposal_data)

            return TriggerResult(
                status="completed",
                event_id=event_id,
                proposal_text=final.get("proposal_text", ""),
                subject=final.get("subject", ""),
                review_status=final.get("review_status", "pending_review"),
                errors=final.get("errors", []),
            )
        except Exception as e:
            self.update_job_status(event_id, "failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=str(e))

    # ── Proposals ─────────────────────────────────────────────────────────────

    def get_job_proposal(self, event_id: str) -> dict:
        # 1. Check DB first
        db_proposal = repo.get_proposal_from_db(event_id)
        if db_proposal:
            return {
                "event_id": event_id,
                "status":   "completed",
                "proposal": {
                    "text":          db_proposal["proposal_text"],
                    "title":         db_proposal["proposal_title"],
                    "review_status": db_proposal["proposal_status"],
                    "proposal_id":   db_proposal["proposal_id"],
                    "created_at":    db_proposal["created_at"],
                },
            }

        # 2. Check Redis running status
        status_raw = self._r().get(f"op:agent5:status:{event_id}")
        if status_raw:
            info = json.loads(status_raw)
            if info.get("status") == "running":
                return {"event_id": event_id, "status": "running",  "proposal": None, "message": "Proposal generation in progress..."}

        # 3. Check trigger queue
        if self._r().get(f"op:agent5:trigger:{event_id}"):
            return {"event_id": event_id, "status": "queued", "proposal": None, "message": "Proposal generation queued..."}

        # 4. Nothing found
        return {"event_id": event_id, "status": "pending", "proposal": None, "message": "No proposal yet. Click 'Write Proposal' to generate."}

    def get_job_status(self, event_id: str) -> dict:
        raw = self._r().get(f"op:agent5:status:{event_id}")
        if not raw:
            proposal = self.get_proposal(event_id)
            if proposal:
                return {"event_id": event_id, "status": proposal.get("run_status", "done"), "updated_at": proposal.get("completed_at")}
            raise HTTPException(status_code=404, detail="Job not found")
        return json.loads(raw)

    def get_pending_proposal(self, proposal_id: str) -> dict:
        raw = self._r().get(f"op:proposal:{proposal_id}")
        if not raw:
            raise HTTPException(status_code=404, detail="Proposal not found")
        return json.loads(raw)

    def review_proposal(self, proposal_id: str, review: ReviewRequest) -> dict:
        if review.status not in ("approved", "revision", "rejected"):
            raise HTTPException(
                status_code=400,
                detail="status must be: approved | revision | rejected",
            )
        r = self._r()
        key = f"op:proposal_review:{proposal_id}"
        r.rpush(key, json.dumps({
            "status":      review.status,
            "feedback":    review.feedback,
            "proposal_id": proposal_id,
        }))
        r.expire(key, 86400)
        return {"status": "review_queued", "proposal_id": proposal_id}


service = UpworkService()