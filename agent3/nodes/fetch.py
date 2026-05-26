import os, uuid
import psycopg2, psycopg2.extras
from agent3.state import Agent3State

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def fetch_node(state: Agent3State) -> Agent3State:
    print(f"[agent3/fetch] Loading campaign {state['campaign_id']}")
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM crm.crm_campaigns WHERE campaign_id = %s",
                (state["campaign_id"],))
    campaign = dict(cur.fetchone())
    state["campaign"] = campaign

    run_id = str(uuid.uuid4())
    state["run_id"] = run_id
    cur.execute("""
        INSERT INTO crm.crm_campaign_runs
            (run_id, campaign_id, run_status, started_at, redis_job_key)
        VALUES (%s, %s, 'running', NOW(), %s)
    """, (run_id, state["campaign_id"], f"op:campaign_run:{run_id}:queue"))
    conn.commit()

    audience = campaign.get("campaign_audience") or "contacts"
    contacts = []

    if audience in ("contacts", "all"):
        contacts += _fetch_contacts(cur, campaign, state["campaign_id"])

    if audience in ("clients", "all"):
        contacts += _fetch_clients(cur, campaign, state["campaign_id"])

    if audience == "all":
        seen, deduped = set(), []
        for c in contacts:
            if c["email"] and c["email"].lower() not in seen:
                seen.add(c["email"].lower())
                deduped.append(c)
        contacts = deduped

    cur.execute("""
        UPDATE crm.crm_campaign_runs
        SET total_recipients = %s WHERE run_id = %s
    """, (len(contacts), run_id))
    conn.commit()
    cur.close(); conn.close()

    state["contacts"]   = contacts
    state["run_status"] = "running" if contacts else "done"
    print(f"[agent3/fetch] Found {len(contacts)} contacts (audience: {audience})")
    return state


def _fetch_contacts(cur, campaign: dict, campaign_id: str) -> list:
    filters = [
        "c.is_suppressed = FALSE",
        "c.gdpr_consent  = TRUE",
        "c.email IS NOT NULL",
        "c.email NOT LIKE '%%placeholder%%'",
    ]
    values = []

    if campaign.get("filter_region"):
        filters.append("(UPPER(co.country_code) = UPPER(%s) OR UPPER(co.country) LIKE %s)")
        values.append(campaign["filter_region"])
        values.append(f"%{campaign['filter_region']}%")

    if campaign.get("filter_industry"):
        filters.append("LOWER(co.industry) LIKE %s")
        values.append(f"%{campaign['filter_industry'].lower()}%")

    if campaign.get("filter_company_size"):
        filters.append("co.company_size = %s")
        values.append(campaign["filter_company_size"])

    if campaign.get("filter_stage"):
        filters.append("c.lifecycle_stage = %s")
        values.append(campaign["filter_stage"])

    if campaign.get("filter_min_score") is not None:
        filters.append("COALESCE(s.overall_score, 0) >= %s")
        values.append(campaign["filter_min_score"])

    if campaign.get("filter_max_score") is not None:
        filters.append("COALESCE(s.overall_score, 0) <= %s")
        values.append(campaign["filter_max_score"])

    if campaign.get("filter_management_tier"):
        filters.append("c.management_tier = %s")
        values.append(campaign["filter_management_tier"])

    filters.append("""
        c.contact_id NOT IN (
            SELECT cr.contact_id FROM crm.crm_campaign_recipients cr
            JOIN crm.crm_campaign_runs r ON r.run_id = cr.run_id
            WHERE r.campaign_id = %s
        )
    """)
    values.append(campaign_id)

    where = "WHERE " + " AND ".join(filters)

    cur.execute(f"""
        SELECT
            c.contact_id        AS id,
            'contact'           AS audience_type,
            c.first_name,
            c.last_name,
            c.email,
            c.job_title,
            c.linkedin_url,
            c.lifecycle_stage,
            c.management_tier,
            c.source_platform,
            co.company_name,
            co.industry,
            co.city,
            co.country,
            co.country_code,
            co.company_size,
            co.domain,
            COALESCE(s.overall_score, 0) AS overall_score,
            COALESCE(s.intent_score,  0) AS intent_score,
            ARRAY(
                SELECT tag_name FROM crm.crm_contact_tags
                WHERE contact_id = c.contact_id
            ) AS tags
        FROM crm.crm_contacts c
        LEFT JOIN crm.crm_companies      co ON co.company_id = c.company_id
        LEFT JOIN crm.crm_contact_scores s  ON s.contact_id  = c.contact_id
        {where}
        ORDER BY COALESCE(s.overall_score, 0) DESC
        LIMIT 100
    """, values)

    results = [dict(r) for r in cur.fetchall()]
    print(f"[agent3/fetch] Contacts matched: {len(results)}")
    return results


def _fetch_clients(cur, campaign: dict, campaign_id: str) -> list:
    filters = [
        "cl.is_deleted = FALSE",
        "cl.email IS NOT NULL",
        "cl.email NOT LIKE '%%placeholder%%'",
    ]
    values = []

    if campaign.get("filter_region"):
        filters.append("(UPPER(cl.country_code) = UPPER(%s) OR UPPER(cl.country) LIKE %s)")
        values.append(campaign["filter_region"])
        values.append(f"%{campaign['filter_region']}%")

    if campaign.get("filter_industry"):
        filters.append("LOWER(cl.industry) LIKE %s")
        values.append(f"%{campaign['filter_industry'].lower()}%")

    if campaign.get("filter_management_tier"):
        filters.append("cl.management_tier = %s")
        values.append(campaign["filter_management_tier"])

    filters.append("""
        cl.email NOT IN (
            SELECT c.email FROM crm.crm_contacts c
            JOIN crm.crm_campaign_recipients cr ON cr.contact_id = c.contact_id
            JOIN crm.crm_campaign_runs r ON r.run_id = cr.run_id
            WHERE r.campaign_id = %s
        )
    """)
    values.append(campaign_id)

    where = "WHERE " + " AND ".join(filters)

    cur.execute(f"""
        SELECT
            cl.client_id        AS id,
            'client'            AS audience_type,
            cl.client_name      AS first_name,
            ''                  AS last_name,
            cl.email,
            cl.management_tier  AS job_title,
            NULL                AS linkedin_url,
            'customer'          AS lifecycle_stage,
            cl.management_tier,
            'manual'            AS source_platform,
            co.company_name,
            cl.industry,
            cl.city,
            cl.country,
            cl.country_code,
            co.company_size,
            co.domain,
            0                   AS overall_score,
            0                   AS intent_score,
            ARRAY[]::text[]     AS tags
        FROM crm.crm_clients cl
        LEFT JOIN crm.crm_companies co ON co.company_id = cl.contact_id
        {where}
        ORDER BY cl.created_at DESC
        LIMIT 100
    """, values)

    results = [dict(r) for r in cur.fetchall()]
    print(f"[agent3/fetch] Clients matched: {len(results)}")
    return results
