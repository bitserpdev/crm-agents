import os
import uuid
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from psycopg2.extras import Json

router = APIRouter()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

class LinkedInFilters(BaseModel):
    industry:         Optional[str]  = None
    region:           Optional[str]  = None
    management_tier:  Optional[str]  = None
    email:            Optional[bool] = False
    phone:            Optional[bool] = False
    domain:           Optional[str]  = None

class CampaignCreate(BaseModel):
    campaign_name:     str
    cron_expression:   str
    source_configs:    list
    is_active:         Optional[bool]            = True
    linkedin_filters:  Optional[LinkedInFilters] = None
    filter_match_mode: Optional[str]             = "all"

class CampaignUpdate(BaseModel):
    campaign_name:     Optional[str]             = None
    cron_expression:   Optional[str]             = None
    source_configs:    Optional[list]            = None
    is_active:         Optional[bool]            = None
    linkedin_filters:  Optional[LinkedInFilters] = None
    filter_match_mode: Optional[str]             = None

class FilterValidationRequest(BaseModel):
    industry:        Optional[str] = None
    region:          Optional[str] = None
    management_tier: Optional[str] = None
    domain:          Optional[str] = None

@router.get("")
def list_campaigns():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT campaign_id, campaign_name, cron_expression,
               source_configs, is_active, last_run_at, created_at,
               linkedin_filters, filter_match_mode
        FROM lz_campaigns ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]

@router.post("/validate-filters")
def validate_filters(payload: FilterValidationRequest):
    import requests as req, json, re

    checks = {}

    # Management tier — hardcoded instant check (these are our internal codes)
    VALID_TIERS = ["c_suite", "vp", "director", "manager", "individual"]
    if not payload.management_tier:
        checks["management_tier"] = {"valid": True, "reason": "not set", "suggestion": None}
    elif payload.management_tier.lower() in VALID_TIERS:
        checks["management_tier"] = {"valid": True, "reason": "valid tier code", "suggestion": None}
    else:
        checks["management_tier"] = {"valid": False, "reason": "Must be one of: " + ", ".join(VALID_TIERS), "suggestion": None}

    # Domain — regex instant check
    if not payload.domain:
        checks["domain"] = {"valid": True, "reason": "not set", "suggestion": None}
    elif re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', payload.domain):
        checks["domain"] = {"valid": True, "reason": "valid domain format", "suggestion": None}
    else:
        checks["domain"] = {"valid": False, "reason": "Invalid domain. Use format like: company.com", "suggestion": None}

    # Industry + Region — single LLM call
    industry_val = payload.industry or ""
    region_val   = payload.region or ""

    prompt = (
        "You are a strict data validator for a B2B sales platform.\n"
        "Validate these two fields and respond with ONLY valid JSON, no markdown.\n\n"
        'industry: "' + industry_val + '"\n'
        "Rules: Must be a real business industry (Telecom, Finance, Technology, Healthcare, Banking, "
        "Insurance, Retail, Manufacturing, Real Estate, Education, Energy, Logistics, Consulting, "
        "Pharma, Cybersecurity, Media, Government, Automotive). "
        "Empty string = valid. Person names or random words = invalid.\n\n"
        'region: "' + region_val + '"\n'
        "Rules: Must be a real country, US state, or major city. "
        "Empty string = valid. Random strings = invalid.\n\n"
        "Respond with ONLY this JSON structure:\n"
        '{"industry":{"valid":true,"reason":"reason here","suggestion":null},'
        '"region":{"valid":true,"reason":"reason here","suggestion":null}}'
    )

    try:
        resp = req.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 150}
            },
            timeout=25
        )
        text = resp.json().get("response", "").strip()
        s = text.find("{")
        e = text.rfind("}") + 1
        result = json.loads(text[s:e])
        checks["industry"] = result.get("industry", {"valid": True, "reason": "skipped", "suggestion": None})
        checks["region"]   = result.get("region",   {"valid": True, "reason": "skipped", "suggestion": None})
    except Exception as ex:
        # On timeout — block and ask user to retry
        checks["industry"] = {"valid": False, "reason": "Validation timed out — please try again", "suggestion": None}
        checks["region"]   = {"valid": False, "reason": "Validation timed out — please try again", "suggestion": None}

    all_valid = all(v.get("valid", True) for v in checks.values())
    return {"valid": all_valid, "checks": checks}

@router.post("")
def create_campaign(payload: CampaignCreate):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    lf = payload.linkedin_filters.dict() if payload.linkedin_filters else {}
    cur.execute("""
        INSERT INTO lz_campaigns
            (campaign_id, campaign_name, cron_expression, source_configs,
             is_active, linkedin_filters, filter_match_mode)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        str(uuid.uuid4()),
        payload.campaign_name,
        payload.cron_expression,
        Json(payload.source_configs),
        payload.is_active,
        Json(lf),
        payload.filter_match_mode or "all",
    ))
    row = dict(cur.fetchone())
    conn.commit(); cur.close(); conn.close()
    from scheduler.cron import register_campaign
    register_campaign(row)
    return row

@router.put("/{campaign_id}")
def update_campaign(campaign_id: str, payload: CampaignUpdate):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    updates = []
    values  = []
    if payload.campaign_name is not None:
        updates.append("campaign_name = %s");     values.append(payload.campaign_name)
    if payload.cron_expression is not None:
        updates.append("cron_expression = %s");   values.append(payload.cron_expression)
    if payload.source_configs is not None:
        updates.append("source_configs = %s");    values.append(Json(payload.source_configs))
    if payload.is_active is not None:
        updates.append("is_active = %s");         values.append(payload.is_active)
    if payload.linkedin_filters is not None:
        updates.append("linkedin_filters = %s");  values.append(Json(payload.linkedin_filters.dict()))
    if payload.filter_match_mode is not None:
        updates.append("filter_match_mode = %s"); values.append(payload.filter_match_mode)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates.append("updated_at = NOW()")
    values.append(campaign_id)
    cur.execute(f"UPDATE lz_campaigns SET {', '.join(updates)} WHERE campaign_id = %s RETURNING *", values)
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")
    conn.commit(); cur.close(); conn.close()
    row = dict(row)
    from scheduler.cron import register_campaign, scheduler
    if row.get("is_active"):
        register_campaign(row)
    else:
        try: scheduler.remove_job(row["campaign_id"])
        except: pass
    return row

@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: str):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM lz_campaigns WHERE campaign_id = %s", (campaign_id,))
    conn.commit(); cur.close(); conn.close()
    try:
        from scheduler.cron import scheduler
        scheduler.remove_job(campaign_id)
    except: pass
    return {"status": "deleted", "campaign_id": campaign_id}

@router.post("/{campaign_id}/trigger")
def trigger_campaign(campaign_id: str):
    import threading
    from scheduler.cron import run_campaign
    threading.Thread(target=run_campaign, args=(campaign_id,), daemon=True).start()
    return {"status": "triggered", "campaign_id": campaign_id}
