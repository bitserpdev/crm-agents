import uuid
from agents.agent2.state import Agent2State
from core.database import get_conn, release_conn, get_dict_cursor
from core.redis import get_redis
from core.logger import logger

PROMOTED_SET = "op:promoted_events"
DEDUP_TTL    = 3600


def enrich_node(state: Agent2State) -> Agent2State:
    if not state["extracted_records"]:
        state["run_status"] = "done"
        return state

    r        = get_redis()
    conn     = get_conn()
    cur      = get_dict_cursor(conn)
    enriched = []

    try:
        for record in state["extracted_records"]:
            event_id  = record.get("_event_id", "")
            dedup_key = record.get("_dedup_key", "")

            # Skip empty records
            if not record.get("first_name", "").strip() and \
               not record.get("job_title", "").strip():
                logger.info("[agent2/enrich] Skipping empty record",
                            event_id=event_id[:16])
                continue

            # Skip already promoted
            if r.sismember(PROMOTED_SET, event_id):
                logger.info("[agent2/enrich] Already promoted", event_id=event_id[:16])
                continue

            # Redis hot dedup
            if r.get(f"op:dedup:{dedup_key}"):
                logger.info("[agent2/enrich] Dedup hit", dedup_key=dedup_key[:16])
                continue

            try:
                company_id = _upsert_company(cur, record)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("[agent2/enrich] Company upsert failed",
                             event_id=event_id[:16], error=str(e))
                company_id = None

            record["_company_id"] = company_id
            enriched.append(record)

    finally:
        cur.close()
        release_conn(conn)

    logger.info("[agent2/enrich] Done",
                enriched=len(enriched),
                total=len(state["extracted_records"]))
    state["enriched_records"] = enriched
    return state


def _upsert_company(cur, record: dict) -> str | None:
    company_name = (record.get("company_name") or "").strip()
    if not company_name:
        return None

    cur.execute("""
        SELECT company_id FROM crm.crm_companies
        WHERE LOWER(company_name) = LOWER(%s)
        LIMIT 1
    """, (company_name,))
    row = cur.fetchone()
    if row:
        return str(row["company_id"])

    company_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO crm.crm_companies
            (company_id, company_name, domain, city, country)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (domain) DO UPDATE SET
            company_name = EXCLUDED.company_name,
            updated_at   = NOW()
        RETURNING company_id
    """, (
        company_id,
        company_name,
        record.get("company_domain") or None,
        record.get("city") or None,
        record.get("country_code") or None,
    ))
    result = cur.fetchone()
    return str(result["company_id"]) if result else company_id