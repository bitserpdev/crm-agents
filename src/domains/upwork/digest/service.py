import json
from datetime import datetime
from typing import Optional

from connectors.registry import get_connector

from .model import DigestConfig, DigestFilters, ManualTriggerRequest
from .repository import repo


class DigestService:

    def get_config(self) -> dict:
        return repo.get_config()

    def save_config(self, config: DigestConfig) -> dict:
        repo.save_config(config.model_dump())
        return {"status": "saved", "config": config.model_dump()}

    def preview_jobs(self, filters: DigestFilters) -> dict:
        jobs = self._fetch_jobs(filters)
        return {"jobs": jobs, "count": len(jobs), "filters": filters.model_dump()}

    def get_preview_jobs(self, limit: int = 20) -> dict:
        config  = repo.get_config()
        filters = config.get("filters", {})

        filter_dict = {
            "query":            filters.get("query", "python developer"),
            "jobType":          filters.get("jobType", ["hourly", "fixed"]),
            "experienceLevel":  filters.get("experienceLevel", ["intermediate", "expert"]),
            "maxJobAge":        {"value": filters.get("maxJobAgeHours", 24), "unit": "hours"},
            "count":            limit,
        }

        try:
            connector = get_connector("upwork")
            jobs      = connector.poll({"filters": filter_dict})
            return {"jobs": jobs[:limit], "count": len(jobs[:limit])}
        except Exception as e:
            return {"error": str(e), "jobs": []}

    def get_status(self) -> dict:
        data = repo.get_status_data()
        return {**data, "config": repo.get_config()}

    def trigger(self, request: ManualTriggerRequest, run_in_background) -> dict:
        def run_digest():
            from agents.agent6.graph import run_agent6

            result = run_agent6(
                filters=request.filters.model_dump() if request.filters else None,
                recipient_email=request.recipient_email,
            )
            repo.store_last_manual({
                "timestamp":  datetime.now().isoformat(),
                "jobs_count": result.get("jobs_count", 0),
                "email_sent": result.get("email_sent", False),
                "errors":     result.get("errors", []),
            })
            print(f"[digest] Manual digest completed: {result.get('jobs_count')} jobs, sent: {result.get('email_sent')}")

        run_in_background(run_digest)
        return {"status": "started", "message": "Digest is being processed. Check logs for results."}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fetch_jobs(self, filters: DigestFilters) -> list:
        filter_dict = {
            "query":           filters.query,
            "jobType":         filters.jobType,
            "experienceLevel": filters.experienceLevel,
            "paymentVerified": filters.paymentVerified,
            "maxJobAge":       {"value": filters.maxJobAgeHours, "unit": "hours"},
            "count":           filters.maxResults,
        }
        if filters.minBudget:
            filter_dict["minBudget"] = filters.minBudget
        if filters.maxBudget:
            filter_dict["maxBudget"] = filters.maxBudget
        if filters.location:
            filter_dict["location"] = filters.location

        try:
            connector = get_connector("upwork")
            jobs      = connector.poll({"filters": filter_dict})
            return jobs[:filters.maxResults]
        except Exception as e:
            print(f"[digest] Preview error: {e}")
            return []


service = DigestService()