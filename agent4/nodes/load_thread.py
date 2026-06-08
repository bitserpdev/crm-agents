import os
import psycopg2, psycopg2.extras
from agent4.state import Agent4State


def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def load_thread_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") == "skipped":
        return state

    contact_id = state.get("contact_id", "")

    if not contact_id or contact_id.strip() == "":
        print(f"[agent4/load_thread] ERROR: Empty contact_id received")
        state["run_status"] = "failed"
        state["errors"].append("Empty contact_id received from queue")
        return state

    print(f"[agent4/load_thread] Loading thread for contact {state['contact_id']}")

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Load contact
    cur.execute(
        """
        SELECT c.*, co.company_name, co.industry, co.country, co.company_size
        FROM crm.crm_contacts c
        LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
        WHERE c.contact_id = %s
    """,
        (state["contact_id"],),
    )
    contact = cur.fetchone()
    if not contact:
        state["run_status"] = "failed"
        state["errors"].append(f"Contact {state['contact_id']} not found")
        return state
    state["contact"] = dict(contact)

    # Load campaign
    cur.execute(
        "SELECT * FROM crm.crm_campaigns WHERE campaign_id = %s",
        (state["campaign_id"],),
    )
    campaign = cur.fetchone()
    if not campaign:
        state["run_status"] = "failed"
        state["errors"].append(f"Campaign {state['campaign_id']} not found")
        return state
    state["campaign"] = dict(campaign)

    # Load the triggering response
    cur.execute(
        "SELECT * FROM crm.crm_campaign_responses WHERE response_id = %s",
        (state["response_id"],),
    )
    response = cur.fetchone()
    if not response:
        state["run_status"] = "failed"
        state["errors"].append(f"Response {state['response_id']} not found")
        return state
    state["response"] = dict(response)
    state["intent_label"] = response["intent_label"]
    state["intent_score"] = response["intent_score"] or 0.0

    # ── Load existing sequence — CRITICAL: load all fields including asked_availability ──
    cur.execute(
        """
        SELECT sequence_id, status, current_step, max_steps,
               asked_availability, teams_meeting_url,
               last_intent_label, last_reply_at, next_followup_at
        FROM crm.crm_follow_up_sequences
        WHERE campaign_id = %s AND contact_id = %s
    """,
        (state["campaign_id"], state["contact_id"]),
    )
    seq = cur.fetchone()
    state["sequence"] = dict(seq) if seq else None

    if seq:
        print(
            f"[agent4/load_thread] Existing sequence: status={seq['status']} asked_avail={seq['asked_availability']} has_teams={bool(seq['teams_meeting_url'])}"
        )

    # ── Load full thread history ──────────────────────────────────────────────
    history = []

    # Initial outbound emails (agent3)
    cur.execute(
        """
        SELECT em.subject, em.body_text AS body, em.sent_at AS ts, 'outbound' AS direction
        FROM crm.crm_email_messages em
        JOIN crm.crm_email_threads et ON et.thread_id = em.thread_id
        WHERE et.contact_id = %s AND em.direction = 'outbound'
        ORDER BY em.sent_at ASC
    """,
        (state["contact_id"],),
    )
    for row in cur.fetchall():
        history.append(
            {
                "direction": "outbound",
                "body": row["body"] or "",
                "subject": row["subject"] or "",
                "ts": str(row["ts"]),
            }
        )

    # All inbound replies
    cur.execute(
        """
        SELECT em.body_text AS body, em.received_at AS ts, 'inbound' AS direction,
               em.subject
        FROM crm.crm_email_messages em
        JOIN crm.crm_email_threads et ON et.thread_id = em.thread_id
        WHERE et.contact_id = %s AND em.direction = 'inbound'
        ORDER BY em.received_at ASC
    """,
        (state["contact_id"],),
    )
    for row in cur.fetchall():
        history.append(
            {
                "direction": "inbound",
                "body": row["body"] or "",
                "subject": row["subject"] or "",
                "ts": str(row["ts"]),
            }
        )

    # Agent4 follow-up emails
    if seq:
        cur.execute(
            """
            SELECT subject, body, direction,
                   COALESCE(sent_at, received_at) AS ts
            FROM crm.crm_follow_up_emails
            WHERE sequence_id = %s
            ORDER BY COALESCE(sent_at, received_at) ASC NULLS LAST
        """,
            (str(seq["sequence_id"]),),
        )
        for row in cur.fetchall():
            history.append(
                {
                    "direction": row["direction"],
                    "body": row["body"] or "",
                    "subject": row["subject"] or "",
                    "ts": str(row["ts"]) if row["ts"] else "",
                }
            )

    history.sort(key=lambda x: x.get("ts") or "")
    state["thread_history"] = history

    cur.close()
    conn.close()
    print(
        f"[agent4/load_thread] Loaded {len(history)} messages, intent={state['intent_label']}"
    )
    return state
