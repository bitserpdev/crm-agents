from psycopg2.extras import Json
from core.database import get_conn, release_conn, get_dict_cursor, get_db
from core.logger import logger
from utils.uuid import new_id


class CampaignRepository:
    def __init__(self):
        pass

    def get_all(
        self,
    ) -> list:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute("""
                            SELECT campaign_id, campaign_name, cron_expression,
                                source_configs, is_active, last_run_at, created_at,
                                linkedin_filters, filter_match_mode
                            FROM lz_campaigns
                            ORDER BY created_at DESC
                        """)
                return [dict(r) for r in cur.fetchall()]
            finally:
                cur.close()

    def get_by_id(self, campaign_id: str) -> dict | None:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute(
                    """
                    SELECT * FROM lz_campaigns
                    WHERE campaign_id = %s
                """,
                    (campaign_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close()

    def insert(self, payload: dict) -> dict:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute(
                    """
                    INSERT INTO lz_campaigns
                        (campaign_id, campaign_name, cron_expression, source_configs,
                        is_active, linkedin_filters, filter_match_mode)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """,
                    (
                        payload["campaign_id"],
                        payload["campaign_name"],
                        payload["cron_expression"],
                        Json(payload["source_configs"]),
                        payload["is_active"],
                        Json(payload["linkedin_filters"]),
                        payload["filter_match_mode"],
                    ),
                )
                row = dict(cur.fetchone())
                conn.commit()
                logger.info(
                    "[campaigns.repo] Inserted", campaign_id=payload["campaign_id"]
                )
                return row
            except Exception as e:
                conn.rollback()
                logger.error("[campaigns.repo] Insert failed", error=str(e))
                raise
            finally:
                cur.close()

    def update(self, campaign_id: str, fields: dict) -> dict | None:
        """
        Dynamic update — only touches columns present in `fields`.
        Safe against future schema additions.
        """
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                # Build SET clause dynamically
                json_fields = {"source_configs", "linkedin_filters"}
                parts = []
                values = []

                for key, val in fields.items():
                    parts.append(f"{key} = %s")
                    values.append(Json(val) if key in json_fields else val)

                parts.append("updated_at = NOW()")
                values.append(campaign_id)

                cur.execute(
                    f"UPDATE lz_campaigns SET {', '.join(parts)} WHERE campaign_id = %s RETURNING *",
                    values,
                )
                row = cur.fetchone()
                conn.commit()
                return dict(row) if row else None
            except Exception as e:
                conn.rollback()
                logger.error(
                    "[campaigns.repo] Update failed",
                    campaign_id=campaign_id,
                    error=str(e),
                )
                raise
            finally:
                cur.close()

    def delete(self, campaign_id: str) -> bool:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                cur.execute(
                    "DELETE FROM lz_campaigns WHERE campaign_id = %s", (campaign_id,)
                )
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
            except Exception as e:
                conn.rollback()
                logger.error(
                    "[campaigns.repo] Delete failed",
                    campaign_id=campaign_id,
                    error=str(e),
                )
                raise
            finally:
                cur.close()
