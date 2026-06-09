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
            values += [limit, offset]

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
                values,
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
            conn = get_dict_cursor(conn)

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
            values += [limit, offset]

            cur = get_dict_cursor(conn)
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
            cur.close()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                """
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
                """
            )
            row = cur.fetchone()
            cur.close()
            return dict(row)

    def add_contact(self, contact_data: dict) -> dict:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            try:
                contact_id = contact_data.get("contact_id", str(new_id()))
                company_id = None

                company_name = contact_data.get("company")

                if company_name:
                    # Check if company exists
                    cur.execute(
                        """
                        SELECT company_id FROM crm.crm_companies 
                        WHERE company_name ILIKE %s
                    """,
                        (company_name,),
                    )
                    existing_company = cur.fetchone()

                    if existing_company:
                        company_id = existing_company["company_id"]
                    else:
                        # Create new company
                        company_id = str(new_id())

                        try:
                            cur.execute(
                                """
                                INSERT INTO crm.crm_companies (
                                    company_id, company_name, city, country, 
                                    industry
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

                        except Exception as e:
                            logger.error(
                                f"Company INSERT failed: {type(e).__name__}: {e}"
                            )
                            raise

                try:
                    # Insert contact
                    cur.execute(
                        """
                        INSERT INTO crm.crm_contacts (
                            contact_id, 
                            company_id, 
                            first_name, 
                            last_name,
                            email, 
                            phone, 
                            job_title, 
                            linkedin_url,
                            contact_type, 
                            lifecycle_stage,
                            source_platform, 
                            dedup_key, 
                            created_by_agent
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (email) DO UPDATE SET
                            first_name = EXCLUDED.first_name,
                            last_name = EXCLUDED.last_name,
                            job_title = EXCLUDED.job_title,
                            phone = EXCLUDED.phone,
                            company_id = EXCLUDED.company_id,
                            updated_at = NOW()
                        RETURNING contact_id, first_name, last_name, email
                    """,
                        (
                            contact_id,
                            company_id,
                            contact_data.get("first_name"),
                            contact_data.get("last_name"),
                            contact_data.get("email"),
                            contact_data.get("phone"),
                            contact_data.get("job_title"),
                            contact_data.get("linkedin_url"),
                            contact_data.get("contact_type", "prospect"),
                            contact_data.get("lifecycle_stage", "subscriber"),
                            "manual",
                            f"csv_{contact_data.get('email')}",
                            "csv-upload",
                        ),
                    )

                except Exception as e:
                    logger.error(f"Company INSERT failed: {type(e).__name__}: {e}")
                    raise

                result = cur.fetchone()

                # Add scores if provided
                if contact_data.get("intent_score") or contact_data.get("lead_score"):
                    cur.execute(
                        """
                        INSERT INTO crm.crm_contact_scores (
                            score_id, contact_id, lead_score,
                            intent_score, overall_score,
                            score_breakdown, scored_by_agent, last_scored_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (contact_id) DO UPDATE SET
                            intent_score = EXCLUDED.intent_score,
                            lead_score = EXCLUDED.lead_score,
                            overall_score = EXCLUDED.overall_score,
                            updated_at = NOW()
                    """,
                        (
                            str(new_id()),
                            result["contact_id"],
                            contact_data.get("lead_score", 50),
                            contact_data.get("intent_score", 0.5),
                            contact_data.get("overall_score", 50),
                            Json(contact_data.get("score_breakdown", {})),
                            "csv-upload",
                        ),
                    )

                # Add tags if provided
                tags = contact_data.get("tags", [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]

                for tag in tags:
                    if tag and len(tag) <= 80:
                        cur.execute(
                            """
                            INSERT INTO crm.crm_contact_tags
                                (tag_id, contact_id, tag_name, tagged_by)
                            VALUES (%s, %s, %s, 'csv-upload')
                            ON CONFLICT (contact_id, tag_name) DO NOTHING
                        """,
                            (str(new_id()), result["contact_id"], tag[:80]),
                        )

                conn.commit()

                return dict(result)

            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cur.close()

    def bulk_add_contacts(self, contacts: list[dict]) -> dict:
        """Bulk add multiple contacts with error handling"""
        results = {
            "total": len(contacts),
            "success": 0,
            "failed": 0,
            "errors": [],
            "contacts": [],
        }

        for idx, contact in enumerate(contacts):
            try:
                # Validate required fields
                if not contact.get("email"):
                    raise ValueError("Email is required")

                # Add contact
                added = self.add_contact(contact)
                results["success"] += 1
                results["contacts"].append(added)

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "row": idx + 2,  # +2 for header row (1-indexed + header)
                        "email": contact.get("email", "Unknown"),
                        "error": str(e),
                    }
                )

        return results


repo = CrmRepository()
