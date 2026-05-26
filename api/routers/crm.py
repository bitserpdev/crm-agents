import os
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@router.get("/contacts")
def get_contacts(
    search:  Optional[str] = None,
    stage:   Optional[str] = None,
    limit:   int = 50,
    offset:  int = 0
):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    filters = []
    values  = []
    if search:
        filters.append("(LOWER(c.first_name||' '||c.last_name) LIKE %s OR LOWER(c.email) LIKE %s OR LOWER(c.job_title) LIKE %s)")
        values += [f"%{search.lower()}%"] * 3
    if stage:
        filters.append("c.lifecycle_stage = %s")
        values.append(stage)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    values += [limit, offset]
    cur.execute(f"""
        SELECT
            c.contact_id, c.first_name, c.last_name,
            c.email, c.job_title, c.contact_type,
            c.lifecycle_stage, c.source_platform,
            c.linkedin_url, c.created_at,
            co.company_name, co.city, co.country,
            s.intent_score, s.lead_score, s.overall_score,
            ARRAY(SELECT tag_name FROM crm.crm_contact_tags
                  WHERE contact_id = c.contact_id) AS tags
        FROM crm.crm_contacts c
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        LEFT JOIN crm.crm_contact_scores s ON s.contact_id = c.contact_id
        {where}
        ORDER BY COALESCE(s.overall_score, 0) DESC, c.created_at DESC
        LIMIT %s OFFSET %s
    """, values)
    rows = cur.fetchall()
    cur.execute(f"""
        SELECT COUNT(*) FROM crm.crm_contacts c {where.replace('LIMIT %s OFFSET %s','') if where else ''}
    """, values[:-2] if values[:-2] else [])
    total = cur.fetchone()["count"]
    cur.close(); conn.close()
    return {"total": total, "records": [dict(r) for r in rows]}

@router.get("/leads")
def get_leads(
    search:  Optional[str] = None,
    status:  Optional[str] = None,
    limit:   int = 50,
    offset:  int = 0
):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    filters = []
    values  = []
    if search:
        filters.append("(LOWER(c.first_name||' '||c.last_name) LIKE %s OR LOWER(l.source_detail) LIKE %s)")
        values += [f"%{search.lower()}%"] * 2
    if status:
        filters.append("l.lead_status = %s")
        values.append(status)
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    values += [limit, offset]
    cur.execute(f"""
        SELECT
            l.lead_id, l.lead_status, l.lead_score,
            l.source_platform, l.source_detail,
            l.initial_message, l.created_at,
            l.estimated_value, l.currency,
            c.first_name, c.last_name, c.job_title, c.email,
            co.company_name,
            s.intent_score, s.overall_score
        FROM crm.crm_leads l
        JOIN crm.crm_contacts c  ON c.contact_id = l.contact_id
        LEFT JOIN crm.crm_companies co ON co.company_id = l.company_id
        LEFT JOIN crm.crm_contact_scores s ON s.contact_id = c.contact_id
        {where}
        ORDER BY COALESCE(l.lead_score, 0) DESC, l.created_at DESC
        LIMIT %s OFFSET %s
    """, values)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return {"records": [dict(r) for r in rows]}

@router.get("/stats")
def crm_stats():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM crm.crm_contacts)  AS total_contacts,
            (SELECT COUNT(*) FROM crm.crm_leads)     AS total_leads,
            (SELECT COUNT(*) FROM crm.crm_companies) AS total_companies,
            (SELECT COUNT(*) FROM crm.crm_leads WHERE lead_status='new')       AS new_leads,
            (SELECT COUNT(*) FROM crm.crm_leads WHERE lead_status='qualified') AS qualified_leads,
            (SELECT ROUND(AVG(overall_score)) FROM crm.crm_contact_scores)     AS avg_score,
            (SELECT COUNT(*) FROM crm.crm_contacts WHERE lifecycle_stage='subscriber') AS subscribers,
            (SELECT COUNT(*) FROM crm.crm_contact_scores WHERE intent_score >= 0.7)    AS high_intent
    """)
    return dict(cur.fetchone())

@router.get("/contacts/{contact_id}")
def get_contact_detail(contact_id: str):
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT c.*, co.company_name, co.city, co.country, co.industry,
               co.website_url, co.linkedin_url AS company_linkedin,
               s.intent_score, s.lead_score, s.fit_score,
               s.engagement_score, s.overall_score, s.score_breakdown,
               ARRAY(SELECT tag_name FROM crm.crm_contact_tags
                     WHERE contact_id = c.contact_id) AS tags
        FROM crm.crm_contacts c
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        LEFT JOIN crm.crm_contact_scores s ON s.contact_id = c.contact_id
        WHERE c.contact_id = %s
    """, (contact_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Contact not found")
    return dict(row)
