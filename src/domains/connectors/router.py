from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from domains.connectors import service as connector_service

router = APIRouter(redirect_slashes=False)


@router.get("")
def list_connectors():
    return connector_service.get_all()


# ── Generic platform routes ───────────────────────────────────────────────────
# Adding a new platform = zero router changes

@router.get("/{platform}/auth")
def platform_auth(platform: str):
    """
    For OAuth platforms: redirects to auth URL.
    For API key platforms: returns setup instructions.
    """
    if platform in connector_service.OAUTH_PLATFORMS:
        url = connector_service.get_auth_url(platform)
        return RedirectResponse(url)
    return connector_service.get_auth_info(platform)


@router.get("/{platform}/callback")
def platform_callback(
    platform:          str,
    code:              str  = None,
    error:             str  = None,
    error_description: str  = None,
):
    if error:
        return {"status": "error", "error": error, "description": error_description}
    return connector_service.handle_oauth_callback(platform, code)


@router.post("/{platform}/webhook")
async def platform_webhook(platform: str, request: Request):
    payload = await request.json()
    return connector_service.handle_webhook(platform, payload)