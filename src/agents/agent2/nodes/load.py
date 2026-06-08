import uuid
from psycopg2.extras import Json
from agents.agent2.state import Agent2State
from core.database import get_conn, release_conn, get_dict_cursor
from core.redis import get_redis
from core.logger import logger

PROMOTED_SET = "op:promoted_events"
DEDUP_TTL    = 3600


def load_node(state: Agent2State) -> Agent2State:
    if not state["enriched_records"]:
        state["run_status"] = "done"
        return state

    r      = get_redis()
    conn   = get_conn()
    cur    = get_dict_cursor(conn)
    loaded = []
    stats  = {"contacts": 0, "leads": 0, "companies": 0, "scores": 0, "tags": 0}

    try:
        for record in state["enriched_records"]:
            try:
                contact_id = _process_record(cur, record, stats)
                conn.commit()

                r.sadd(PROMOTED_SET, record.get("_event_id", ""))
                r.set(f"op:dedup:{record.get('_dedup_key','')}",
                      contact_id or "1", ex=DEDUP_TTL)

                loaded.append({**record, "_contact_id": contact_id})
                logger.info("[agent2/load] Loaded",
                            type=record.get("record_type"),
                            name=f"{record.get('first_name','')} {record.get('last_name','')}")

            except Exception as e:
                conn.rollback()
                msg = f"Load error on {record.get('_event_id','?')[:16]}: {e}"
                logger.error("[agent2/load] " + msg)
                state["errors"].append(msg)

    finally:
        cur.close()
        release_conn(conn)

    state["loaded_records"] = loaded
    state["stats"]          = stats
    logger.info("[agent2/load] Stats", **stats)
    return state


def _process_record(cur, record: dict, stats: dict) -> str | None:
    event_id   = record.get("_event_id", "")
    dedup_key  = record.get("_dedup_key", "")
    platform   = record.get("_platform", "linkedin")
    company_id = record.get("_company_id")
    rec_type   = record.get("record_type", "profile")
    contact_id = None

    if rec_type == "profile":
        contact_id = _insert_contact(cur, record, event_id, dedup_key,
                                     platform, company_id, stats)

    if contact_id or rec_type == "job":
        contact_id = _insert_lead(cur, record, event_id, dedup_key,
                                  platform, company_id, contact_id, stats)

    _insert_audit(cur, event_id, contact_id, rec_type, platform)
    return contact_id


def _insert_contact(cur, record, event_id, dedup_key,
                    platform, company_id, stats) -> str:
    email      = record.get("email") or f"linkedin_{event_id[:8]}@placeholder.bits"
    contact_id = str(uuid.uuid4())

    cur.execute("""
        INSERT INTO crm.crm_contacts (
            contact_id, company_id, first_name, last_name,
            email, job_title, linkedin_url, contact_type,
            lifecycle_stage, source_platform, dedup_key,
            lz_event_id, created_by_agent
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (dedup_key) DO UPDATE SET
            job_title    = EXCLUDED.job_title,
            linkedin_url = EXCLUDED.linkedin_url,
            updated_at   = NOW()
        RETURNING contact_id
    """, (
        contact_id, company_id,
        record.get("first_name", "Unknown"),
        record.get("last_name", ""),
        email,
        record.get("job_title", ""),
        record.get("linkedin_url", ""),
        record.get("contact_type", "prospect"),
        record.get("lifecycle_stage", "subscriber"),
        platform, dedup_key, event_id,
        "agent-2-lead-creation",
    ))
    row = cur.fetchone()
    if row:
        contact_id = str(row["contact_id"])
    stats["contacts"] += 1

    # Scores
    intent  = float(record.get("intent_score", 0.5))
    l_score = int(record.get("lead_score", int(intent * 100)))
    overall = min(100, int((intent * 60) + (l_score * 0.4)))
    cur.execute("""
        INSERT INTO crm.crm_contact_scores (
            score_id, contact_id, lead_score, intent_score,
            overall_score, score_breakdown, scored_by_agent, last_scored_at
        ) VALUES (%s,%s,%s,%s,%s,%s,'agent-2-lead-creation',NOW())
        ON CONFLICT (contact_id) DO UPDATE SET
            intent_score  = EXCLUDED.intent_score,
            lead_score    = EXCLUDED.lead_score,
            overall_score = EXCLUDED.overall_score,
            updated_at    = NOW()
    """, (
        str(uuid.uuid4()), contact_id, l_score,
        intent, overall, Json({"intent": intent, "lead": l_score}),
    ))
    stats["scores"] += 1

    # Tags
    for tag in record.get("tags", []):
        if tag and len(tag) <= 80:
            cur.execute("""
                INSERT INTO crm.crm_contact_tags
                    (tag_id, contact_id, tag_name, tagged_by)
                VALUES (%s,%s,%s,'agent-2-lead-creation')
                ON CONFLICT DO NOTHING
            """, (str(uuid.uuid4()), contact_id, str(tag)[:80]))
            stats["tags"] += 1

    return contact_id


def _insert_lead(cur, record, event_id, dedup_key,
                 platform, company_id, contact_id, stats) -> str:
    rec_type = record.get("record_type", "profile")

    if rec_type == "job" and not contact_id:
        contact_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO crm.crm_contacts (
                contact_id, first_name, last_name, email,
                job_title, contact_type, lifecycle_stage,
                source_platform, dedup_key, lz_event_id, created_by_agent
            ) VALUES (%s,'Job','Lead',%s,%s,'prospect','subscriber',%s,%s,%s,
                      'agent-2-lead-creation')
            ON CONFLICT (dedup_key) DO UPDATE SET updated_at=NOW()
            RETURNING contact_id
        """, (
            contact_id,
            f"joblead_{event_id[:8]}@placeholder.bits",
            record.get("job_title", ""),
            platform, f"job_{dedup_key}", event_id,
        ))
        row = cur.fetchone()
        if row:
            contact_id = str(row["contact_id"])

    l_score = int(record.get("lead_score",
                  int(float(record.get("intent_score", 0.5)) * 100)))
    cur.execute("""
        INSERT INTO crm.crm_leads (
            lead_id, contact_id, company_id, lz_event_id,
            lead_status, lead_score, source_platform,
            source_detail, initial_message, created_by_agent
        ) VALUES (%s,%s,%s,%s,'new',%s,%s,%s,%s,'agent-2-lead-creation')
    """, (
        str(uuid.uuid4()), contact_id, company_id, event_id,
        l_score, platform,
        record.get("job_title", record.get("source_detail", "")),
        record.get("description", record.get("summary", "")),
    ))
    stats["leads"] += 1
    return contact_id


def _insert_audit(cur, event_id, contact_id, rec_type, platform):
    cur.execute("""
        INSERT INTO crm.crm_agent_actions (
            action_id, agent_id, action_type,
            entity_type, entity_id, action_detail, outcome
        ) VALUES (%s,'agent-2-lead-creation','lead_created','contact',%s,%s,'success')
    """, (
        str(uuid.uuid4()),
        contact_id or event_id,
        Json({"event_id": event_id, "record_type": rec_type, "platform": platform}),
    ))