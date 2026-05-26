import os
import requests

SNOV_CLIENT_ID     = os.getenv("SNOV_CLIENT_ID", "a02ef6b2097d5af4220b5667990cec4a")
SNOV_CLIENT_SECRET = os.getenv("SNOV_CLIENT_SECRET", "f84307ec381cd35de3e4ca47b03aa0bb")

def get_access_token() -> str:
    resp = requests.post(
        "https://api.snov.io/v1/oauth/access_token",
        json={
            "grant_type":    "client_credentials",
            "client_id":     SNOV_CLIENT_ID,
            "client_secret": SNOV_CLIENT_SECRET,
        },
        timeout=10
    )
    return resp.json().get("access_token", "")


def search_prospects(job_title: str, industry: str, location: str, limit: int = 10) -> list:
    """
    Search LinkedIn prospects by job title, industry, location.
    Returns list of prospects with name, email, title, company, location.
    """
    token = get_access_token()
    if not token:
        print("[Snov.io] Failed to get access token")
        return []

    try:
        params = {
            "access_token": token,
            "rows":         limit,
            "position":     job_title,
            "industry":     industry,
            "country_code": _get_country_code(location),
        }
        # Remove empty params
        params = {k: v for k, v in params.items() if v}

        resp = requests.get(
            "https://api.snov.io/v1/get-prospects-by-filters",
            params=params,
            timeout=15
        )
        data = resp.json()
        print(f"[Snov.io] search status: {resp.status_code} — {len(data.get('data', {}).get('prospects', []))} prospects")
        return data.get("data", {}).get("prospects", [])
    except Exception as e:
        print(f"[Snov.io] search error: {e}")
        return []


def get_emails_for_profile(linkedin_url: str) -> dict:
    """Get emails for a LinkedIn profile URL."""
    token = get_access_token()
    if not token:
        return {}
    try:
        resp = requests.post(
            "https://api.snov.io/v1/get-emails-from-url",
            json={"access_token": token, "url": linkedin_url},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        print(f"[Snov.io] email lookup error: {e}")
        return {}


def _get_country_code(location: str) -> str:
    """Convert location name to country code."""
    mapping = {
        "united states": "US", "us": "US", "usa": "US",
        "uk": "GB", "united kingdom": "GB",
        "canada": "CA", "australia": "AU",
        "germany": "DE", "france": "FR",
        "india": "IN", "singapore": "SG",
        "uae": "AE", "dubai": "AE",
        "pakistan": "PK", "netherlands": "NL",
    }
    return mapping.get(location.lower().strip(), "US")
