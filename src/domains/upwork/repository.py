from typing import Optional
from core.database import get_db, get_dict_cursor


class UpworkRepository:

    def get_proposal_from_db(self, event_id: str) -> Optional[dict]:
        with get_db() as conn:
            cur  = get_dict_cursor(conn)
            try:
                cur.execute(
                    """
                    SELECT proposal_id, proposal_title,
                        cover_text AS proposal_text,
                        proposal_status, generated_by_agent, created_at
                    FROM crm.crm_proposals
                    WHERE cover_text ILIKE %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (f"%{event_id}%",),
                )
                row = cur.fetchone()
                return dict(row) if row else None
            finally:
                cur.close(); conn.close()

    def get_pending_jobs(self, limit: int = 20) -> list[dict]:
        with get_db() as conn:
            cur  = get_dict_cursor(conn)
            try:
                cur.execute(
                    """
                    SELECT
                        event_id,
                        raw_payload->>'title'            AS title,
                        raw_payload->>'budget'           AS budget,
                        raw_payload->>'experience_level' AS experience_level,
                        raw_payload->>'url'              AS url,
                        received_at
                    FROM lz_raw_events
                    WHERE source_platform = 'upwork'
                    AND processing_status = 'done'
                    ORDER BY received_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [dict(r) for r in cur.fetchall()]
            finally:
                cur.close(); conn.close()


repo = UpworkRepository()