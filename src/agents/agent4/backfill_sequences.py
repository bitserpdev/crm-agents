"""Backfill crm_follow_up_sequences from existing campaign responses (one-time / dev)."""

from core.database import get_conn, get_dict_cursor


def backfill_conversation_sequences() -> dict:
    """
    Create sequence rows for contacts who replied but have no conversation record.
    Populates last_reply_at so the Conversations UI can display them.
    """
    conn = get_conn()
    cur = get_dict_cursor(conn)

    cur.execute(
        """
        INSERT INTO crm.crm_follow_up_sequences
            (campaign_id, contact_id, run_id, original_response_id,
             current_step, max_steps, status, last_reply_at,
             last_intent_label, asked_availability)
        SELECT DISTINCT ON (r.contact_id, cr.campaign_id)
            cr.campaign_id,
            r.contact_id,
            r.run_id,
            r.response_id,
            1,
            5,
            CASE
                WHEN r.intent_label = 'unsubscribe' THEN 'unsubscribed'
                ELSE 'active'
            END,
            r.responded_at,
            COALESCE(r.intent_label, 'warm'),
            FALSE
        FROM crm.crm_campaign_responses r
        JOIN crm.crm_campaign_runs cr ON cr.run_id = r.run_id
        WHERE r.responded_at IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM crm.crm_follow_up_sequences s
              WHERE s.contact_id = r.contact_id
                AND s.campaign_id = cr.campaign_id
          )
        ORDER BY r.contact_id, cr.campaign_id, r.responded_at DESC
        RETURNING sequence_id
        """
    )
    created = cur.fetchall()
    created_ids = [str(row["sequence_id"]) for row in created]

    # Link inbound replies to sequences for thread view
    if created_ids:
        cur.execute(
            """
            INSERT INTO crm.crm_follow_up_emails
                (sequence_id, contact_id, campaign_id, step_number,
                 direction, body, intent_label, intent_score,
                 received_at, delivery_status)
            SELECT
                s.sequence_id,
                r.contact_id,
                s.campaign_id,
                1,
                'inbound',
                r.reply_body,
                r.intent_label,
                COALESCE(r.intent_score, 0),
                r.responded_at,
                'received'
            FROM crm.crm_follow_up_sequences s
            JOIN crm.crm_campaign_responses r
              ON r.response_id = s.original_response_id
            WHERE s.sequence_id = ANY(%s::uuid[])
              AND NOT EXISTS (
                  SELECT 1 FROM crm.crm_follow_up_emails fe
                  WHERE fe.sequence_id = s.sequence_id
                    AND fe.direction = 'inbound'
                    AND fe.received_at = r.responded_at
              )
            """,
            (created_ids,),
        )

    conn.commit()
    cur.close()
    conn.close()

    return {"sequences_created": len(created_ids)}
