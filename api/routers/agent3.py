import os, uuid
import psycopg2, psycopg2.extras
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional
from psycopg2.extras import Json

router = APIRouter(redirect_slashes=False)

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# ── Campaign CRUD ─────────────────────────────────────────────────────────────
class CampaignCreate(BaseModel):
    campaign_name:        str
    service_description:  str
    from_address:         str
    filter_region:        Optional[str]  = None
    filter_industry:      Optional[str]  = None
    filter_company_size:  Optional[str]  = None
    filter_min_score:     Optional[int]  = 0
    filter_max_score:     Optional[int]  = 100
    filter_stage:         Optional[str]  = None
    scheduled_at:         Optional[str]  = None

@router.get("/campaigns")
def list_campaigns():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
    cur.close(); conn.close()
    return [dict(r) for r in rows]

@router.post("/campaigns")
def create_campaign(payload: CampaignCreate):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Get system user
    cur.execute("SELECT user_id FROM crm.crm_users LIMIT 1")
    user = cur.fetchone()
    campaign_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO crm.crm_campaigns (
            campaign_id, campaign_name, campaign_type,
            campaign_status, schedule_type, from_address,
            service_description, filter_region, filter_industry,
            filter_company_size, filter_min_score, filter_max_score,
            filter_stage, scheduled_at, created_by
        ) VALUES (%s,%s,'email','draft','manual',%s,%s,%s,%s,%s,%s,%s,%s,%s::timestamptz,%s)
        RETURNING *
    """, (
        campaign_id, payload.campaign_name,
        payload.from_address, payload.service_description,
        payload.filter_region, payload.filter_industry,
        payload.filter_company_size,
        payload.filter_min_score, payload.filter_max_score,
        payload.filter_stage,
        payload.scheduled_at or None,
        str(user["user_id"]),
    ))
    row = dict(cur.fetchone())
    conn.commit(); cur.close(); conn.close()
    return row


class CampaignUpdate(BaseModel):
    campaign_name:        str
    service_description:  str
    from_address:         str
    filter_region:        Optional[str] = None
    filter_industry:      Optional[str] = None
    filter_company_size:  Optional[str] = None
    filter_min_score:     Optional[int] = 0
    filter_max_score:     Optional[int] = 100
    filter_stage:         Optional[str] = None
    scheduled_at:         Optional[str] = None

@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, payload: CampaignUpdate):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
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
    """, (
        payload.campaign_name, payload.service_description,
        payload.from_address, payload.filter_region,
        payload.filter_industry, payload.filter_company_size,
        payload.filter_min_score, payload.filter_max_score,
        payload.filter_stage, payload.scheduled_at or None,
        campaign_id,
    ))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    if not row:
        return {"error": "Campaign not found"}
    return dict(row)

@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM crm.crm_campaigns WHERE campaign_id = %s", (campaign_id,))
    conn.commit(); cur.close(); conn.close()
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
            graph.invoke({
                "campaign_id":    campaign_id,
                "run_id":         "",
                "campaign":       {},
                "contacts":       [],
                "personalized":   [],
                "sent":           [],
                "failed":         [],
                "errors":         [],
                "agent_trace_id": str(_uuid.uuid4()),
                "run_status":     "running",
                "stats":          {},
            })
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
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM crm.crm_campaigns WHERE campaign_id=%s", (campaign_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return {"error": f"Campaign {campaign_id} not found"}
    campaign = dict(row)
    if contact_id:
        cur.execute("""
            SELECT c.*, co.company_name, co.industry
            FROM crm.crm_contacts c
            LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
            WHERE c.contact_id = %s
        """, (contact_id,))
    else:
        cur.execute("""
            SELECT c.*, co.company_name, co.industry
            FROM crm.crm_contacts c
            LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
            LIMIT 1
        """)
    contact_row = cur.fetchone()
    if not contact_row:
        cur.close(); conn.close()
        return {"error": "No contacts found"}
    contact = dict(contact_row)
    cur.close(); conn.close()
    job_id = str(_uuid.uuid4())
    _preview_jobs[job_id] = {"status": "pending"}
    from agent3.nodes.personalize import PERSONALIZE_PROMPT
    prompt = PERSONALIZE_PROMPT + "\n\nContact and campaign details:\n" + json.dumps({
        "contact": {
            "name": f"{contact.get('first_name','')} {contact.get('last_name','')}",
            "job_title": contact.get("job_title", ""),
            "company": contact.get("company_name", ""),
            "industry": contact.get("industry", ""),
        },
        "service_description": campaign.get("service_description", ""),
        "sender_name": "BITS Analytics Team",
    }, default=str)
    def run():
        try:
            resp = req.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3.2", "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.4, "num_predict": 1200}},
                timeout=180
            )
            full_text = resp.json().get("response", "").strip()
            s = full_text.find("{"); e = full_text.rfind("}") + 1
            if s == -1 or e == 0:
                _preview_jobs[job_id] = {"status": "error", "error": "LLM returned no JSON"}
            else:
                result = json.loads(full_text[s:e])
                _preview_jobs[job_id] = {
                    "status": "done",
                    "contact": json.loads(json.dumps(contact, default=str)),
                    "email": result
                }
        except Exception as ex:
            _preview_jobs[job_id] = {"status": "error", "error": str(ex)}
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
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM crm.crm_campaign_runs
        WHERE campaign_id = %s ORDER BY created_at DESC
    """, (campaign_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

@router.get("/runs/{run_id}/recipients")
def run_recipients(run_id: str):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT cr.*, c.first_name, c.last_name, c.email,
               c.job_title, co.company_name
        FROM crm.crm_campaign_recipients cr
        JOIN crm.crm_contacts c ON c.contact_id = cr.contact_id
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        WHERE cr.run_id = %s ORDER BY cr.sent_at DESC
    """, (run_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

@router.get("/replies")
def get_replies(campaign_id: Optional[str] = None):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where = "WHERE r.campaign_id = %s" if campaign_id else ""
    vals  = (campaign_id,) if campaign_id else ()
    cur.execute(f"""
        SELECT cr.*, c.first_name, c.last_name, c.email,
               co.company_name, r.campaign_name
        FROM crm.crm_campaign_responses cr
        JOIN crm.crm_contacts c ON c.contact_id = cr.contact_id
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        JOIN crm.crm_campaign_runs run ON run.run_id = cr.run_id
        JOIN crm.crm_campaigns r ON r.campaign_id = run.campaign_id
        {where}
        ORDER BY cr.responded_at DESC
    """, vals)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

# ── OAuth for Microsoft 365 ───────────────────────────────────────────────────
@router.get("/auth/callback")
def auth_callback(code: str = None, state: str = "", error: str = None, error_description: str = None):
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
        cur.execute("""
            UPDATE crm.crm_campaign_recipients
            SET opened_at = NOW(), open_count = COALESCE(open_count, 0) + 1
            WHERE recipient_id = %s
        """, (recipient_id,))
        conn.commit()
        cur.close(); conn.close()
    except:
        pass
    # Return 1x1 transparent pixel
    pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return Response(content=pixel, media_type="image/gif")
