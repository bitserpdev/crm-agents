import os, uuid
import traceback
import psycopg2, psycopg2.extras
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional
from psycopg2.extras import Json
import psycopg2
import psycopg2.extras
from typing import List
from utils.llm_parser import extract_json_from_llm
from langchain_ollama import ChatOllama
from pydantic import BaseModel

class EmailOutput(BaseModel):
    subject: str
    text: str
    html: str

llm = ChatOllama(
    model="llama3.2",
    base_url="http://localhost:11434",
    temperature=0.2,
    timeout=1000,
    num_predict=800,
    format="json",
)

router = APIRouter(redirect_slashes=False)


def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


# ── Campaign CRUD ─────────────────────────────────────────────────────────────
class CampaignCreate(BaseModel):
    campaign_name: str
    service_description: str
    from_address: str
    filter_region: Optional[str] = None
    filter_industry: Optional[str] = None
    filter_company_size: Optional[str] = None
    filter_min_score: Optional[int] = 0
    filter_max_score: Optional[int] = 100
    filter_stage: Optional[str] = None
    scheduled_at: Optional[str] = None


class SendCustomizedEmailRequest(BaseModel):
    campaign_id: str
    contact_ids: List[str]
    subject: str
    body: str
    html_body: str


@router.post("/campaigns/send-customized")
def send_customized_email(request: SendCustomizedEmailRequest):
    """Send customized email to multiple contacts."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import psycopg2

    print(f"[DEBUG] Sending customized email to {len(request.contact_ids)} contacts")

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()

    sent_count = 0
    failed_count = 0
    failed_emails = []

    for contact_id in request.contact_ids:
        # Get contact details
        cur.execute(
            """
            SELECT c.email, c.first_name, c.last_name, c.job_title, co.company_name
            FROM crm.crm_contacts c
            LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
            WHERE c.contact_id = %s
        """,
            (contact_id,),
        )
        contact = cur.fetchone()

        if not contact or not contact[0]:
            failed_count += 1
            failed_emails.append(f"Contact {contact_id} not found")
            continue

        email = contact[0]
        first_name = contact[1] or ""
        last_name = contact[2] or ""
        job_title = contact[3] or "professional"
        company = contact[4] or "your company"
        full_name = f"{first_name} {last_name}".strip()

        # Personalize the email
        personalized_body = request.body
        personalized_body = personalized_body.replace("[Name]", full_name)
        personalized_body = personalized_body.replace("[name]", first_name)
        personalized_body = personalized_body.replace("[Company]", company)
        personalized_body = personalized_body.replace("[company]", company)
        personalized_body = personalized_body.replace("[Job Title]", job_title)
        personalized_body = personalized_body.replace("[job title]", job_title)

        personalized_html = request.html_body
        personalized_html = personalized_html.replace("[Name]", full_name)
        personalized_html = personalized_html.replace("[name]", first_name)
        personalized_html = personalized_html.replace("[Company]", company)
        personalized_html = personalized_html.replace("[company]", company)
        personalized_html = personalized_html.replace("[Job Title]", job_title)
        personalized_html = personalized_html.replace("[job title]", job_title)

        personalized_subject = request.subject
        personalized_subject = personalized_subject.replace("[Name]", full_name)
        personalized_subject = personalized_subject.replace("[name]", first_name)
        personalized_subject = personalized_subject.replace("[Job Title]", job_title)

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = personalized_subject
            msg["From"] = os.getenv("SMTP_USER")
            msg["To"] = email

            msg.attach(MIMEText(personalized_body, "plain"))
            msg.attach(MIMEText(personalized_html, "html"))

            with smtplib.SMTP(
                os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))
            ) as server:
                server.starttls()
                server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
                server.sendmail(os.getenv("SMTP_USER"), email, msg.as_string())

            sent_count += 1
            print(f"✓ Sent to {email}")

        except Exception as e:
            failed_count += 1
            failed_emails.append(f"{email}: {str(e)}")
            print(f"✗ Failed to send to {email}: {e}")

    cur.close()
    conn.close()

    return {
        "sent": sent_count,
        "failed": failed_count,
        "failed_emails": failed_emails[:10],  # Return first 10 failures
    }


@router.get("/campaigns")
def list_campaigns():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT c.*,
               (SELECT COUNT(*) FROM crm.crm_campaign_runs r
                WHERE r.campaign_id = c.campaign_id) AS run_count,
               (SELECT SUM(sent_count) FROM crm.crm_campaign_runs r
                WHERE r.campaign_id = c.campaign_id) AS total_sent
        FROM crm.crm_campaigns c
        WHERE c.campaign_type = 'email'
        ORDER BY c.created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/campaigns")
def create_campaign(payload: CampaignCreate):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Get system user
    cur.execute("SELECT user_id FROM crm.crm_users LIMIT 1")
    user = cur.fetchone()
    campaign_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO crm.crm_campaigns (
            campaign_id, campaign_name, campaign_type,
            campaign_status, schedule_type, from_address,
            service_description, filter_region, filter_industry,
            filter_company_size, filter_min_score, filter_max_score,
            filter_stage, scheduled_at, created_by
        ) VALUES (%s,%s,'email','draft','manual',%s,%s,%s,%s,%s,%s,%s,%s,%s::timestamptz,%s)
        RETURNING *
    """,
        (
            campaign_id,
            payload.campaign_name,
            payload.from_address,
            payload.service_description,
            payload.filter_region,
            payload.filter_industry,
            payload.filter_company_size,
            payload.filter_min_score,
            payload.filter_max_score,
            payload.filter_stage,
            payload.scheduled_at or None,
            str(user["user_id"]),
        ),
    )
    row = dict(cur.fetchone())
    conn.commit()
    cur.close()
    conn.close()
    return row


