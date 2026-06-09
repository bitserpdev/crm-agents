from core.database import get_conn, get_dict_cursor
from services.email import EmailMessage, email_service
from agents.agent3.state import Agent3State


def send_node(state: Agent3State) -> Agent3State:
    """Send personalized campaign emails and seed follow-up sequences."""
    personalized = state.get("personalized") or []
    if not personalized:
        state["sent"] = []
        state["failed"] = []
        return state

    campaign_id = state["campaign_id"]
    run_id = state["run_id"]
    sent: list[dict] = []
    failed: list[dict] = []

    print(f"[agent3/send] Sending {len(personalized)} emails...")

    for item in personalized:
        contact = item.get("contact") or {}
        contact_id = contact.get("id") or contact.get("contact_id")
        email = contact.get("email")

        if not email or not contact_id:
            failed.append({"contact": contact, "error": "missing email or contact_id"})
            continue

        success = email_service.send(
            EmailMessage(
                to=email,
                subject=item.get("subject", ""),
                body_text=item.get("text", ""),
                body_html=item.get("html"),
            )
        )

        if not success:
            failed.append({"contact": contact, "error": "smtp send failed"})
            _record_recipient(run_id, contact_id, "failed")
            continue

        try:
            from agents.agent4.seed_sequences import seed_outbound_sequence

            seed_outbound_sequence(
                campaign_id,
                contact_id,
                run_id=run_id,
                subject=item.get("subject", ""),
                body=item.get("text", ""),
            )
        except Exception as e:
            print(f"[agent3/send] Follow-up seed failed for {email}: {e}")
            _record_recipient(run_id, contact_id, "sent")
        else:
            sent.append({"contact": contact, "email": email})

    state["sent"] = sent
    state["failed"] = failed
    print(f"[agent3/send] Done — {len(sent)} sent, {len(failed)} failed")
    return state


def _record_recipient(run_id: str, contact_id: str, status: str) -> None:
    """Ensure recipient row exists when seed_outbound_sequence did not run."""
    conn = get_conn()
    cur = get_dict_cursor(conn)
    try:
        cur.execute(
            """
            INSERT INTO crm.crm_campaign_recipients
                (run_id, contact_id, delivery_status, sent_at)
            SELECT %s, %s, %s, CASE WHEN %s = 'sent' THEN NOW() ELSE NULL END
            WHERE NOT EXISTS (
                SELECT 1 FROM crm.crm_campaign_recipients
                WHERE run_id = %s AND contact_id = %s
            )
            """,
            (run_id, contact_id, status, status, run_id, contact_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
