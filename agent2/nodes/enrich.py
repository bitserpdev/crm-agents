import os
import uuid
import redis
import psycopg2
import psycopg2.extras
from agent2.state import Agent2State

r = redis.from_url(os.getenv("REDIS_URL"))
PROMOTED_SET = "op:promoted_events"
DEDUP_TTL = 3600  # 1 hour


def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def _upsert_company(cur, record: dict) -> str | None:
    company_name = (record.get("company_name") or "").strip()  # FIX: handles None value
    if not company_name:
        return None

    # Check if company exists by name
    cur.execute(
        """
        SELECT company_id FROM crm.crm_companies
        WHERE LOWER(company_name) = LOWER(%s)
        LIMIT 1
    """,
        (company_name,),
    )
    row = cur.fetchone()

    if row:
        return str(row["company_id"])

    # Insert new company
    company_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO crm.crm_companies
            (company_id, company_name, domain, city, country)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (domain) DO UPDATE SET
            company_name = EXCLUDED.company_name,
            updated_at   = NOW()
        RETURNING company_id
    """,
        (
            company_id,
            company_name,
            record.get("company_domain") or None,
            record.get("city") or None,
            record.get("country_code") or None,
        ),
    )
    result = cur.fetchone()
    return str(result["company_id"]) if result else company_id


def enrich_node(state: Agent2State) -> Agent2State:
    if not state["extracted_records"]:
        state["run_status"] = "done"
        return state

    enriched = []
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    for record in state["extracted_records"]:
        event_id = record.get("_event_id") or ""
        dedup_key = record.get("_dedup_key") or ""

        # Skip empty records
        if (
            not record.get("first_name", "").strip()
            and not record.get("job_title", "").strip()
        ):
            print(
                f"[agent2/enrich] Skipping empty record: {record.get("_event_id","")[:16]}"
            )
            continue
        # Skip if already promoted (Redis set check)
        if r.sismember(PROMOTED_SET, event_id):
            print(f"[agent2/enrich] Already promoted: {event_id[:16]}... skipping")
            continue

        # Redis hot dedup for contacts (1h TTL)
        op_dedup_key = f"op:dedup:{dedup_key}"
        if r.get(op_dedup_key):
            print(f"[agent2/enrich] Contact dedup hit: {dedup_key[:16]}... skipping")
            continue

        # Upsert company and get company_id
        try:
            company_id = _upsert_company(cur, record)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(
                f"[agent2/enrich] Company upsert failed for event {event_id[:16]}: {e}"
            )
            company_id = None

        record["_company_id"] = company_id
        enriched.append(record)

    cur.close()
    conn.close()
    print(
        f"[agent2/enrich] {len(enriched)}/{len(state['extracted_records'])} records after dedup"
    )
    state["enriched_records"] = enriched
    return state
