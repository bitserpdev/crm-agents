import os
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from apify_client import ApifyClient
from connectors.base import BaseConnector
from core.database import get_conn, release_conn, get_dict_cursor
from core.logger import logger

ACTOR_ID = "get-leads/linkedin-scraper"


class ApifyLinkedInConnector(BaseConnector):
    platform_name = "linkedin"

    def __init__(self):
        token = os.getenv("APIFY_API_TOKEN")
        if not token:
            raise ValueError("APIFY_API_TOKEN not set in .env")
        self.client = ApifyClient(token)

    def get_auth_url(self):
        return ""

    def handle_oauth_callback(self, code):
        return {"status": "apify uses api token"}

    def _get_cookies(self) -> str:
        li_at = os.getenv("LINKEDIN_LI_AT_COOKIE", "")
        if not li_at:
            logger.info("[Apify] No LinkedIn cookie set")
            return ""
        return f"li_at={li_at}"

    def poll(self, campaign_config: dict) -> List[Dict[str, Any]]:
        filters = campaign_config.get("filters", {})
        lf = campaign_config.get("linkedin_filters", {})
        extract_types = campaign_config.get("extract_types", ["jobs", "profiles"])
        results = []

        keywords = filters.get("keywords", "")
        if not keywords and lf:
            parts = []
            if lf.get("industry"):
                parts.append(lf["industry"])
            if lf.get("management_tier"):
                parts.append(lf["management_tier"].replace("_", " "))
            keywords = " ".join(parts) if parts else "business professional"

        location = filters.get("location", "")
        if not location and lf.get("region"):
            location = lf["region"]

        merged = {**filters, "keywords": keywords, "location": location}

        if "jobs" in extract_types:
            jobs = self._fetch_jobs(merged)
            results.extend(jobs)
            logger.info(f"[Apify] Got {len(jobs)} jobs")

        if "profiles" in extract_types:
            profiles = self._fetch_profiles(merged)
            results.extend(profiles)
            logger.info(f"[Apify] Got {len(profiles)} profiles")

        return results

    def _fetch_jobs(self, filters: dict) -> list:
        try:
            run = self.client.actor(ACTOR_ID).call(
                run_input={
                    "searchQuery": filters.get("keywords", "software engineer"),
                    "location": filters.get("location", "United States"),
                    "maxResults": filters.get("count", 10),
                    "mode": "jobs",
                    "loginCookies": self._get_cookies(),
                }
            )
            items = [
                i
                for i in self.client.dataset(run["defaultDatasetId"]).iterate_items()
                if i.get("resultType") != "bandwidth_report"
            ]
            logger.info(f"[Apify] Raw jobs received: {len(items)}")
            return [self.normalize(i, "job") for i in items if i]
        except Exception as e:
            logger.error(f"[Apify] Job fetch error: {e}")
            return []

    def _fetch_profiles(self, filters: dict) -> list:
        try:
            li_at = os.getenv("LINKEDIN_LI_AT_COOKIE", "")
            run_input = {
                "searchQuery": filters.get("keywords", "software engineer"),
                "location": filters.get("location", "United States"),
                "maxResults": filters.get("count", 10),
                "mode": "search_profiles",
                "discoverEmails": True,
            }
            if li_at:
                run_input["loginCookies"] = f"li_at={li_at}"
                logger.info(f"[Apify] Using LinkedIn cookie: {li_at[:20]}...")
            run = self.client.actor(ACTOR_ID).call(run_input=run_input)
            items = [
                i
                for i in self.client.dataset(run["defaultDatasetId"]).iterate_items()
                if i.get("resultType") != "bandwidth_report"
                and not i.get("error")
                and i.get("name")
            ]
            logger.info(f"[Apify] Raw profiles received: {len(items)}")
            return [self.normalize(i, "profile") for i in items if i]
        except Exception as e:
            logger.error(f"[Apify] Profile fetch error: {e}")
            return []

    def normalize(self, raw: dict, data_type: str) -> dict:
        if data_type == "job":
            url = (
                raw.get("jobUrl")
                or raw.get("url")
                or f"https://linkedin.com/jobs/view/{raw.get('id','')}"
            )
            return {
                "type": "job",
                "platform": "linkedin",
                "title": raw.get("title", ""),
                "description": raw.get("description", raw.get("descriptionText", "")),
                "company": raw.get("companyName", raw.get("company", "")),
                "location": raw.get("location", ""),
                "posted_at": raw.get("postedAt", ""),
                "url": url,
                "raw": raw,
                "dedup_key": self.make_dedup_key({"url": url}),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }

        if data_type == "profile":
            # Try multiple URL fields
            url = (
                raw.get("url")
                or raw.get("linkedinUrl")
                or raw.get("linkedin_url")
                or raw.get("profileUrl")
                or ""
            )
            # Try multiple location fields
            loc_raw = raw.get("location_normalized", {}) or {}
            location = (
                loc_raw.get("raw") or raw.get("location") or raw.get("city") or ""
            )
            # Try multiple email fields
            email = (
                raw.get("email")
                or raw.get("emailAddress")
                or (raw.get("guessed_emails") or [None])[0]
                or (raw.get("emails") or [{}])[0].get("email")
                or ""
            )
            # Try multiple name fields
            name = (
                raw.get("name")
                or raw.get("fullName")
                or f"{raw.get('firstName','')} {raw.get('lastName','')}".strip()
                or ""
            )
            # Try multiple company fields
            company = (
                raw.get("current_company")
                or raw.get("currentCompany")
                or raw.get("company")
                or ""
            )
            # Try multiple title fields
            title = (
                raw.get("current_title")
                or raw.get("currentTitle")
                or raw.get("headline")
                or raw.get("title")
                or ""
            )
            # Debug raw keys
            logger.info(f"[Apify] Raw keys: {list(raw.keys())[:15]}")
            return {
                "type": "profile",
                "platform": "linkedin",
                "name": name,
                "headline": raw.get("headline") or title,
                "title": title,
                "location": location,
                "company": company,
                "current_title": title,
                "current_company": company,
                "industry": raw.get("industry") or raw.get("companyIndustry") or "",
                "email": email,
                "phone": raw.get("phone") or raw.get("phoneNumber") or "",
                "connections": raw.get("connections_count")
                or raw.get("connectionsCount")
                or 0,
                "followers": raw.get("follower_count")
                or raw.get("followersCount")
                or 0,
                "open_to_work": raw.get("open_to_work")
                or raw.get("openToWork")
                or False,
                "skills": raw.get("skills") or [],
                "picture_url": raw.get("picture_url")
                or raw.get("profilePicture")
                or "",
                "profile_url": url,
                "url": url,
                "company_website": raw.get("company_website")
                or raw.get("companyWebsite")
                or "",
                "raw": raw,
                "dedup_key": self.make_dedup_key({"url": url}),
                "received_at": datetime.now(timezone.utc).isoformat(),
            }

        return raw

    def make_dedup_key(self, record: dict) -> str:
        identifier = record.get("url") or str(record)
        return hashlib.sha256(identifier.encode()).hexdigest()
