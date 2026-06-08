from typing import Optional
from fastapi import APIRouter, Query

from .model import LeadList
from .service import service

router = APIRouter()

@router.get("", response_model=LeadList)
def get_leads(
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit:  int = 50,
    offset: int = 0,
):
    return service.get_leads(search, status, limit, offset)