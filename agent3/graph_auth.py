import os
import msal
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

# Do NOT include offline_access, openid, profile — MSAL adds these automatically
SCOPES = [
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/User.Read",
]

def _get_msal_app():
    tenant_id = os.getenv("AZURE_TENANT_ID", "common")
    return msal.ConfidentialClientApplication(
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_credential=os.getenv("AZURE_CLIENT_SECRET"),
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )

def get_auth_url(campaign_id: str) -> str:
    app = _get_msal_app()
    return app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=os.getenv("AZURE_REDIRECT_URI"),
        state=campaign_id,
    )

def handle_callback(code: str, campaign_id: str) -> dict:
    app = _get_msal_app()
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=os.getenv("AZURE_REDIRECT_URI"),
    )
    if "access_token" not in result:
        raise ValueError(f"Auth failed: {result.get('error_description','Unknown error')}")

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()
    cur.execute("""
        UPDATE crm.crm_campaigns
        SET azure_token         = %s,
            azure_refresh_token = %s,
            azure_token_expiry  = NOW() + INTERVAL '1 hour'
        WHERE campaign_id = %s
    """, (
        result["access_token"],
        result.get("refresh_token", ""),
        campaign_id,
    ))
    conn.commit(); cur.close(); conn.close()
    return result

def get_access_token(campaign_id: str) -> str:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT azure_token, azure_refresh_token, azure_token_expiry
        FROM crm.crm_campaigns WHERE campaign_id = %s
    """, (campaign_id,))
    row = cur.fetchone()
    cur.close(); conn.close()

    if not row or not row["azure_token"]:
        raise ValueError("Campaign not authenticated. Click 'Connect Outlook' first.")

    if row["azure_token_expiry"] and \
       row["azure_token_expiry"] < datetime.now(timezone.utc):
        return _refresh_token(campaign_id, row["azure_refresh_token"])

    return row["azure_token"]

def _refresh_token(campaign_id: str, refresh_token: str) -> str:
    app = _get_msal_app()
    result = app.acquire_token_by_refresh_token(refresh_token, scopes=SCOPES)
    if "access_token" not in result:
        raise ValueError("Token refresh failed — please reconnect Outlook")
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()
    cur.execute("""
        UPDATE crm.crm_campaigns
        SET azure_token         = %s,
            azure_refresh_token = %s,
            azure_token_expiry  = NOW() + INTERVAL '1 hour'
        WHERE campaign_id = %s
    """, (result["access_token"], result.get("refresh_token", ""), campaign_id))
    conn.commit(); cur.close(); conn.close()
    return result["access_token"]
