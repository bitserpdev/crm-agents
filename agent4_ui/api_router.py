import os
from fastapi import APIRouter, HTTPException
import psycopg2, psycopg2.extras

router = APIRouter(prefix="/api/agent4", tags=["agent4"])

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@router.get("/sequences")
def get_sequences(campaign_id: str = None, status: str = None):
    """Get all follow-up sequences with contact info."""
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    filters = []
    values  = []
    if campaign_id:
        filters.append("s.campaign_id = %s")
        values.append(campaign_id)
    if status and status != "all":
        filters.append("s.status = %s")
        values.append(status)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    cur.execute(f"""
        SELECT
            s.sequence_id, s.campaign_id, s.contact_id, s.run_id,
            s.current_step, s.max_steps, s.status,
            s.next_followup_at, s.last_reply_at,
            s.last_intent_label, s.teams_meeting_url,
            s.created_at, s.updated_at,
            c.first_name, c.last_name, c.email, c.job_title,
            co.company_name, co.industry,
            cs.overall_score,
            camp.campaign_name,
            tm.join_url AS teams_join_url,
            (SELECT COUNT(*) FROM crm.crm_follow_up_emails fe
             WHERE fe.sequence_id = s.sequence_id) AS total_messages
        FROM crm.crm_follow_up_sequences s
        JOIN crm.crm_contacts c ON c.contact_id = s.contact_id
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        LEFT JOIN crm.crm_contact_scores cs ON cs.contact_id = s.contact_id
        LEFT JOIN crm.crm_campaigns camp ON camp.campaign_id = s.campaign_id
        LEFT JOIN crm.crm_teams_meetings tm ON tm.sequence_id = s.sequence_id
        {where}
        ORDER BY s.updated_at DESC
    """, values)

    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


@router.get("/sequences/{sequence_id}/thread")
def get_thread(sequence_id: str):
    """Get full conversation thread for a sequence."""
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get sequence + contact info
    cur.execute("""
        SELECT s.*, c.first_name, c.last_name, c.email, c.job_title,
               co.company_name, camp.campaign_name, camp.service_description
        FROM crm.crm_follow_up_sequences s
        JOIN crm.crm_contacts c ON c.contact_id = s.contact_id
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        LEFT JOIN crm.crm_campaigns camp ON camp.campaign_id = s.campaign_id
        WHERE s.sequence_id = %s
    """, (sequence_id,))
    seq = cur.fetchone()
    if not seq:
        raise HTTPException(404, "Sequence not found")

    # Get initial outbound email from agent3
    cur.execute("""
        SELECT em.subject, em.body_text AS body, em.sent_at AS ts,
               'outbound' AS direction, NULL AS intent_label, NULL AS intent_score
        FROM crm.crm_email_messages em
        JOIN crm.crm_email_threads et ON et.thread_id = em.thread_id
        WHERE et.contact_id = %s
        ORDER BY em.sent_at ASC
        LIMIT 5
    """, (seq["contact_id"],))
    initial_emails = [dict(r) for r in cur.fetchall()]

    # Get all follow-up emails (inbound + outbound) from agent4
    cur.execute("""
        SELECT subject, body, sent_at AS ts, received_at,
               direction, intent_label, intent_score,
               delivery_status, step_number
        FROM crm.crm_follow_up_emails
        WHERE sequence_id = %s
        ORDER BY COALESCE(sent_at, received_at) ASC NULLS LAST
    """, (sequence_id,))
    followup_msgs = [dict(r) for r in cur.fetchall()]

    # Get Teams meeting if any
    cur.execute("""
        SELECT join_url, subject, scheduled_at
        FROM crm.crm_teams_meetings
        WHERE sequence_id = %s
        ORDER BY created_at DESC LIMIT 1
    """, (sequence_id,))
    meeting = cur.fetchone()

    cur.close(); conn.close()

    # Merge and sort all messages
    all_messages = []
    for m in initial_emails:
        all_messages.append({
            "direction":    "outbound",
            "body":         m["body"] or "",
            "subject":      m["subject"] or "",
            "ts":           str(m["ts"]) if m["ts"] else None,
            "intent_label": None,
            "intent_score": None,
            "step":         0,
            "type":         "initial",
        })
    for m in followup_msgs:
        ts = m["ts"] or m["received_at"]
        all_messages.append({
            "direction":    m["direction"],
            "body":         m["body"] or "",
            "subject":      m["subject"] or "",
            "ts":           str(ts) if ts else None,
            "intent_label": m["intent_label"],
            "intent_score": m["intent_score"],
            "step":         m["step_number"],
            "type":         "followup",
        })

    all_messages.sort(key=lambda x: x["ts"] or "")

    return {
        "sequence": dict(seq),
        "messages": all_messages,
        "meeting":  dict(meeting) if meeting else None,
    }


@router.get("/stats")
def get_stats(campaign_id: str = None):
    """Get aggregate stats for the conversation view header."""
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    camp_filter = "WHERE s.campaign_id = %s" if campaign_id else ""
    values = [campaign_id] if campaign_id else []

    cur.execute(f"""
        SELECT
            COUNT(*) FILTER (WHERE s.status = 'active')        AS active,
            COUNT(*) FILTER (WHERE s.status = 'call_scheduled') AS call_scheduled,
            COUNT(*) FILTER (WHERE s.last_intent_label = 'hot') AS hot,
            COUNT(*) FILTER (WHERE s.last_intent_label = 'warm') AS warm,
            COUNT(*) FILTER (WHERE s.status = 'exhausted')     AS exhausted,
            COUNT(*) FILTER (WHERE s.status = 'unsubscribed')  AS unsubscribed,
            COUNT(*)                                            AS total
        FROM crm.crm_follow_up_sequences s
        {camp_filter}
    """, values)

    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row)
