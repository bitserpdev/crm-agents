import threading
from fastapi import HTTPException
from core.llm import get_llm, LLMFormat
from core.logger import logger
from services.email import email_service, EmailMessage
from utils.uuid import new_id
from .model import EmailCampaignCreate, SendCustomizedEmailRequest
from .repository import repo

llm = get_llm(fmt=LLMFormat.JSON)

_preview_jobs: dict = {}


class CampaignService:

    # ── Campaign CRUD ─────────────────────────────────────────────────────────

    def list_email_campaigns(self) -> list[dict]:
        return repo.list_email_campaigns()

    def create_email_campaign(self, payload: EmailCampaignCreate) -> dict:
        user_id = repo.get_system_user_id()
        if not user_id:
            raise HTTPException(status_code=500, detail="No system user found")
        status = "scheduled" if payload.scheduled_at else "draft"
        try:
            return repo.create_email_campaign(payload.model_dump(), user_id, status)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def delete_email_campaign(self, campaign_id: str) -> dict:
        if not repo.delete_email_campaign(campaign_id):
            raise HTTPException(status_code=404, detail="Campaign not found")
        return {"deleted": campaign_id}

    # ── Send customized ───────────────────────────────────────────────────────

    def send_customized(self, request: SendCustomizedEmailRequest) -> dict:
        contacts = {
            c["contact_id"]: c
            for c in repo.get_contacts_for_send(request.contact_ids)
        }
        sent = failed = 0
        failed_emails = []

        for contact_id in request.contact_ids:
            contact = contacts.get(contact_id)
            if not contact or not contact.get("email"):
                failed += 1
                failed_emails.append(f"Contact {contact_id} not found")
                continue

            ctx = self._build_context(contact)
            success = email_service.send(EmailMessage(
                to=contact["email"],
                subject=self._personalize(request.subject, ctx),
                body_text=self._personalize(request.body, ctx),
                body_html=self._personalize(request.html_body, ctx),
            ))

            if success:
                sent += 1
            else:
                failed += 1
                failed_emails.append(contact["email"])

        return {"sent": sent, "failed": failed,
                "failed_emails": failed_emails[:10]}

    # ── Preview ───────────────────────────────────────────────────────────────

    def start_preview(self, campaign_id: str,
                      contact_id: str | None = None) -> dict:
        campaign = repo.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404,
                                detail=f"Campaign {campaign_id} not found")

        sample  = repo.get_contact_for_preview(contact_id) if contact_id else None
        audience = repo.get_sample_audience()

        ctx = {
            "name":      f"{sample.get('first_name','')} {sample.get('last_name','')}".strip()
                         if sample else "there",
            "job_title": (sample or audience).get("job_title", "Data Engineer"),
            "company":   sample.get("company_name", "your company") if sample else "[Company]",
            "industry":  (sample or audience).get("industry", "technology"),
        }

        job_id = new_id()
        _preview_jobs[job_id] = {"status": "pending"}
        threading.Thread(
            target=self._run_preview,
            args=(job_id, campaign, ctx),
            daemon=True,
        ).start()
        return {"job_id": job_id}

    def get_preview_job(self, job_id: str) -> dict:
        return _preview_jobs.get(job_id, {"status": "not_found"})

    # ── Replies / Recipients / Tracking ──────────────────────────────────────

    def get_replies(self, campaign_id: str | None = None) -> list:
        return repo.get_replies(campaign_id)

    def get_run_recipients(self, run_id: str) -> list:
        return repo.get_run_recipients(run_id)

    def track_open(self, recipient_id: str):
        repo.track_open(recipient_id)

    # ── Private ───────────────────────────────────────────────────────────────

    def _run_preview(self, job_id: str, campaign: dict, ctx: dict):
        try:
            import json
            from agents.agent3.prompts import PERSONALIZE_PROMPT
            from utils.llm_parser import extract_json_from_llm

            prompt   = PERSONALIZE_PROMPT.replace("{company_name}", ctx["company"])
            response = llm.invoke([
                ("system", prompt),
                ("human", json.dumps({
                    "contact": {
                        "name":      ctx["name"],
                        "job_title": ctx["job_title"],
                        "company":   ctx["company"],
                        "industry":  ctx["industry"],
                    },
                    "campaign_service": campaign.get("service_description", ""),
                    "from_email":       campaign.get("from_address", ""),
                })),
            ])

            result = extract_json_from_llm(response.content.strip())
            if not result or not all(k in result for k in ("subject","text","html")):
                raise ValueError("Invalid LLM response")

            _preview_jobs[job_id] = {"status": "done", "email": result}

        except Exception as e:
            logger.error("[email.service] Preview failed", error=str(e))
            _preview_jobs[job_id] = {"status": "done",
                                     "email": self._fallback_preview(ctx)}

    def _fallback_preview(self, ctx: dict) -> dict:
        return {
            "subject": f"Quick question for {ctx['job_title']}s at {ctx['company']}",
            "text": (
                f"Hi {ctx['name']},\n\nAs a {ctx['job_title']} at {ctx['company']}, "
                f"you're likely managing complex data workflows. We help {ctx['industry']} "
                f"companies build reliable ETL pipelines and BI dashboards.\n\n"
                f"Would a 15-minute call be worth your time?\n\n"
                f"Best,\nBITS Global Consulting"
            ),
            "html": (
                f"<p>Hi {ctx['name']},</p>"
                f"<p>As a <strong>{ctx['job_title']}</strong> at "
                f"<strong>{ctx['company']}</strong>, you're likely managing complex "
                f"data workflows. We help {ctx['industry']} companies build reliable "
                f"ETL pipelines and BI dashboards.</p>"
                f"<p>Would a 15-minute call be worth your time?</p>"
                f"<p>Best,<br><strong>BITS Global Consulting</strong></p>"
            ),
        }

    def _build_context(self, contact: dict) -> dict:
        return {
            "Name":      f"{contact.get('first_name','')} {contact.get('last_name','')}".strip(),
            "name":      contact.get("first_name", ""),
            "Company":   contact.get("company_name", "your company"),
            "company":   contact.get("company_name", "your company"),
            "Job Title": contact.get("job_title", "professional"),
            "job title": contact.get("job_title", "professional"),
        }

    def _personalize(self, text: str, ctx: dict) -> str:
        for key, val in ctx.items():
            text = text.replace(f"[{key}]", val)
        return text


service = CampaignService()