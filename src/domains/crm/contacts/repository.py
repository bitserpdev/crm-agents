from psycopg2.extras import Json
from typing import Optional
from utils.uuid import new_id
from core.database import get_db, get_dict_cursor
from core.logger import logger


class CrmRepository:

    def list_contacts(
        self,
        search: Optional[str] = None,
        stage: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[dict]]:

        with get_db() as conn:
            cur = get_dict_cursor(conn)

            filters, values = [], []

            if search:
                filters.append(
                    "(LOWER(c.first_name||' '||c.last_name) LIKE %s "
                    "OR LOWER(c.email) LIKE %s "
                    "OR LOWER(c.job_title) LIKE %s)"
                )
                values += [f"%{search.lower()}%"] * 3
            if stage:
                filters.append("c.lifecycle_stage = %s")
                values.append(stage)

            where = f"WHERE {' AND '.join(filters)}" if filters else ""
            count_vals = values[:]

            cur.execute(
                f"""
                SELECT
                    c.contact_id, c.first_name, c.last_name,
                    c.email, c.job_title, c.contact_type,
                    c.lifecycle_stage, c.source_platform,
                    c.linkedin_url, c.created_at,
                    co.company_name, co.city, co.country,
                    s.intent_score, s.lead_score, s.overall_score,
                    ARRAY(SELECT tag_name FROM crm.crm_contact_tags
                        WHERE contact_id = c.contact_id) AS tags
                FROM crm.crm_contacts c
                LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                LEFT JOIN crm.crm_contact_scores s ON s.contact_id = c.contact_id
                {where}
                ORDER BY COALESCE(s.overall_score, 0) DESC, c.created_at DESC
                LIMIT %s OFFSET %s
                """,
                values + [limit, offset],
            )
            rows = cur.fetchall()

            cur.execute(
                f"SELECT COUNT(*) FROM crm.crm_contacts c {where}",
                count_vals,
            )
            total = cur.fetchone()["count"]

            cur.close()
            return total, [dict(r) for r in rows]

    def get_contact_by_id(self, contact_id: str) -> Optional[dict]:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                """
                SELECT c.*, co.company_name, co.city, co.country, co.industry,
                    co.website_url, co.linkedin_url AS company_linkedin,
                    s.intent_score, s.lead_score, s.fit_score,
                    s.engagement_score, s.overall_score, s.score_breakdown,
                    ARRAY(SELECT tag_name FROM crm.crm_contact_tags
                            WHERE contact_id = c.contact_id) AS tags
                FROM crm.crm_contacts c
                LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
                LEFT JOIN crm.crm_contact_scores s ON s.contact_id = c.contact_id
                WHERE c.contact_id = %s
                """,
                (contact_id,),
            )
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def list_leads(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:

        with get_db() as conn:
            cur = get_dict_cursor(conn)  # fixed: was overwriting conn

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

            where = f"WHERE {' AND '.join(filters)}" if filters else ""

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
                values + [limit, offset],
            )
            rows = cur.fetchall()
            cur.close()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM crm.crm_contacts)  AS total_contacts,
                    (SELECT COUNT(*) FROM crm.crm_leads)     AS total_leads,
                    (SELECT COUNT(*) FROM crm.crm_companies) AS total_companies,
                    (SELECT COUNT(*) FROM crm.crm_leads
                    WHERE lead_status = 'new')              AS new_leads,
                    (SELECT COUNT(*) FROM crm.crm_leads
                    WHERE lead_status = 'qualified')        AS qualified_leads,
                    (SELECT ROUND(AVG(overall_score))
                    FROM crm.crm_contact_scores)            AS avg_score,
                    (SELECT COUNT(*) FROM crm.crm_contacts
                    WHERE lifecycle_stage = 'subscriber')   AS subscribers,
                    (SELECT COUNT(*) FROM crm.crm_contact_scores
                    WHERE intent_score >= 0.7)              AS high_intent
                """)
            row = cur.fetchone()
            cur.close()
            return dict(row)

    def add_contact(self, contact_data: dict) -> dict:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                contact_id = contact_data.get("contact_id") or str(new_id())
                company_id = self._upsert_company(cur, contact_data)
                result = self._upsert_contact(cur, contact_id, company_id, contact_data)

                if contact_data.get("intent_score") or contact_data.get("lead_score"):
                    self._upsert_scores(cur, result["contact_id"], contact_data)

                self._insert_tags(
                    cur, result["contact_id"], contact_data.get("tags", [])
                )

                conn.commit()
                return dict(result)

            except Exception as e:
                conn.rollback()
                raise
            finally:
                cur.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _upsert_company(self, cur, contact_data: dict) -> Optional[str]:
        company_name = contact_data.get("company")
        if not company_name:
            return None

        cur.execute(
            "SELECT company_id FROM crm.crm_companies WHERE company_name ILIKE %s",
            (company_name,),
        )
        row = cur.fetchone()
        if row:
            return row["company_id"]

        company_id = str(new_id())
        cur.execute(
            """
            INSERT INTO crm.crm_companies (
                company_id, company_name, city, country, industry
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                company_id,
                company_name,
                contact_data.get("city"),
                contact_data.get("country"),
                contact_data.get("industry"),
            ),
        )
        return company_id

    def _upsert_contact(
        self, cur, contact_id: str, company_id: Optional[str], contact_data: dict
    ) -> dict:
        email = contact_data.get("email")

        # Check if contact already exists
        cur.execute(
            "SELECT contact_id FROM crm.crm_contacts WHERE email = %s",
            (email,),
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                """
                UPDATE crm.crm_contacts SET
                    first_name  = %s,
                    last_name   = %s,
                    job_title   = %s,
                    phone       = %s,
                    company_id  = %s,
                    linkedin_url = %s,
                    updated_at  = NOW()
                WHERE email = %s
                RETURNING contact_id, first_name, last_name, email
                """,
                (
                    contact_data.get("first_name"),
                    contact_data.get("last_name"),
                    contact_data.get("job_title"),
                    contact_data.get("phone"),
                    company_id,
                    contact_data.get("linkedin_url"),
                    email,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO crm.crm_contacts (
                    contact_id, company_id, first_name, last_name,
                    email, phone, job_title, linkedin_url,
                    contact_type, lifecycle_stage,
                    source_platform, dedup_key, created_by_agent
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING contact_id, first_name, last_name, email
                """,
                (
                    contact_id,
                    company_id,
                    contact_data.get("first_name"),
                    contact_data.get("last_name"),
                    email,
                    contact_data.get("phone"),
                    contact_data.get("job_title"),
                    contact_data.get("linkedin_url"),
                    contact_data.get("contact_type", "prospect"),
                    contact_data.get("lifecycle_stage", "subscriber"),
                    "csv-upload",
                    f"csv_{email}",
                    "csv-upload",
                ),
            )

        return cur.fetchone()

    def _upsert_scores(self, cur, contact_id: str, contact_data: dict) -> None:
        cur.execute(
            """
            INSERT INTO crm.crm_contact_scores (
                score_id, contact_id, lead_score,
                intent_score, overall_score,
                score_breakdown, scored_by_agent, last_scored_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (contact_id) DO UPDATE SET
                intent_score  = EXCLUDED.intent_score,
                lead_score    = EXCLUDED.lead_score,
                overall_score = EXCLUDED.overall_score,
                updated_at    = NOW()
            """,
            (
                str(new_id()),
                contact_id,
                contact_data.get("lead_score", 50),
                contact_data.get("intent_score", 0.5),
                contact_data.get("overall_score", 50),
                Json(contact_data.get("score_breakdown", {})),
                "csv-upload",
            ),
        )

    def _insert_tags(self, cur, contact_id: str, tags) -> None:
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        for tag in tags:
            if tag and len(tag) <= 80:
                try:
                    cur.execute(
                        """
                        INSERT INTO crm.crm_contact_tags
                            (tag_id, contact_id, tag_name, tagged_by)
                        VALUES (%s, %s, %s, 'csv-upload')
                        ON CONFLICT (contact_id, tag_name) DO NOTHING
                        """,
                        (str(new_id()), contact_id, tag[:80]),
                    )
                except Exception as e:
                    print(f"Failed to insert tag '{tag}' for contact {contact_id}: {e}")
                    raise

    def bulk_add_contacts(self, contacts: list[dict]) -> dict:
        results = {
            "total": len(contacts),
            "success": 0,
            "failed": 0,
            "errors": [],
            "contacts": [],
        }

        for idx, contact in enumerate(contacts):
            try:
                if not contact.get("email"):
                    raise ValueError("Email is required")
                added = self.add_contact(contact)
                results["success"] += 1
                results["contacts"].append(added)
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "row": idx + 2,
                        "email": contact.get("email", "Unknown"),
                        "error": str(e),
                    }
                )

        return results


repo = CrmRepository()
