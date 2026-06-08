from typing import Optional
from core.database import get_db, get_dict_cursor


class IngestionRepository:

    def list_raw_events(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        filters, values = [], []

        if platform:
            filters.append("source_platform = %s")
            values.append(platform)
        if status:
            filters.append("processing_status = %s")
            values.append(status)

        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        values += [limit, offset]

        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                f"""
                SELECT event_id, received_at, source_platform,
                    raw_payload, dedup_key, processing_status,
                    campaign_id, created_at
                FROM lz_raw_events
                {where}
                ORDER BY received_at DESC
                LIMIT %s OFFSET %s
                """,
                values,
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(r) for r in rows]

    def get_stats(self) -> list[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute("""
                SELECT
                    source_platform,
                    COUNT(*)                                              AS total_events,
                    COUNT(*) FILTER (WHERE processing_status = 'done')   AS done,
                    COUNT(*) FILTER (WHERE processing_status = 'duplicate') AS duplicates
                FROM lz_raw_events
                GROUP BY source_platform
                """)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(r) for r in rows]


repo = IngestionRepository()
