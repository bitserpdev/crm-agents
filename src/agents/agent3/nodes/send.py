from typing import List
from core.database import get_conn, get_dict_cursor
from services.email import EmailMessage, email_service


def send_customized_emails(
    campaign_id: str, contact_ids: List[str], subject: str, body: str, html_body: str
):
    """Send customized email to multiple contacts, personalizing each."""

    conn = get_conn()
    cur = get_dict_cursor()

    messages: list[EmailMessage] = []

    for contact_id in contact_ids:
        # Get contact details
        cur.execute(
            """
            SELECT c.email, c.first_name, c.last_name, co.company_name
            FROM crm.crm_contacts c
            LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
            WHERE c.contact_id = %s
        """,
            (contact_id,),
        )
        contact = cur.fetchone()

        if not contact or not contact["email"]:
            skipped += 1
            continue

        email = contact["email"]
        first_name = contact["first_name"] or ""
        last_name = contact["last_name"] or ""
        company = contact["company_name"] or "your company"
        full_name = f"{first_name} {last_name}".strip()

        def personalize(text: str) -> str:
            return (
                text.replace("[Name]", full_name)
                .replace("[name]", first_name)
                .replace("[Company]", company)
                .replace("[company]", company)
            )

        messages.append(
            EmailMessage(
                to=email,
                subject=personalize(subject),
                body_text=personalize(body),
                body_html=personalize(html_body),
            )
        )

    cur.close()
    conn.close()

    result = email_service.send_bulk(messages)
    result["skipped"] = skipped
    return result
