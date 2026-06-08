import os
import json
import uuid
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from landing.redis_client import push_to_inbound_queue
from datetime import datetime, timezone

router = APIRouter()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@router.get("")
def list_connectors():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT platform_name, auth_type, is_active,
               last_synced_at, polling_interval_sec,
               CASE WHEN oauth_access_token IS NOT NULL
                    THEN 'connected' ELSE 'disconnected'
               END AS auth_status,
               oauth_expires_at
        FROM lz_platform_integrations
        ORDER BY platform_name
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

@router.get("/linkedin/auth")
def linkedin_auth():
    from connectors.linkedin import LinkedInConnector
    connector = LinkedInConnector()
    url = connector.get_auth_url()
    return RedirectResponse(url)

@router.get("/linkedin/callback")
def linkedin_callback(
    code: str = None,
    error: str = None,
    error_description: str = None
):
    if error:
        return {
            "status": "error",
            "error": error,
            "description": error_description
        }
    if not code:
        return {"status": "error", "error": "No code received"}
    from connectors.linkedin import LinkedInConnector
    connector = LinkedInConnector()
    tokens = connector.handle_oauth_callback(code)
    return {"status": "connected", "platform": "linkedin"}

@router.post("/linkedin/webhook")
async def linkedin_webhook(request: Request):
    payload = await request.json()
    event   = {
        "event_id":        str(uuid.uuid4()),
        "source_platform": "linkedin",
        "received_at":     datetime.now(timezone.utc).isoformat(),
        "raw_payload":     payload
    }
    push_to_inbound_queue(event)
    return {"status": "queued", "event_id": event["event_id"]}

@router.get("/upwork/auth")
def upwork_auth():
    # Apify uses API token stored in env, no OAuth flow
    return {"message": "Upwork uses Apify API token. Set APIFY_API_TOKEN in .env"}

@router.post("/upwork/webhook")
async def upwork_webhook(request: Request):
    payload = await request.json()
    event = {
        "event_id":        str(uuid.uuid4()),
        "source_platform": "upwork",
        "received_at":     datetime.now(timezone.utc).isoformat(),
        "raw_payload":     payload
    }
    push_to_inbound_queue(event)
    return {"status": "queued", "event_id": event["event_id"]}