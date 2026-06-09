"""Create follow-up sequences when outbound campaign emails are sent."""

from datetime import datetime, timedelta, timezone

from core.database import get_conn, get_dict_cursor

FOLLOWUP_INTERVAL_DAYS = 3
MAX_STEPS = 5


def _get_or_create_run(cur, campaign_id: str) -> str:
    cur.execute(
        """
        SELECT run_id FROM crm.crm_campaign_runs
        WHERE campaign_id = %s
        ORDER BY created_at DESC LIMIT 1
        """,
        (campaign_id,),
    )
    row = cur.fetchone()
    if row:
        return str(row["run_id"])

    import uuid

    run_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO crm.crm_campaign_runs
            (run_id, campaign_id, run_status, started_at)
        VALUES (%s, %s, 'running', NOW())
        """,
        (run_id, campaign_id),
    )
    return run_id


def seed_outbound_sequence(
    campaign_id: str,
    contact_id: str,
    *,
    run_id: str | None = None,
    subject: str = "",
    body: str = "",
) -> str | None:
    """
    Record a sent recipient and start a follow-up sequence (last_reply_at NULL).
    Returns sequence_id or None if already exists.
    """
    conn = get_conn()
    cur = get_dict_cursor(conn)
    now = datetime.now(timezone.utc)
    next_followup = now + timedelta(days=FOLLOWUP_INTERVAL_DAYS)

    try:
        if not run_id:
            run_id = _get_or_create_run(cur, campaign_id)

        cur.execute(
            """
            INSERT INTO crm.crm_campaign_recipients
                (run_id, contact_id, delivery_status, sent_at)
            SELECT %s, %s, 'sent', %s
            WHERE NOT EXISTS (
                SELECT 1 FROM crm.crm_campaign_recipients
                WHERE run_id = %s AND contact_id = %s
            )
            """,
            (run_id, contact_id, now, run_id, contact_id),
        )

        cur.execute(
            """
            SELECT sequence_id FROM crm.crm_follow_up_sequences
            WHERE campaign_id = %s AND contact_id = %s AND last_reply_at IS NULL
            LIMIT 1
            """,
            (campaign_id, contact_id),
        )
        existing = cur.fetchone()
        if existing:
            conn.commit()
            return str(existing["sequence_id"])

        cur.execute(
            """
            INSERT INTO crm.crm_follow_up_sequences
                (campaign_id, contact_id, run_id,
                 current_step, max_steps, status,
                 next_followup_at, last_reply_at,
                 last_intent_label, asked_availability)
            VALUES (%s, %s, %s, 0, %s, 'active', %s, NULL, NULL, FALSE)
            RETURNING sequence_id
            """,
            (campaign_id, contact_id, run_id, MAX_STEPS, next_followup),
        )
        seq_row = cur.fetchone()
        sequence_id = str(seq_row["sequence_id"])

        if subject or body:
            cur.execute(
                """
                INSERT INTO crm.crm_follow_up_emails
                    (sequence_id, contact_id, campaign_id,
                     step_number, direction, subject, body,
                     sent_at, delivery_status)
                VALUES (%s, %s, %s, 0, 'outbound', %s, %s, %s, 'sent')
                """,
                (sequence_id, contact_id, campaign_id, subject, body, now),
            )

        conn.commit()
        return sequence_id
    finally:
        cur.close()
        conn.close()
