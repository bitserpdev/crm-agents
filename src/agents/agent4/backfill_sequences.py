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


def backfill_followup_sequences() -> dict:
    """
    Create follow-up sequences for contacts who were emailed but never replied.
    Populates last_reply_at=NULL so the Follow-ups UI can display them.
    """
    from datetime import datetime, timedelta, timezone

    from agents.agent4.seed_sequences import FOLLOWUP_INTERVAL_DAYS, MAX_STEPS

    conn = get_conn()
    cur = get_dict_cursor(conn)
    now = datetime.now(timezone.utc)
    next_followup = now + timedelta(days=FOLLOWUP_INTERVAL_DAYS)

    interval_days = f"{FOLLOWUP_INTERVAL_DAYS} days"

    cur.execute(
        f"""
        INSERT INTO crm.crm_follow_up_sequences
            (campaign_id, contact_id, run_id,
             current_step, max_steps, status,
             next_followup_at, last_reply_at,
             last_intent_label, asked_availability)
        SELECT DISTINCT ON (r.contact_id, cr.campaign_id)
            cr.campaign_id,
            r.contact_id,
            r.run_id,
            0,
            %s,
            'active',
            COALESCE(r.sent_at, NOW()) + INTERVAL '{interval_days}',
            NULL,
            NULL,
            FALSE
        FROM crm.crm_campaign_recipients r
        JOIN crm.crm_campaign_runs cr ON cr.run_id = r.run_id
        WHERE r.delivery_status = 'sent'
          AND NOT EXISTS (
              SELECT 1 FROM crm.crm_campaign_responses resp
              WHERE resp.contact_id = r.contact_id
                AND resp.run_id = r.run_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM crm.crm_follow_up_sequences s
              WHERE s.contact_id = r.contact_id
                AND s.campaign_id = cr.campaign_id
                AND s.last_reply_at IS NULL
          )
        ORDER BY r.contact_id, cr.campaign_id, r.sent_at DESC
        RETURNING sequence_id
        """,
        (MAX_STEPS,),
    )
    from_recipients = cur.fetchall()

    # Seed from outbound emails when recipients table was never populated
    cur.execute(
        f"""
        INSERT INTO crm.crm_follow_up_sequences
            (campaign_id, contact_id, run_id,
             current_step, max_steps, status,
             next_followup_at, last_reply_at,
             last_intent_label, asked_availability)
        SELECT DISTINCT ON (et.contact_id, lr.campaign_id)
            lr.campaign_id,
            et.contact_id,
            lr.run_id,
            0,
            %s,
            'active',
            COALESCE(em.sent_at, NOW()) + INTERVAL '{interval_days}',
            NULL,
            NULL,
            FALSE
        FROM crm.crm_email_messages em
        JOIN crm.crm_email_threads et ON et.thread_id = em.thread_id
        JOIN LATERAL (
            SELECT cr.campaign_id, cr.run_id
            FROM crm.crm_campaign_runs cr
            JOIN crm.crm_campaigns camp ON camp.campaign_id = cr.campaign_id
            WHERE camp.campaign_type = 'email'
            ORDER BY cr.created_at DESC
            LIMIT 1
        ) lr ON TRUE
        WHERE em.direction = 'outbound'
          AND NOT EXISTS (
              SELECT 1 FROM crm.crm_campaign_responses resp
              WHERE resp.contact_id = et.contact_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM crm.crm_follow_up_sequences s
              WHERE s.contact_id = et.contact_id
                AND s.last_reply_at IS NULL
          )
        ORDER BY et.contact_id, lr.campaign_id, em.sent_at DESC
        RETURNING sequence_id
        """,
        (MAX_STEPS,),
    )
    from_emails = cur.fetchall()

    # Backfill from agent run logs when recipients table was never populated
    cur.execute(
        f"""
        INSERT INTO crm.crm_follow_up_sequences
            (campaign_id, contact_id, run_id,
             current_step, max_steps, status,
             next_followup_at, last_reply_at,
             last_intent_label, asked_availability)
        SELECT DISTINCT ON (detail.contact_id, cr.campaign_id)
            cr.campaign_id,
            detail.contact_id::uuid,
            (aa.action_detail->>'run_id')::uuid,
            0,
            %s,
            'active',
            COALESCE(cr.completed_at, cr.started_at, NOW()) + INTERVAL '{interval_days}',
            NULL,
            NULL,
            FALSE
        FROM crm.crm_agent_actions aa
        JOIN crm.crm_campaign_runs cr
          ON cr.run_id = (aa.action_detail->>'run_id')::uuid
        CROSS JOIN LATERAL jsonb_array_elements_text(
            COALESCE(aa.action_detail->'contact_ids', '[]'::jsonb)
        ) AS detail(contact_id)
        WHERE aa.action_type = 'email_campaign_sent'
          AND aa.outcome = 'success'
          AND (aa.action_detail->>'sent')::int > 0
          AND detail.contact_id ~ '^[0-9a-f-]{{36}}$'
          AND NOT EXISTS (
              SELECT 1 FROM crm.crm_campaign_responses resp
              WHERE resp.contact_id = detail.contact_id::uuid
                AND resp.run_id = cr.run_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM crm.crm_follow_up_sequences s
              WHERE s.contact_id = detail.contact_id::uuid
                AND s.campaign_id = cr.campaign_id
                AND s.last_reply_at IS NULL
          )
        ORDER BY detail.contact_id, cr.campaign_id, cr.started_at DESC
        RETURNING sequence_id
        """,
        (MAX_STEPS,),
    )
    from_actions = cur.fetchall()

    # Ensure recipient rows exist for follow-up UI open-tracking joins
    cur.execute(
        """
        INSERT INTO crm.crm_campaign_recipients
            (run_id, contact_id, delivery_status, sent_at)
        SELECT DISTINCT
            (aa.action_detail->>'run_id')::uuid,
            detail.contact_id::uuid,
            'sent',
            COALESCE(cr.completed_at, cr.started_at, NOW())
        FROM crm.crm_agent_actions aa
        JOIN crm.crm_campaign_runs cr
          ON cr.run_id = (aa.action_detail->>'run_id')::uuid
        CROSS JOIN LATERAL jsonb_array_elements_text(
            COALESCE(aa.action_detail->'contact_ids', '[]'::jsonb)
        ) AS detail(contact_id)
        WHERE aa.action_type = 'email_campaign_sent'
          AND aa.outcome = 'success'
          AND detail.contact_id ~ '^[0-9a-f-]{36}$'
          AND NOT EXISTS (
              SELECT 1 FROM crm.crm_campaign_recipients r
              WHERE r.run_id = (aa.action_detail->>'run_id')::uuid
                AND r.contact_id = detail.contact_id::uuid
          )
        """
    )

    conn.commit()
    cur.close()
    conn.close()

    created = len(from_recipients) + len(from_emails) + len(from_actions)
    return {
        "from_recipients": len(from_recipients),
        "from_email_threads": len(from_emails),
        "from_agent_actions": len(from_actions),
        "sequences_created": created,
    }
