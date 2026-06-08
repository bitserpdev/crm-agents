from fastapi import APIRouter

from .contacts.router import router as contacts_router
from .leads.router import router as leads_router

router = APIRouter()

router.include_router(contacts_router, prefix="/contacts", tags=["crm-contacts"])
router.include_router(leads_router, prefix="/leads", tags=["crm-leads"])
