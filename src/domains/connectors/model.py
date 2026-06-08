from pydantic import BaseModel
from typing import Optional


class ConnectorStatus(BaseModel):
    platform_name:        str
    auth_type:            str
    is_active:            bool
    last_synced_at:       Optional[str] = None
    polling_interval_sec: Optional[int] = None
    auth_status:          str            # "connected" | "disconnected"
    oauth_expires_at:     Optional[str] = None


class WebhookEvent(BaseModel):
    event_id:        str
    source_platform: str
    received_at:     str
    raw_payload:     dict