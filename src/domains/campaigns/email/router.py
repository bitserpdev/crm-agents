from typing import Optional
from fastapi import APIRouter
from fastapi.responses import Response
from .model import (
    EmailCampaignCreate, EmailCampaignResponse,
    DeleteResponse, SendCustomizedEmailRequest,
)
from .service import service

router = APIRouter()


@router.get("", response_model=list[EmailCampaignResponse])
def list_email_campaigns():
    return service.list_email_campaigns()


@router.post("", response_model=EmailCampaignResponse)
def create_email_campaign(payload: EmailCampaignCreate):
    return service.create_email_campaign(payload)


@router.delete("/{campaign_id}", response_model=DeleteResponse)
def delete_email_campaign(campaign_id: str):
    return service.delete_email_campaign(campaign_id)


@router.post("/send-customized")
def send_customized(request: SendCustomizedEmailRequest):
    return service.send_customized(request)


@router.post("/{campaign_id}/preview/start")
def start_preview(campaign_id: str, contact_id: Optional[str] = None):
    return service.start_preview(campaign_id, contact_id)


@router.get("/preview/job/{job_id}")
def get_preview_job(job_id: str):
    return service.get_preview_job(job_id)


@router.get("/replies")
def get_replies(campaign_id: Optional[str] = None):
    return service.get_replies(campaign_id)


@router.get("/runs/{run_id}/recipients")
def run_recipients(run_id: str):
    return service.get_run_recipients(run_id)


@router.get("/track/open/{recipient_id}")
def track_open(recipient_id: str):
    service.track_open(recipient_id)
    pixel = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
    return Response(content=pixel, media_type="image/gif")