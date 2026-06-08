from fastapi import APIRouter, HTTPException
from .model import RunSummary, RunDetail, RunStat
from .repository import repo

router = APIRouter()


@router.get("", response_model=list[RunSummary])
def list_runs(limit: int = 50):
    return repo.list_runs(limit)


@router.get("/stats", response_model=list[RunStat])
def run_stats():
    return repo.get_stats()


@router.get("/campaign/{campaign_id}", response_model=list[RunSummary])
def runs_by_campaign(campaign_id: str, limit: int = 50):
    return repo.list_by_campaign(campaign_id, limit)


@router.get("/{log_id}", response_model=RunDetail)
def get_run_detail(log_id: str):
    run = repo.get_by_id(log_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run