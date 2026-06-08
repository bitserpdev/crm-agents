from fastapi import APIRouter, BackgroundTasks

from .model import (
    DigestConfig, DigestFilters, ManualTriggerRequest,
    TriggerResponse, PreviewResponse, DigestStatus, ConfigSaveResponse,
)
from .service import service

router = APIRouter()


@router.get("/config",          response_model=dict)
def get_config():
    return service.get_config()


@router.post("/config",         response_model=ConfigSaveResponse)
def update_config(config: DigestConfig):
    return service.save_config(config)


@router.post("/preview",        response_model=PreviewResponse)
def preview_digest(filters: DigestFilters):
    return service.preview_jobs(filters)


@router.post("/trigger",        response_model=TriggerResponse)
def trigger_digest(request: ManualTriggerRequest, background_tasks: BackgroundTasks):
    return service.trigger(request, background_tasks.add_task)


@router.get("/status",          response_model=DigestStatus)
def get_digest_status():
    return service.get_status()


@router.get("/jobs/preview",    response_model=PreviewResponse)
def get_preview_jobs(limit: int = 20):
    return service.get_preview_jobs(limit)