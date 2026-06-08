from fastapi import HTTPException
from core.llm import get_llm, LLMFormat
from core.logger import logger
from utils.uuid import new_id
from domains.campaigns.repository import CampaignRepository 
from domains.campaigns.models import (
    CampaignCreate,
    CampaignUpdate,
    FilterValidationRequest,
)

# ── Filter validation ────────────────────────────────────────────────────────

VALID_TIERS = ["c_suite", "vp", "director", "manager", "individual"]

# Supported platforms — add new ones here without touching any other file
SUPPORTED_PLATFORMS = {"linkedin", "upwork"}


class CampaignService:

    def __init__(self):
        self.repo = CampaignRepository()

    def validate_filters(self, payload: FilterValidationRequest) -> dict:
        checks = {}

        # Management tier — instant, no LLM needed
        if not payload.management_tier:
            checks["management_tier"] = self._check(True, "not set")
        elif payload.management_tier.lower() in VALID_TIERS:
            checks["management_tier"] = self._check(True, "valid tier code")
        else:
            checks["management_tier"] = self._check(
                False, f"Must be one of: {', '.join(VALID_TIERS)}"
            )

        # Domain — regex, no LLM needed
        import re

        if not payload.domain:
            checks["domain"] = self._check(True, "not set")
        elif re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$", payload.domain):
            checks["domain"] = self._check(True, "valid domain format")
        else:
            checks["domain"] = self._check(False, "Use format like: company.com")

        # Industry + region — single LLM call
        checks.update(
            self._validate_with_llm(payload.industry or "", payload.region or "")
        )

        return {
            "valid": all(v.get("valid", True) for v in checks.values()),
            "checks": checks,
        }

    def _validate_with_llm(self, industry: str, region: str) -> dict:
        import json, requests as req

        prompt = (
            "You are a strict data validator for a B2B sales platform.\n"
            "Validate these two fields and respond with ONLY valid JSON, no markdown.\n\n"
            f'industry: "{industry}"\n'
            "Rules: Must be a real business industry (Telecom, Finance, Technology, "
            "Healthcare, Banking, Insurance, Retail, Manufacturing, Real Estate, "
            "Education, Energy, Logistics, Consulting, Pharma, Cybersecurity, Media, "
            "Government, Automotive). Empty string = valid.\n\n"
            f'region: "{region}"\n'
            "Rules: Must be a real country, US state, or major city. "
            "Empty string = valid.\n\n"
            "Respond with ONLY:\n"
            '{"industry":{"valid":true,"reason":"...","suggestion":null},'
            '"region":{"valid":true,"reason":"...","suggestion":null}}'
        )

        try:
            resp = req.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": 150},
                },
                timeout=25,
            )
            text = resp.json().get("response", "").strip()
            s = text.find("{")
            e = text.rfind("}") + 1
            result = json.loads(text[s:e])
            return {
                "industry": result.get("industry", self._check(True, "skipped")),
                "region": result.get("region", self._check(True, "skipped")),
            }
        except Exception as ex:
            logger.error("[campaigns.service] LLM validation failed", error=str(ex))
            return {
                "industry": self._check(False, "Validation timed out — please retry"),
                "region": self._check(False, "Validation timed out — please retry"),
            }

    # ── Campaign CRUD ─────────────────────────────────────────────────────────────

    def get_all(self) -> list:
        return self.repo.get_all()

    def get_by_id(self, campaign_id: str) -> dict:
        row = self.repo.get_by_id(campaign_id)
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return row

    def create(self, payload: CampaignCreate) -> dict:
        # Validate platforms in source_configs before inserting
        self._validate_source_platforms(payload.source_configs)

        record = {
            "campaign_id": new_id(),
            "campaign_name": payload.campaign_name,
            "cron_expression": payload.cron_expression,
            "source_configs": payload.source_configs,
            "is_active": payload.is_active,
            "linkedin_filters": (
                payload.linkedin_filters.dict() if payload.linkedin_filters else {}
            ),
            "filter_match_mode": payload.filter_match_mode or "all",
        }

        row = self.repo.insert(record)

        # Register with scheduler after successful DB insert
        self._sync_scheduler(row, action="register")
        return row

    def update(self, campaign_id: str, payload: CampaignUpdate) -> dict:
        fields = {
            k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None
        }

        if "linkedin_filters" in fields and hasattr(fields["linkedin_filters"], "dict"):
            fields["linkedin_filters"] = fields["linkedin_filters"].dict()

        if "source_configs" in fields:
            self._validate_source_platforms(fields["source_configs"])

        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        row = self.repo.update(campaign_id, fields)
        if not row:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # Sync scheduler — register if active, remove if deactivated
        action = "register" if row.get("is_active") else "remove"
        self._sync_scheduler(row, action=action)
        return row

    def delete(self, campaign_id: str) -> dict:
        deleted = self.repo.delete(campaign_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Campaign not found")

        self._sync_scheduler({"campaign_id": campaign_id}, action="remove")
        return {"status": "deleted", "campaign_id": campaign_id}

    def trigger(self, campaign_id: str) -> dict:
        # Verify campaign exists before triggering
        self.get_by_id(campaign_id)

        import threading
        from services.campaign import run_campaign

        threading.Thread(
            target=run_campaign,
            args=(campaign_id,),
            daemon=True,
        ).start()
        return {"status": "triggered", "campaign_id": campaign_id}

    # ── Private helpers ───────────────────────────────────────────────────────────

    def _check(self, valid: bool, reason: str, suggestion=None) -> dict:
        return {"valid": valid, "reason": reason, "suggestion": suggestion}

    def _validate_source_platforms(self, source_configs: list):
        """
        Raises if any source_config references an unsupported platform.
        Add new platforms to SUPPORTED_PLATFORMS — nothing else changes.
        """
        for src in source_configs:
            platform = (
                src.get("type", "")
                if isinstance(src, dict)
                else getattr(src, "type", "")
            )
            if platform and platform not in SUPPORTED_PLATFORMS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported platform '{platform}'. "
                    f"Supported: {', '.join(sorted(SUPPORTED_PLATFORMS))}",
                )

    def _sync_scheduler(self, campaign: dict, action: str):
        """Keeps scheduler in sync after any DB change."""
        try:
            from scheduler.cron import register_campaign, scheduler

            if action == "register":
                register_campaign(campaign)
            elif action == "remove":
                scheduler.remove_job(str(campaign["campaign_id"]))
        except Exception as e:
            # Scheduler sync failure should never break the API response
            logger.warning(
                "[campaigns.service] Scheduler sync failed", action=action, error=str(e)
            )

campaign_service = CampaignService()