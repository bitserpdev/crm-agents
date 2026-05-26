import os
import requests

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "d1243171699d9d4968f20963166539be9805ef88")

def find_domain(company: str) -> str:
    """Find company domain using Hunter.io Domain Search."""
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"company": company, "api_key": HUNTER_API_KEY, "limit": 1},
            timeout=10
        )
        domain = resp.json().get("data", {}).get("domain", "")
        if domain:
            print(f"[Hunter.io] Found domain for '{company}': {domain}")
        return domain
    except Exception as e:
        print(f"[Hunter.io] Domain search error: {e}")
        return ""

def find_email(first_name: str, last_name: str, company: str = "", domain: str = "") -> dict:
    """Find email using Hunter.io Email Finder API."""
    if not domain and company:
        domain = find_domain(company)

    if not domain:
        return {"email": None, "score": 0, "source": None}

    try:
        params = {
            "domain":     domain,
            "first_name": first_name,
            "last_name":  last_name,
            "api_key":    HUNTER_API_KEY,
        }
        resp = requests.get(
            "https://api.hunter.io/v2/email-finder",
            params=params,
            timeout=10
        )
        data = resp.json().get("data", {})
        email = data.get("email")
        score = data.get("score", 0)
        if email:
            print(f"[Hunter.io] Found: {email} (score: {score})")
            return {"email": email, "score": score, "source": "hunter.io"}
        else:
            print(f"[Hunter.io] No email found for {first_name} {last_name} @ {domain}")
            return {"email": None, "score": 0, "source": None}
    except Exception as e:
        print(f"[Hunter.io] Error: {e}")
        return {"email": None, "score": 0, "source": None}

def search_emails(domain: str, limit: int = 10) -> list:
    """Get all emails for a domain."""
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": limit},
            timeout=10
        )
        emails = resp.json().get("data", {}).get("emails", [])
        print(f"[Hunter.io] Found {len(emails)} emails for {domain}")
        return emails
    except Exception as e:
        print(f"[Hunter.io] Search error: {e}")
        return []
