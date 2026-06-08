import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from core.redis import get_redis


class DigestRepository:

    def _r(self):
        return get_redis()

    def get_config(self) -> dict:
        raw = self._r().get("op:digest:config")
        if raw:
            return json.loads(raw)
        return {
            "enabled": True,
            "recipient_email": os.getenv("UPWORK_DIGEST_EMAIL", ""),
            "filters": {
                "query":            os.getenv("UPWORK_DIGEST_QUERY", "python developer data engineer"),
                "jobType":          ["hourly", "fixed"],
                "experienceLevel":  ["intermediate", "expert"],
                "minBudget":        None,
                "maxBudget":        None,
                "location":         None,
                "paymentVerified":  False,
                "maxJobAgeHours":   24,
                "maxResults":       50,
            },
            "send_time_hour":   0,
            "send_time_minute": 5,
        }

    def save_config(self, config: dict):
        self._r().set("op:digest:config", json.dumps(config), ex=86400 * 30)

    def store_last_manual(self, data: dict):
        self._r().set("op:digest:last_manual", json.dumps(data), ex=86400)

    def get_status_data(self) -> dict:
        r     = self._r()
        today = datetime.now().strftime("%Y-%m-%d")

        last_run    = r.get("op:digest:last_run")
        last_count  = r.get(f"op:digest:count:{today}")
        last_manual = r.get("op:digest:last_manual")

        stats = []
        for i in range(7):
            date  = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            count = r.get(f"op:digest:count:{date}")
            stats.append({"date": date, "jobs_count": int(count) if count else 0})

        return {
            "last_run_date":     last_run,
            "today_jobs_count":  int(last_count) if last_count else 0,
            "last_manual":       json.loads(last_manual) if last_manual else None,
            "weekly_stats":      stats,
        }


repo = DigestRepository()