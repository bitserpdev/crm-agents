from typing import Optional
from fastapi import APIRouter, Query
from .model import RawEventList, SemanticSearchResult, PlatformStat
from .service import service

router = APIRouter()


@router.get("/raw", response_model=RawEventList)
def get_raw_events(
    platform: Optional[str] = None,
    status:   Optional[str] = None,
    limit:    int = 50,
    offset:   int = 0,
):
    return service.get_raw_events(platform, status, limit, offset)


@router.get("/search", response_model=SemanticSearchResult)
def semantic_search(
    q:        str = Query(..., description="Search query"),
    limit:    int = 10,
    platform: Optional[str] = None,
):
    return service.semantic_search(q, limit, platform)


@router.get("/stats", response_model=list[PlatformStat])
def data_stats():
    return service.get_stats()