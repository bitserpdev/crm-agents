from fastapi import APIRouter
from domains.campaigns.service import campaign_service
from domains.campaigns.models import (
    CampaignCreate,
    CampaignUpdate,
    FilterValidationRequest,
)
from domains.campaigns.email.router import router as email_router
from domains.campaigns.run.router import router as run_history_router
from domains.campaigns.sequences.router import router as sequences_router

router = APIRouter()

# ── Static routes first ───────────────────────────────────────────────────────
@router.get("")
def list_campaigns():
    return campaign_service.get_all()


@router.post("")
def create_campaign(payload: CampaignCreate):
    return campaign_service.create(payload)


@router.post("/validate-filters")
def validate_filters(payload: FilterValidationRequest):
    return campaign_service.validate_filters(payload)


# ── Mount child routers BEFORE /{campaign_id} ─────────────────────────────────
router.include_router(
    email_router,
    prefix="/emails",
    tags=["Campaign Emails"],
)

router.include_router(
    run_history_router,
    prefix="/runs",
    tags=["Campaign Runs"],
)

router.include_router(
    sequences_router, prefix="/sequences", tags=["campaigns-sequences"]
)


# ── Dynamic /{campaign_id} routes LAST ───────────────────────────────────────
@router.put("/{campaign_id}")
def update_campaign(campaign_id: str, payload: CampaignUpdate):
    return campaign_service.update(campaign_id, payload)


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: str):
    return campaign_service.delete(campaign_id)


@router.post("/{campaign_id}/trigger")
def trigger_campaign(campaign_id: str):
    return campaign_service.trigger(campaign_id)
