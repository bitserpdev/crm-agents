import os
import hashlib
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any
from connectors.base import BaseConnector

LINKEDIN_AUTH_URL  = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_API_BASE  = "https://api.linkedin.com/v2"
OPENID_USERINFO    = "https://api.linkedin.com/v2/userinfo"

CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("LINKEDIN_REDIRECT_URI")

class LinkedInConnector(BaseConnector):
    platform_name = "linkedin"

    def get_auth_url(self) -> str:
        scopes = "openid profile email"
        return (
            f"{LINKEDIN_AUTH_URL}"
            f"?response_type=code"
            f"&client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&scope={scopes.replace(' ', '%20')}"
        )

    def handle_oauth_callback(self, code: str) -> dict:
        resp = requests.post(LINKEDIN_TOKEN_URL, data={
            "grant_type":    "authorization_code",
            "code":          code,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri":  REDIRECT_URI,
        })
        resp.raise_for_status()
        tokens = resp.json()
        self._save_tokens(tokens)
        return tokens

    def _save_tokens(self, tokens: dict):
        import psycopg2
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur  = conn.cursor()
        cur.execute("""
            UPDATE lz_platform_integrations
            SET oauth_access_token  = %s,
                oauth_refresh_token = %s,
                oauth_expires_at    = NOW() + INTERVAL '60 days',
                oauth_scopes        = %s,
                updated_at          = NOW()
            WHERE platform_name = 'linkedin'
        """, (
            tokens.get("access_token"),
            tokens.get("refresh_token"),
            tokens.get("scope", "").split(" "),
        ))
        conn.commit()
        cur.close()
        conn.close()

    def _get_access_token(self) -> str:
        import psycopg2
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur  = conn.cursor()
        cur.execute("""
            SELECT oauth_access_token
            FROM lz_platform_integrations
            WHERE platform_name = 'linkedin'
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row or not row[0]:
            raise ValueError("LinkedIn not authenticated. Please connect via OAuth first.")
        return row[0]

    def poll(self, campaign_config: dict) -> List[Dict[str, Any]]:
        token   = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        results = []

        # Fetch authenticated user profile via OpenID userinfo endpoint
        profile = self._fetch_own_profile(headers)
        if profile:
            results.append(profile)

        return results

    def _fetch_own_profile(self, headers: dict) -> dict:
        try:
            resp = requests.get(OPENID_USERINFO, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            print(f"[LinkedIn] Fetched profile: {data.get('name', 'unknown')}")
            return self.normalize(data, "profile")
        except Exception as e:
            print(f"[LinkedIn] Profile fetch error: {e}")
            return {}

    def normalize(self, raw: dict, data_type: str) -> dict:
        if data_type == "profile":
            profile_id = raw.get("sub", raw.get("id", str(raw)))
            url = f"https://linkedin.com/in/{profile_id}"
            return {
                "type":        "profile",
                "platform":    "linkedin",
                "name":        raw.get("name", ""),
                "email":       raw.get("email", ""),
                "headline":    raw.get("given_name", "") + " " + raw.get("family_name", ""),
                "picture":     raw.get("picture", ""),
                "profile_url": url,
                "url":         url,
                "raw":         raw,
                "dedup_key":   self.make_dedup_key({"url": url}),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
        return raw

    def make_dedup_key(self, record: dict) -> str:
        identifier = record.get("url") or str(record)
        return hashlib.sha256(identifier.encode()).hexdigest()

