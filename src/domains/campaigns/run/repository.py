from typing import Optional
from core.database import get_db, get_dict_cursor


class ExtractionRunRepository:

    def list_runs(self, limit: int = 50) -> list[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                """
                SELECT
                    el.log_id, el.event_id, el.agent_id,
                    el.extraction_status, el.duration_ms, el.ran_at,
                    el.error_message,
                    re.source_platform, re.campaign_id, re.processing_status
                FROM lz_extraction_logs el
                JOIN lz_raw_events re ON re.event_id = el.event_id
                ORDER BY el.ran_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(r) for r in rows]

    def list_by_campaign(self, campaign_id: str, limit: int = 50) -> list[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                """
                SELECT
                    el.log_id, el.event_id, el.agent_id,
                    el.extraction_status, el.duration_ms,
                    el.ran_at, el.error_message,
                    re.source_platform, re.processing_status
                FROM lz_extraction_logs el
                JOIN lz_raw_events re ON re.event_id = el.event_id
                WHERE re.campaign_id = %s
                ORDER BY el.ran_at DESC
                LIMIT %s
                """,
                (campaign_id, limit),
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(r) for r in rows]

    def get_by_id(self, log_id: str) -> Optional[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                """
                SELECT el.*, re.raw_payload, re.source_platform,
                    re.processing_status, re.campaign_id
                FROM lz_extraction_logs el
                JOIN lz_raw_events re ON re.event_id = el.event_id
                WHERE el.log_id = %s
                """,
                (log_id,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return dict(row) if row else None

    def get_stats(self) -> list[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute("""
                SELECT
                    extraction_status,
                    COUNT(*)         AS count,
                    AVG(duration_ms) AS avg_duration_ms
                FROM lz_extraction_logs
                GROUP BY extraction_status
                """)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(r) for r in rows]


repo = ExtractionRunRepository()
