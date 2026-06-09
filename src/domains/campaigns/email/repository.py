from core.database import get_db, get_dict_cursor
from core.logger import logger


class EmailCampaignRepository:

    # ── Campaign CRUD ─────────────────────────────────────────────────────────

    def list_email_campaigns(self) -> list[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute("""
                    SELECT campaign_id, campaign_name, campaign_status, from_address,
                        service_description, filter_region, filter_industry,
                        filter_company_size, filter_min_score, filter_max_score,
                        filter_stage, scheduled_at, created_at
                    FROM crm.crm_campaigns
                    WHERE campaign_type = 'email'
                    ORDER BY created_at DESC
                """)
                return [dict(r) for r in cur.fetchall()]
            finally:
                cur.close()

    def get_system_user_id(self) -> str | None:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute("SELECT user_id FROM crm.crm_users LIMIT 1")
                row = cur.fetchone()
                return str(row["user_id"]) if row else None
            finally:
                cur.close()

    def create_email_campaign(self, payload: dict, user_id: str, status: str) -> dict:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute(
                    """
                    INSERT INTO crm.crm_campaigns (
                        campaign_name, campaign_type, campaign_status,
                        from_address, service_description,
                        filter_region, filter_industry, filter_company_size,
                        filter_min_score, filter_max_score, filter_stage,
                        scheduled_at, schedule_type, created_by
                    ) VALUES (
                        %s, 'email', %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    RETURNING *
                """,
                    (
                        payload["campaign_name"],
                        status,
                        payload["from_address"],
                        payload["service_description"],
                        payload["filter_region"],
                        payload["filter_industry"],
                        payload["filter_company_size"],
                        payload["filter_min_score"],
                        payload["filter_max_score"],
                        payload["filter_stage"],
                        payload["scheduled_at"],
                        "scheduled" if payload["scheduled_at"] else "immediate",
                        user_id,
                    ),
                )
                row = dict(cur.fetchone())
                conn.commit()
                return row
            except Exception as e:
                conn.rollback()
                logger.error("[email.repo] create failed", error=str(e))
                raise
            finally:
                cur.close()

    def delete_email_campaign(self, campaign_id: str) -> bool:
        with get_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    DELETE FROM crm.crm_campaigns
                    WHERE campaign_id = %s AND campaign_type = 'email'
                """,
                    (campaign_id,),
                )
                conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                conn.rollback()
                logger.error(
                    "[email.repo] delete failed", campaign_id=campaign_id, error=str(e)
                )
                raise
            finally:
                cur.close()

    # ── Send / Preview ────────────────────────────────────────────────────────

    def get_contacts_for_send(self, contact_ids: list) -> list[dict]:
    
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute(
                    """
                    SELECT c.contact_id, c.email, c.first_name,
                        c.last_name, c.job_title, co.company_name
                    FROM crm.crm_contacts c
                    LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                    WHERE c.contact_id = ANY(%s::uuid[])
                """,
                    (contact_ids,),
                )
                return [dict(r) for r in cur.fetchall()]
            finally:
                cur.close()

    def get_campaign(self, campaign_id: str) -> dict | None:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute(
                    "SELECT * FROM crm.crm_campaigns WHERE campaign_id = %s",
                    (campaign_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close()

    def get_contact_for_preview(self, contact_id: str) -> dict | None:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute(
                    """
                    SELECT c.*, co.company_name, co.industry,
                        co.domain, co.country, co.city, co.company_size
                    FROM crm.crm_contacts c
                    LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                    WHERE c.contact_id = %s
                """,
                    (contact_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close()

    def get_sample_audience(self) -> dict:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute("""
                    SELECT co.industry, c.job_title
                    FROM crm.crm_contacts c
                    LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                    WHERE co.industry IS NOT NULL
                    LIMIT 1
                """)
                row = cur.fetchone()
                return dict(row) if row else {}
            finally:
                cur.close()

    # ── Replies / Recipients / Tracking ──────────────────────────────────────

    def get_replies(self, campaign_id: str | None = None) -> list[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                where = "WHERE r.campaign_id = %s" if campaign_id else ""
                vals = (campaign_id,) if campaign_id else ()
                cur.execute(
                    f"""
                    SELECT cr.*, c.first_name, c.last_name, c.email,
                        co.company_name, r.campaign_name
                    FROM crm.crm_campaign_responses cr
                    JOIN crm.crm_contacts c ON c.contact_id = cr.contact_id
                    LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                    JOIN crm.crm_campaign_runs run ON run.run_id = cr.run_id
                    JOIN crm.crm_campaigns r ON r.campaign_id = run.campaign_id
                    {where}
                    ORDER BY cr.responded_at DESC
                """,
                    vals,
                )
                return [dict(r) for r in cur.fetchall()]
            finally:
                cur.close()

    def get_run_recipients(self, run_id: str) -> list[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute(
                    """
                    SELECT cr.*, c.first_name, c.last_name, c.email,
                        c.job_title, co.company_name
                    FROM crm.crm_campaign_recipients cr
                    JOIN crm.crm_contacts c ON c.contact_id = cr.contact_id
                    LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                    WHERE cr.run_id = %s
                    ORDER BY cr.sent_at DESC
                """,
                    (run_id,),
                )
                return [dict(r) for r in cur.fetchall()]
            finally:
                cur.close()

    def track_open(self, recipient_id: str):
        with get_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    UPDATE crm.crm_campaign_recipients
                    SET opened_at  = NOW(),
                        open_count = COALESCE(open_count, 0) + 1
                    WHERE recipient_id = %s
                """,
                    (recipient_id,),
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(
                    "[email.repo] track_open failed",
                    recipient_id=recipient_id,
                    error=str(e),
                )
            finally:
                cur.close()

    def preview_contacts(self, campaign_id: str) -> dict:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                """
                SELECT c.contact_id, c.first_name, c.last_name,
                    c.email, c.job_title, co.company_name,
                    cs.overall_score
                FROM crm.crm_contacts c
                LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                LEFT JOIN crm.crm_contact_scores cs ON cs.contact_id = c.contact_id
                JOIN crm.crm_campaign_recipients r ON r.contact_id = c.contact_id
                JOIN crm.crm_campaign_runs cr ON cr.run_id = r.run_id
                WHERE cr.campaign_id = %s
                AND c.is_suppressed = FALSE
                ORDER BY cs.overall_score DESC NULLS LAST
                LIMIT 50
                """,
                (campaign_id,),
            )
            rows = cur.fetchall()
            cur.close()
        return {"contacts": [dict(r) for r in rows], "total": len(rows)}


# Module-level singleton
repo = EmailCampaignRepository()
