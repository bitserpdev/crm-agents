from typing import Optional
from fastapi import APIRouter, Query

from .model import ContactList, ContactDetail
from .service import service

router = APIRouter()


@router.get("", response_model=ContactList)
def get_contacts(
    search: Optional[str] = None,
    stage:  Optional[str] = None,
    limit:  int = 50,
    offset: int = 0,
):
    return service.get_contacts(search, stage, limit, offset)


@router.get("/{contact_id}", response_model=ContactDetail)
def get_contact_detail(contact_id: str):
    return service.get_contact(contact_id)