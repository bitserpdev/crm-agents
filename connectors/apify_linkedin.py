import os
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from apify_client import ApifyClient
from connectors.base import BaseConnector

ACTOR_ID = "get-leads/linkedin-scraper"

class ApifyLinkedInConnector(BaseConnector):
    platform_name = "linkedin"

    def __init__(self):
        token = os.getenv("APIFY_API_TOKEN")
        if not token:
            raise ValueError("APIFY_API_TOKEN not set in .env")
        self.client = ApifyClient(token)

    def get_auth_url(self): return ""
    def handle_oauth_callback(self, code): return {"status": "apify uses api token"}

    def poll(self, campaign_config: dict) -> List[Dict[str, Any]]:
        filters    = campaign_config.get("filters", {})
        lf         = campaign_config.get("linkedin_filters", {})
        extract_types = campaign_config.get("extract_types", ["jobs", "profiles"])
        results    = []

        # Build search query from linkedin_filters
        keywords = filters.get("keywords", "")
        if not keywords and lf:
            parts = []
            if lf.get("industry"):        parts.append(lf["industry"])
            if lf.get("management_tier"): parts.append(lf["management_tier"].replace("_", " "))
            keywords = " ".join(parts) if parts else "business professional"

        location = filters.get("location", "")
        if not location and lf.get("region"):
            location = lf["region"]

        merged = {**filters, "keywords": keywords, "location": location}

        if "jobs" in extract_types:
            jobs = self._fetch_jobs(merged)
            results.extend(jobs)
            print(f"[Apify] Got {len(jobs)} jobs")

        if "profiles" in extract_types:
            profiles = self._fetch_profiles(merged)
            results.extend(profiles)
            print(f"[Apify] Got {len(profiles)} profiles")

        return results

    def _fetch_jobs(self, filters: dict) -> list:
        try:
            run = self.client.actor(ACTOR_ID).call(run_input={
                "searchQuery": filters.get("keywords", "software engineer"),
                "location":    filters.get("location", "United States"),
                "maxResults":  filters.get("count", 10),
                "mode":        "jobs",
            })
            items = [i for i in self.client.dataset(run["defaultDatasetId"]).iterate_items()
                     if i.get("resultType") != "bandwidth_report"]
            print(f"[Apify] Raw jobs received: {len(items)}")
            return [self.normalize(i, "job") for i in items if i]
        except Exception as e:
            print(f"[Apify] Job fetch error: {e}")
            return []

    def _fetch_profiles(self, filters: dict) -> list:
        try:
            run = self.client.actor(ACTOR_ID).call(run_input={
                "searchQuery": filters.get("keywords", "software engineer"),
                "location":    filters.get("location", "United States"),
                "maxResults":  filters.get("count", 10),
                "mode":        "search_profiles",
            })
            items = [i for i in self.client.dataset(run["defaultDatasetId"]).iterate_items()
                     if i.get("resultType") != "bandwidth_report"]
            print(f"[Apify] Raw profiles received: {len(items)}")
            return [self.normalize(i, "profile") for i in items if i]
        except Exception as e:
            print(f"[Apify] Profile fetch error: {e}")
            return []

    def normalize(self, raw: dict, data_type: str) -> dict:
        if data_type == "job":
            url = raw.get("jobUrl") or raw.get("url") or \
                  f"https://linkedin.com/jobs/view/{raw.get('id','')}"
            return {
                "type":        "job",
                "platform":    "linkedin",
                "title":       raw.get("title", ""),
                "description": raw.get("description", raw.get("descriptionText", "")),
                "company":     raw.get("companyName", raw.get("company", "")),
                "location":    raw.get("location", ""),
                "posted_at":   raw.get("postedAt", ""),
                "url":         url,
                "raw":         raw,
                "dedup_key":   self.make_dedup_key({"url": url}),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }

        if data_type == "profile":
            url      = raw.get("url", "")
            loc_raw  = raw.get("location_normalized", {}) or {}
            location = (
                loc_raw.get("raw") or
                raw.get("location") or ""
            )
            email = (
                raw.get("email") or
                (raw.get("guessed_emails") or [None])[0] or
                ""
            )
            return {
                "type":          "profile",
                "platform":      "linkedin",
                "name":          raw.get("name") or "",
                "headline":      raw.get("headline") or "",
                "title":         raw.get("current_title") or raw.get("headline") or "",
                "location":      location,
                "company":       raw.get("current_company") or "",
                "current_title": raw.get("current_title") or "",
                "current_company": raw.get("current_company") or "",
                "industry":      raw.get("industry") or "",
                "email":         email,
                "phone":         raw.get("phone") or "",
                "connections":   raw.get("connections_count") or 0,
                "followers":     raw.get("follower_count") or 0,
                "open_to_work":  raw.get("open_to_work") or False,
                "skills":        raw.get("skills") or [],
                "picture_url":   raw.get("picture_url") or "",
                "profile_url":   url,
                "url":           url,
                "company_website": raw.get("company_website") or "",
                "raw":           raw,
                "dedup_key":     self.make_dedup_key({"url": url}),
                "received_at":   datetime.now(timezone.utc).isoformat(),
            }

        return raw

    def make_dedup_key(self, record: dict) -> str:
        identifier = record.get("url") or str(record)
        return hashlib.sha256(identifier.encode()).hexdigest()
