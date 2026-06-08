from fastapi import APIRouter

from .model import ReviewRequest, TriggerResult, JobList, ProposalStatus, ReviewResult
from .service import service
from domains.upwork.digest.router import router as digest_router

router = APIRouter()

router.include_router(digest_router, prefix="/digest", tags=["Digest"])


@router.get("/jobs/pending", response_model=JobList)
def get_pending_jobs(limit: int = 20):
    return service.get_pending_jobs(limit)


@router.post("/jobs/{event_id}/trigger", response_model=TriggerResult)
def trigger_job(event_id: str):
    return service.trigger_job(event_id)


@router.get("/jobs/{event_id}/proposal", response_model=ProposalStatus)
def get_job_proposal(event_id: str):
    return service.get_job_proposal(event_id)


@router.get("/jobs/{event_id}/status")
def get_job_status(event_id: str):
    return service.get_job_status(event_id)


@router.get("/proposals/{proposal_id}/pending")
def get_pending_proposal(proposal_id: str):
    return service.get_pending_proposal(proposal_id)


@router.post("/proposals/{proposal_id}/review", response_model=ReviewResult)
def review_proposal(proposal_id: str, review: ReviewRequest):
    return service.review_proposal(proposal_id, review)
