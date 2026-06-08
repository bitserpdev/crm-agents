from datetime import datetime, timezone
from fastapi import HTTPException
from core.redis import push_to_inbound_queue
from core.logger import logger
from utils.uuid import new_id

# ── Platform registry ─────────────────────────────────────────────────────────
# Add new platforms here only — nothing else needs to change
OAUTH_PLATFORMS  = {"linkedin"}
APIKEY_PLATFORMS = {"upwork"}
ALL_PLATFORMS    = OAUTH_PLATFORMS | APIKEY_PLATFORMS


def get_all() -> list:
    from domains.connectors import repository as repo
    return repo.get_all_integrations()


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_auth_url(platform: str) -> str:
    _assert_platform(platform)

    if platform not in OAUTH_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Platform '{platform}' does not use OAuth. "
                   f"OAuth platforms: {', '.join(sorted(OAUTH_PLATFORMS))}",
        )

    connector = _get_connector(platform)
    return connector.get_auth_url()


def handle_oauth_callback(platform: str, code: str) -> dict:
    _assert_platform(platform)

    if not code:
        raise HTTPException(status_code=400, detail="No auth code received")

    connector = _get_connector(platform)
    connector.handle_oauth_callback(code)
    logger.info("[connectors.service] OAuth connected", platform=platform)
    return {"status": "connected", "platform": platform}


def get_auth_info(platform: str) -> dict:
    """
    For non-OAuth platforms — returns setup instructions.
    Keeps the API surface consistent regardless of auth type.
    """
    _assert_platform(platform)

    if platform in APIKEY_PLATFORMS:
        return {
            "platform": platform,
            "auth_type": "api_key",
            "message": f"{platform.title()} uses an API token. "
                       f"Set {platform.upper()}_API_TOKEN in .env",
        }

    return get_auth_url(platform)


# ── Webhooks ──────────────────────────────────────────────────────────────────

def handle_webhook(platform: str, payload: dict) -> dict:
    _assert_platform(platform)

    event = {
        "event_id":        new_id(),
        "source_platform": platform,
        "received_at":     datetime.now(timezone.utc).isoformat(),
        "raw_payload":     payload,
    }

    push_to_inbound_queue(event)
    logger.info("[connectors.service] Webhook queued",
                platform=platform, event_id=event["event_id"])
    return {"status": "queued", "event_id": event["event_id"]}


# ── Private ───────────────────────────────────────────────────────────────────

def _assert_platform(platform: str):
    if platform not in ALL_PLATFORMS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown platform '{platform}'. "
                   f"Supported: {', '.join(sorted(ALL_PLATFORMS))}",
        )


def _get_connector(platform: str):
    from connectors import get_connector
    return get_connector(platform)