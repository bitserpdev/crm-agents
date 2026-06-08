from typing import Optional
from core.database import get_db, get_dict_cursor


class CrmRepository:

    def list_leads(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        filters, values = [], []

        if search:
            filters.append(
                "(LOWER(c.first_name||' '||c.last_name) LIKE %s "
                "OR LOWER(l.source_detail) LIKE %s)"
            )
            values += [f"%{search.lower()}%"] * 2
        if status:
            filters.append("l.lead_status = %s")
            values.append(status)

        where   = f"WHERE {' AND '.join(filters)}" if filters else ""
        values += [limit, offset]

        with get_db() as conn:
            cur  = get_dict_cursor(conn)
            cur.execute(
                f"""
                SELECT
                    l.lead_id, l.lead_status, l.lead_score,
                    l.source_platform, l.source_detail,
                    l.initial_message, l.created_at,
                    l.estimated_value, l.currency,
                    c.first_name, c.last_name, c.job_title, c.email,
                    co.company_name,
                    s.intent_score, s.overall_score
                FROM crm.crm_leads l
                JOIN crm.crm_contacts c ON c.contact_id = l.contact_id
                LEFT JOIN crm.crm_companies co ON co.company_id = l.company_id
                LEFT JOIN crm.crm_contact_scores s ON s.contact_id = c.contact_id
                {where}
                ORDER BY COALESCE(l.lead_score, 0) DESC, l.created_at DESC
                LIMIT %s OFFSET %s
                """,
                values,
            )
            rows = cur.fetchall()
            cur.close(); conn.close()
            return [dict(r) for r in rows]

repo = CrmRepository()