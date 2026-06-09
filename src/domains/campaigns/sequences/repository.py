from typing import Optional
from core.database import get_db, get_dict_cursor


class SequenceRepository:

    # ── Conversations ─────────────────────────────────────────────────────────

    def list_conversations(
        self,
        campaign_id: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> list[dict]:
        filters = ["s.last_reply_at IS NOT NULL"]
        values  = []

        if campaign_id:
            filters.append("s.campaign_id = %s")
            values.append(campaign_id)
        if intent and intent != "all":
            if intent == "call_scheduled":
                filters.append("s.status = 'call_scheduled'")
            elif intent == "unsubscribed":
                filters.append("s.status = 'unsubscribed'")
            else:
                filters.append("s.last_intent_label = %s")
                values.append(intent)

        where = "WHERE " + " AND ".join(filters)

        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                f"""
                SELECT s.sequence_id, s.campaign_id, s.contact_id,
                       s.current_step, s.max_steps, s.status,
                       s.last_reply_at, s.last_intent_label,
                       s.teams_meeting_url, s.asked_availability,
                       s.created_at, s.updated_at,
                       c.first_name, c.last_name, c.email, c.job_title,
                       co.company_name, co.industry, cs.overall_score,
                       camp.campaign_name,
                       tm.join_url AS teams_join_url,
                       (SELECT fe.body FROM crm.crm_follow_up_emails fe
                        WHERE fe.sequence_id = s.sequence_id AND fe.direction = 'inbound'
                        ORDER BY fe.received_at DESC LIMIT 1) AS last_reply_preview,
                       (SELECT COUNT(*) FROM crm.crm_follow_up_emails fe
                        WHERE fe.sequence_id = s.sequence_id) AS total_messages
                FROM crm.crm_follow_up_sequences s
                JOIN crm.crm_contacts c ON c.contact_id = s.contact_id
                LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                LEFT JOIN crm.crm_contact_scores cs ON cs.contact_id = s.contact_id
                LEFT JOIN crm.crm_campaigns camp ON camp.campaign_id = s.campaign_id
                LEFT JOIN crm.crm_teams_meetings tm ON tm.sequence_id = s.sequence_id
                {where}
                ORDER BY s.last_reply_at DESC
                """,
                values,
            )
            rows = cur.fetchall()
            cur.close()
        return [dict(r) for r in rows]

    def get_conversation_stats(self, campaign_id: Optional[str] = None) -> dict:
        camp_filter = "AND s.campaign_id = %s" if campaign_id else ""
        values      = [campaign_id] if campaign_id else []

        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NOT NULL)                                 AS total,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NOT NULL AND s.last_intent_label = 'hot') AS hot,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NOT NULL AND s.last_intent_label = 'warm')AS warm,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NOT NULL AND s.last_intent_label = 'cold')AS cold,
                    COUNT(*) FILTER (WHERE s.status = 'call_scheduled')                                 AS call_scheduled,
                    COUNT(*) FILTER (WHERE s.status = 'unsubscribed')                                   AS unsubscribed
                FROM crm.crm_follow_up_sequences s
                WHERE s.last_reply_at IS NOT NULL {camp_filter}
                """,
                values,
            )
            row = cur.fetchone()
            cur.close()
        return dict(row)

    def get_thread(self, sequence_id: str) -> Optional[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)

            cur.execute(
                """
                SELECT s.*, c.first_name, c.last_name, c.email, c.job_title,
                       co.company_name, camp.campaign_name, camp.service_description
                FROM crm.crm_follow_up_sequences s
                JOIN crm.crm_contacts c ON c.contact_id = s.contact_id
                LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                LEFT JOIN crm.crm_campaigns camp ON camp.campaign_id = s.campaign_id
                WHERE s.sequence_id = %s
                """,
                (sequence_id,),
            )
            seq = cur.fetchone()
            if not seq:
                cur.close()
                return None

            cur.execute(
                """
                SELECT em.subject, em.body_text AS body, em.sent_at AS ts,
                       'outbound' AS direction, NULL AS intent_label, 0 AS step
                FROM crm.crm_email_messages em
                JOIN crm.crm_email_threads et ON et.thread_id = em.thread_id
                WHERE et.contact_id = %s
                ORDER BY em.sent_at ASC
                """,
                (seq["contact_id"],),
            )
            initial = cur.fetchall()

            cur.execute(
                """
                SELECT subject, body, direction, intent_label,
                       step_number AS step,
                       COALESCE(sent_at, received_at) AS ts
                FROM crm.crm_follow_up_emails
                WHERE sequence_id = %s
                ORDER BY COALESCE(sent_at, received_at) ASC NULLS LAST
                """,
                (sequence_id,),
            )
            followups = cur.fetchall()

            cur.execute(
                """
                SELECT join_url, subject, scheduled_at
                FROM crm.crm_teams_meetings
                WHERE sequence_id = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (sequence_id,),
            )
            meeting = cur.fetchone()
            cur.close()

        return {
            "sequence":  dict(seq),
            "initial":   [dict(r) for r in initial],
            "followups": [dict(r) for r in followups],
            "meeting":   dict(meeting) if meeting else None,
        }

    # ── Follow-ups ────────────────────────────────────────────────────────────

    def list_followups(
        self,
        campaign_id: Optional[str] = None,
        tab: str = "all",
    ) -> list[dict]:
        filters = ["c.is_suppressed = FALSE", "s.last_reply_at IS NULL"]
        values  = []

        if campaign_id:
            filters.append("s.campaign_id = %s")
            values.append(campaign_id)

        tab_filters = {
            "no_open":   ["r.opened_at IS NULL", "s.status = 'active'"],
            "opened":    ["r.opened_at IS NOT NULL", "s.status = 'active'"],
            "fu1":       ["s.current_step = 1", "s.status = 'active'"],
            "fu2":       ["s.current_step = 2", "s.status = 'active'"],
            "fu3":       ["s.current_step = 3", "s.status = 'active'"],
            "fu4":       ["s.current_step = 4", "s.status = 'active'"],
            "fu5":       ["s.current_step = 5", "s.status = 'active'"],
            "exhausted": ["s.status = 'exhausted'"],
        }
        filters += tab_filters.get(tab, ["s.status IN ('active', 'exhausted')"])
        where = "WHERE " + " AND ".join(filters)

        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                f"""
                SELECT s.sequence_id, s.campaign_id, s.contact_id,
                       s.current_step, s.max_steps, s.status,
                       s.next_followup_at, s.created_at, s.updated_at,
                       c.first_name, c.last_name, c.email, c.job_title,
                       co.company_name, co.industry, camp.campaign_name,
                       r.opened_at, r.sent_at AS initial_sent_at,
                       (SELECT COUNT(*) FROM crm.crm_follow_up_emails fe
                        WHERE fe.sequence_id = s.sequence_id
                        AND fe.direction = 'outbound') AS followups_sent
                FROM crm.crm_follow_up_sequences s
                JOIN crm.crm_contacts c ON c.contact_id = s.contact_id
                LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                LEFT JOIN crm.crm_campaigns camp ON camp.campaign_id = s.campaign_id
                LEFT JOIN crm.crm_campaign_recipients r
                       ON (r.contact_id = s.contact_id AND r.run_id = s.run_id)
                {where}
                ORDER BY s.next_followup_at ASC NULLS LAST
                """,
                values,
            )
            rows = cur.fetchall()
            cur.close()
        return [dict(r) for r in rows]

    def get_followup_stats(self, campaign_id: Optional[str] = None) -> dict:
        camp_filter = "AND s.campaign_id = %s" if campaign_id else ""
        values      = [campaign_id] if campaign_id else []

        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NULL AND s.status IN ('active','exhausted'))        AS total,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NULL AND s.status='active' AND r.opened_at IS NULL) AS no_open,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NULL AND s.status='active' AND r.opened_at IS NOT NULL) AS opened,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NULL AND s.status='active' AND s.current_step=1)    AS fu1,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NULL AND s.status='active' AND s.current_step=2)    AS fu2,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NULL AND s.status='active' AND s.current_step=3)    AS fu3,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NULL AND s.status='active' AND s.current_step=4)    AS fu4,
                    COUNT(*) FILTER (WHERE s.last_reply_at IS NULL AND s.status='active' AND s.current_step=5)    AS fu5,
                    COUNT(*) FILTER (WHERE s.status='exhausted')                                                  AS exhausted
                FROM crm.crm_follow_up_sequences s
                LEFT JOIN crm.crm_campaign_recipients r
                       ON (r.contact_id = s.contact_id AND r.run_id = s.run_id)
                WHERE 1=1 {camp_filter}
                """,
                values,
            )
            row = cur.fetchone()
            cur.close()
        return dict(row)


repo = SequenceRepository()