class CampaignUpdate(BaseModel):
    campaign_name: str
    service_description: str
    from_address: str
    filter_region: Optional[str] = None
    filter_industry: Optional[str] = None
    filter_company_size: Optional[str] = None
    filter_min_score: Optional[int] = 0
    filter_max_score: Optional[int] = 100
    filter_stage: Optional[str] = None
    scheduled_at: Optional[str] = None


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, payload: CampaignUpdate):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        UPDATE crm.crm_campaigns SET
            campaign_name       = %s,
            service_description = %s,
            from_address        = %s,
            filter_region       = %s,
            filter_industry     = %s,
            filter_company_size = %s,
            filter_min_score    = %s,
            filter_max_score    = %s,
            filter_stage        = %s,
            scheduled_at        = %s::timestamptz,
            updated_at          = NOW()
        WHERE campaign_id = %s
        RETURNING *
    """,
        (
            payload.campaign_name,
            payload.service_description,
            payload.from_address,
            payload.filter_region,
            payload.filter_industry,
            payload.filter_company_size,
            payload.filter_min_score,
            payload.filter_max_score,
            payload.filter_stage,
            payload.scheduled_at or None,
            campaign_id,
        ),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not row:
        return {"error": "Campaign not found"}
    return dict(row)


@router.post("/campaigns/{campaign_id}/preview-contacts")
def preview_contacts(campaign_id: str, filters: dict = None):
    """Preview contacts that match the campaign filters."""

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Build query with proper NULL handling
    query = """
    SELECT
        c.contact_id,
        c.first_name,
        c.last_name,
        c.email,
        c.job_title,
        c.lifecycle_stage,
        co.company_name,
        co.industry,
        co.country,
        co.country_code,
        co.company_size,
        COALESCE(s.overall_score, 0) as overall_score
    FROM crm.crm_contacts c
    LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
    LEFT JOIN crm.crm_contact_scores s ON s.contact_id = c.contact_id
    WHERE c.is_suppressed = FALSE
      AND c.gdpr_consent = TRUE
      AND c.email IS NOT NULL
      AND c.email NOT LIKE '%%placeholder%%'
    """

    params = []

    if filters:
        if filters.get("filter_region"):
            # Use COALESCE to handle NULL values
            query += " AND (UPPER(COALESCE(co.country_code, '')) = UPPER(%s) OR UPPER(COALESCE(co.country, '')) LIKE %s)"
            params.append(filters["filter_region"])
            params.append(f"%{filters['filter_region']}%")

        if filters.get("filter_industry") and filters["filter_industry"]:
            query += " AND LOWER(COALESCE(co.industry, '')) LIKE %s"
            params.append(f"%{filters['filter_industry'].lower()}%")

        if filters.get("filter_company_size") and filters["filter_company_size"]:
            query += " AND COALESCE(co.company_size, '') = %s"
            params.append(filters["filter_company_size"])

        if filters.get("filter_stage") and filters["filter_stage"]:
            query += " AND c.lifecycle_stage = %s"
            params.append(filters["filter_stage"])

        if filters.get("filter_min_score") is not None:
            query += " AND COALESCE(s.overall_score, 0) >= %s"
            params.append(int(filters["filter_min_score"]))

        if filters.get("filter_max_score") is not None:
            query += " AND COALESCE(s.overall_score, 0) <= %s"
            params.append(int(filters["filter_max_score"]))

    query += " ORDER BY COALESCE(s.overall_score, 0) DESC LIMIT 100"

    try:
        print("Executing query...")
        cur.execute(query, tuple(params))
        print("Query executed successfully")
        contacts = cur.fetchall()
        print(f"Retrieved {len(contacts)} rows")
    except Exception as e:
        traceback.print_exc()
        print(f"[ERROR] Database error: {e}")
        contacts = []
    finally:
        cur.close()
        conn.close()

    return {"contacts": [dict(c) for c in contacts]}


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM crm.crm_campaigns WHERE campaign_id = %s", (campaign_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"deleted": campaign_id}


_running_campaigns = set()


@router.post("/campaigns/{campaign_id}/trigger")
def trigger_campaign(campaign_id: str):
    if campaign_id in _running_campaigns:
        return {"status": "already_running", "campaign_id": campaign_id}

    import threading

    def run():
        import uuid as _uuid

        _running_campaigns.add(campaign_id)
        try:
            from agent3.graph import build_agent3_graph

            graph = build_agent3_graph()
            graph.invoke(
                {
                    "campaign_id": campaign_id,
                    "run_id": "",
                    "campaign": {},
                    "contacts": [],
                    "personalized": [],
                    "sent": [],
                    "failed": [],
                    "errors": [],
                    "agent_trace_id": str(_uuid.uuid4()),
                    "run_status": "running",
                    "stats": {},
                }
            )
        finally:
            _running_campaigns.discard(campaign_id)

    threading.Thread(target=run, daemon=True).start()
    return {"status": "triggered", "campaign_id": campaign_id}


# In-memory job store for preview generation
_preview_jobs = {}


@router.post("/campaigns/{campaign_id}/preview/start")
def start_preview(campaign_id: str, contact_id: Optional[str] = None):
    import json, requests as req, threading, uuid as _uuid

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM crm.crm_campaigns WHERE campaign_id=%s", (campaign_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return {"error": f"Campaign {campaign_id} not found"}

    campaign = dict(row)

    sample_contact = None

    if contact_id:
        # Specific contact preview — use their real details
        cur.execute(
            """
            SELECT c.*, co.company_name, co.industry, co.domain, co.country, co.city, co.company_size
            FROM crm.crm_contacts c
            LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
            WHERE c.contact_id = %s
        """,
            (contact_id,),
        )
        row = cur.fetchone()
        sample_contact = dict(row) if row else None

        contact_name = f"{sample_contact.get('first_name', '')} {sample_contact.get('last_name', '')}".strip()
        contact_job_title = sample_contact.get("job_title", "professional")
        contact_company = sample_contact.get("company_name", "your company")
        contact_industry = sample_contact.get("industry", "technology")

    else:
        # Generic preview — only pull industry/job_title for context
        # DO NOT use a real person's name or company
        cur.execute("""
            SELECT co.industry, c.job_title
            FROM crm.crm_contacts c
            LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
            WHERE co.industry IS NOT NULL
            LIMIT 1
        """)

    row = cur.fetchone()
    audience = dict(row) if row else {}

    contact_name = "[Name]"  # ← placeholder, not a real person
    contact_job_title = audience.get("job_title") or "Data Engineer"
    contact_company = "[Company]"  # ← placeholder
    contact_industry = audience.get("industry") or "technology"

    cur.close()
    conn.close()

    job_id = str(_uuid.uuid4())
    _preview_jobs[job_id] = {"status": "pending"}

    from agent3.nodes.personalize import PERSONALIZE_PROMPT

    contact_name = (
        f"{sample_contact.get('first_name', '')} {sample_contact.get('last_name', '')}".strip()
        if sample_contact
        else "there"
    )
    contact_job_title = (
        sample_contact.get("job_title", "professional")
        if sample_contact
        else "professional"
    )
    contact_company = (
        sample_contact.get("company_name", "your company")
        if sample_contact
        else "your company"
    )
    contact_industry = (
        sample_contact.get("industry", "technology") if sample_contact else "technology"
    )

    prompt = PERSONALIZE_PROMPT.format(
        name=contact_name,
        job_title=contact_job_title,
        company=contact_company,
        industry=contact_industry,
    )

    print(f"Prompt being sent to Ollama: {prompt[:500]}...")

    def run():
        try:
            print(f"[DEBUG] Starting LLM for job: {job_id}")
            print(
                f"[DEBUG] Contact: {contact_name} | {contact_job_title} | {contact_company}"
            )

            resp = llm.invoke(prompt)
            full_text = resp.content.strip()

            result = extract_json_from_llm(full_text)

            if not result:
                raise ValueError("extract_json_from_llm returned None")

            if not all(k in result for k in ("subject", "text", "html")):
                raise ValueError(f"Missing keys in result: {result.keys()}")

            _preview_jobs[job_id] = {"status": "done", "email": result}
            print(f"[DEBUG] Job {job_id} completed — subject: {result.get('subject')}")

            print(f"[DEBUG] Job {job_id} completed successfully")

        except Exception as ex:
            print(f"[ERROR] Job {job_id} failed: {ex}")
            import traceback

            traceback.print_exc()

            _preview_jobs[job_id] = {
                "status": "done",
                "email": {
                    "subject": f"Quick question for {contact_job_title}s at {contact_company}",
                    "text": (
                        f"Hi {contact_name},\n\n"
                        f"As a {contact_job_title} at {contact_company}, you're likely managing "
                        f"complex data workflows. We help {contact_industry} companies build "
                        f"reliable ETL pipelines and BI dashboards.\n\n"
                        f"Would a 15-minute call be worth your time?\n\n"
                        f"Best,\nSami Ali\nBITS Global Consulting"
                    ),
                    "html": (
                        f"<p>Hi {contact_name},</p>"
                        f"<p>As a {contact_job_title} at {contact_company}, you're likely managing "
                        f"complex data workflows. We help {contact_industry} companies build "
                        f"reliable ETL pipelines and BI dashboards.</p>"
                        f"<p>Would a 15-minute call be worth your time?</p>"
                        f"<p>Best,<br>Sami Ali<br>BITS Global Consulting</p>"
                    ),
                },
            }

    print(f"[DEBUG PRE-THREAD] contact_name='{contact_name}'")
    print(f"[DEBUG PRE-THREAD] contact_company='{contact_company}'")
    print(f"[DEBUG PRE-THREAD] prompt length={len(prompt)}")
    print(f"[DEBUG PRE-THREAD] prompt sample='{prompt[:300]}'")

    threading.Thread(target=run, daemon=True).start()
    return {"job_id": job_id}


@router.get("/preview/job/{job_id}")
def get_preview_job(job_id: str):
    job = _preview_jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


@router.get("/campaigns/{campaign_id}/runs")
def campaign_runs(campaign_id: str):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT * FROM crm.crm_campaign_runs
        WHERE campaign_id = %s ORDER BY created_at DESC
    """,
        (campaign_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/runs/{run_id}/recipients")
def run_recipients(run_id: str):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT cr.*, c.first_name, c.last_name, c.email,
               c.job_title, co.company_name
        FROM crm.crm_campaign_recipients cr
        JOIN crm.crm_contacts c ON c.contact_id = cr.contact_id
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        WHERE cr.run_id = %s ORDER BY cr.sent_at DESC
    """,
        (run_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/replies")
def get_replies(campaign_id: Optional[str] = None):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where = "WHERE r.campaign_id = %s" if campaign_id else ""
    vals = (campaign_id,) if campaign_id else ()
    cur.execute(
        f"""
        SELECT cr.*, c.first_name, c.last_name, c.email,
               co.company_name, r.campaign_name
        FROM crm.crm_campaign_responses cr
        JOIN crm.crm_contacts c ON c.contact_id = cr.contact_id
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        JOIN crm.crm_campaign_runs run ON run.run_id = cr.run_id
        JOIN crm.crm_campaigns r ON r.campaign_id = run.campaign_id
        {where}
        ORDER BY cr.responded_at DESC
    """,
        vals,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


# ── OAuth for Microsoft 365 ───────────────────────────────────────────────────
@router.get("/auth/callback")
def auth_callback(
    code: str = None, state: str = "", error: str = None, error_description: str = None
):
    if error:
        return {"status": "error", "error": error, "description": error_description}
    if not code:
        return {"status": "error", "error": "No code received"}
    try:
        from agent3.graph_auth import handle_callback

        handle_callback(code=code, campaign_id=state)
        return {"status": "connected", "campaign_id": state}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/auth/{campaign_id}")
def start_auth(campaign_id: str):
    from agent3.graph_auth import get_auth_url
    import urllib.parse

    url = get_auth_url(campaign_id)
    # Append campaign_id to state
    return RedirectResponse(url)


@router.get("/auth/{campaign_id}/start")
def start_auth_explicit(campaign_id: str):
    from agent3.graph_auth import get_auth_url
    from fastapi.responses import RedirectResponse

    url = get_auth_url(campaign_id)
    return RedirectResponse(url)


@router.get("/track/open/{recipient_id}")
def track_open(recipient_id: str):
    from fastapi.responses import Response
    import psycopg2

    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.crm_campaign_recipients
            SET opened_at = NOW(), open_count = COALESCE(open_count, 0) + 1
            WHERE recipient_id = %s
        """,
            (recipient_id,),
        )
        conn.commit()
        cur.close()
        conn.close()
    except:
        pass
    # Return 1x1 transparent pixel
    pixel = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
    return Response(content=pixel, media_type="image/gif")
