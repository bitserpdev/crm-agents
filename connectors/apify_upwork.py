import os
import json
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any
from apify_client import ApifyClient
from connectors.base import BaseConnector

# Apify actor for Upwork job scraping
UPWORK_ACTOR_ID = "ninz/upwork-job-extractor"

class UpworkConnector(BaseConnector):
    platform_name = "upwork"

    def __init__(self):
        token = os.getenv("APIFY_API_TOKEN")
        if not token:
            raise ValueError("APIFY_API_TOKEN not set in .env")
        self.client = ApifyClient(token)

    def get_auth_url(self) -> str:
        # Upwork doesn't require OAuth for scraping via Apify
        return ""

    def handle_oauth_callback(self, code: str) -> dict:
        return {"status": "apify uses api token"}

    
    def _match_fixed_price(self, job: dict, min_budget: float, max_budget: float) -> bool:
        price = str(job.get("price", "")).strip()
        if not price or price.lower() == "not specified" or "-" not in price:
            return False
        try:
            low, high = price.split("-")
            low = float(low.replace("$", "").strip())
            high = float(high.replace("$", "").strip())
            return (
                min_budget <= low <= max_budget
                or min_budget <= high <= max_budget
                or (low <= min_budget and high >= max_budget)
            )
        except Exception:
            return False

    def _match_hourly_rate(self, job: dict, min_rate: float, max_rate: float) -> bool:
        price = str(job.get("price", "")).strip()
        if not price or price.lower() == "not specified":
            return False
        try:
            # Handle range format "$18.0-$45.0" — match if ranges overlap
            if "-" in price:
                low, high = price.split("-")
                low = float(low.replace("$", "").strip())
                high = float(high.replace("$", "").strip())
                return low <= max_rate and high >= min_rate
            else:
                value = float(price.replace("$", "").strip())
                return min_rate <= value <= max_rate
        except Exception:
            return False

    def poll(self, campaign_config: dict) -> List[Dict[str, Any]]:

        filters = campaign_config.get("filters", {})
        query = filters.get("query", "")

        if not query:
            print("[Upwork] No query provided, skipping")
            return []

        # Build actor input
        actor_input = {
            "query": query,
        }

        # Location filter
        if filters.get("location"):
            actor_input["location"] = [filters["location"]]

        # Experience level mapping
        exp_map = {
            "entry": "entry",
            "intermediate": "intermediate",
            "expert": "expert"
        }
        exp_levels = filters.get("experienceLevel", [])
        if exp_levels:
            actor_input["experienceLevel"] = [exp_map.get(l, l) for l in exp_levels]

        # Job type
        job_type = filters.get("jobType")
        if job_type:
            actor_input["jobType"] = [job_type]

        # Client history
        client_history = filters.get("clientHistory", [])
        if client_history:
            actor_input["clientHistory"] = client_history

        # Payment verified
        payment_verified = filters.get("paymentVerified", False)
        if payment_verified:
            actor_input["paymentVerified"] = True

        # Max job age
        max_age = filters.get("maxJobAge", {})
        if max_age and max_age.get("value"):
            actor_input["maxJobAge"] = max_age


        count = campaign_config.get("count", 20)
        actor_input["limit"] = count

        try:
            run = self.client.actor(UPWORK_ACTOR_ID).call(run_input=actor_input)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())

            print(json.dumps(items[0], indent=2, default=str))

            print(f"[Upwork] Received {len(items)} jobs")

            filtered_items = items

            job_type = filters.get("jobType")

            min_budget = filters.get("minBudget")
            max_budget = filters.get("maxBudget")

            # Hourly budget filter
            if (
                job_type == "hourly"
                and filters.get("minBudget") is not None
                and filters.get("maxBudget") is not None
            ):
                min_rate = float(filters["minBudget"])
                max_rate = float(filters["maxBudget"])

                filtered_items = [
                    job
                    for job in filtered_items
                    if self._match_hourly_rate(
                        job,
                        min_rate,
                        max_rate
                    )
                ]

                print(
                    f"[Upwork] Hourly filter: "
                    f"{len(filtered_items)} jobs remaining"
                )

            # Fixed price filter
            elif (
                job_type == "fixed-price"
                and filters.get("minBudget") is not None
                and filters.get("maxBudget") is not None
            ):
                min_budget = float(filters["minBudget"])
                max_budget = float(filters["maxBudget"])

                filtered_items = [
                    job
                    for job in filtered_items
                    if self._match_fixed_price(
                        job,
                        min_budget,
                        max_budget
                    )
                ]

                print(
                    f"[Upwork] Fixed filter: "
                    f"{len(filtered_items)} jobs remaining"
                )

            return [
                self.normalize(item, "job")
                for item in filtered_items
                if item
            ]

        except Exception as e:
            print(f"[Upwork] Actor error: {e}")
            return []

    def normalize(self, raw: dict, data_type: str = "job") -> dict:
        if data_type != "job":
            return raw

        # Extract job URL – Apify actor provides "url" field
        job_url = raw.get("url") or raw.get("jobUrl") or ""
        if not job_url:
            # Fallback: construct from job ID if available
            job_id = raw.get("id") or raw.get("jobId")
            if job_id:
                job_url = f"https://www.upwork.com/jobs/{job_id}"
            else:
                job_url = f"https://www.upwork.com/jobs/{raw.get('title','')}-{raw.get('postedDate','')}".replace(" ", "-")

        # Generate unique dedup key from URL
        dedup_key = self.make_dedup_key({"url": job_url})

        return {
            "type": "upwork_job",
            "platform": "upwork",
            "title": raw.get("title", ""),
            "description": raw.get("description", raw.get("descriptionText", "")),
            "budget": raw.get("budget", {}),
            "client": {
                "name": raw.get("client", {}).get("name"),
                "hire_rate": raw.get("client", {}).get("hireRate"),
                "total_spent": raw.get("client", {}).get("totalSpent"),
                "country": raw.get("client", {}).get("country"),
                "rating": raw.get("client", {}).get("rating"),
            },
            "skills": raw.get("skills", []),
            "experience_level": raw.get("experienceLevel"),
            "proposals_count": raw.get("proposalsCount"),
            "posted_date": raw.get("postedDate"),
            "url": job_url,
            "raw": raw,
            "dedup_key": dedup_key,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

    def make_dedup_key(self, record: dict) -> str:
        identifier = record.get("url") or str(record)
        if not identifier:
            identifier = str(record)
        return hashlib.sha256(identifier.encode()).hexdigest()