import json
import re
from core.database import get_db, get_dict_cursor
from services.email import EmailMessage, email_service


# ─────────────────────────────────────────────
# process_new_replies
# ─────────────────────────────────────────────
def process_new_replies():
    print("[agent4/monitor] Checking for new replies...")

    with get_db() as conn:
        cur = get_dict_cursor(conn)
        cur.execute("""
            SELECT r.response_id, r.contact_id, r.run_id,
                   r.intent_label, r.intent_score, r.reply_body,
                   cr.campaign_id
            FROM crm.crm_campaign_responses r
            JOIN crm.crm_campaign_runs cr ON cr.run_id = r.run_id
            WHERE r.queued_for_agent4 = FALSE
              AND r.contact_id IS NOT NULL
            ORDER BY r.responded_at ASC
            LIMIT 20
            """)
        replies = cur.fetchall()
        cur.close()

    if not replies:
        print("[agent4/monitor] No new replies")
        return

    # Mark ALL as queued BEFORE processing
    response_ids = [str(r["response_id"]) for r in replies]
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE crm.crm_campaign_responses SET queued_for_agent4 = TRUE WHERE response_id = ANY(%s)",
            (response_ids,),
        )
        conn.commit()
        cur.close()

    print(f"[agent4/monitor] Processing {len(replies)} replies")
    from agent4.graph import build_agent4_graph

    graph = build_agent4_graph()

    for reply in replies:
        try:
            print(
                f"[agent4/monitor] → {reply['intent_label']} from {str(reply['contact_id'])[:8]}..."
            )
            graph.invoke(
                {
                    "response_id": str(reply["response_id"]),
                    "contact_id": str(reply["contact_id"]),
                    "campaign_id": str(reply["campaign_id"]),
                    "contact": {},
                    "campaign": {},
                    "response": {},
                    "sequence": None,
                    "thread_history": [],
                    "intent_label": reply["intent_label"],
                    "intent_score": float(reply["intent_score"] or 0),
                    "reply_subject": "",
                    "reply_body": "",
                    "call_situation": "",
                    "teams_meeting_url": None,
                    "sent": False,
                    "run_status": "running",
                    "errors": [],
                }
            )
        except Exception as e:
            print(f"[agent4/monitor] Error processing {reply['response_id']}: {e}")
            # Reset to FALSE so it retries on next poll
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE crm.crm_campaign_responses SET queued_for_agent4 = FALSE WHERE response_id = %s",
                    (str(reply["response_id"]),),
                )
                conn.commit()
                cur.close()


# ─────────────────────────────────────────────
# send_followups
# ─────────────────────────────────────────────
def _build_followup_html(body: str) -> str:
    return (
        '<html><body style="font-family:Arial,sans-serif;font-size:14px;'
        'color:#333;max-width:600px;margin:0 auto;padding:20px;">'
        f"<p>{body.replace(chr(10), '<br>')}</p>"
        '<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">'
        '<p style="font-size:12px;color:#999;">BITS Global Consulting | erp@bitsglobalconsulting.com</p>'
        "</body></html>"
    )


def _generate_followup_content(llm, step: int, seq: dict) -> tuple[str, str]:
    name = f"{seq['first_name'] or ''} {seq['last_name'] or ''}".strip()
    service = seq["service_description"] or "our data and CRM solutions"
    company = seq["company_name"] or ""

    prompt = (
        f"You are a professional B2B sales rep at BITS Global Consulting.\n"
        f"Write follow-up email #{step} of 5 to {name}, {seq.get('job_title', '')} at {company}.\n"
        f"Service we offer: {service}\n"
        f"Be warm, concise, professional. Under 100 words. Vary the angle from previous emails.\n"
        f'Return ONLY valid JSON: {{"subject": "subject here", "body": "email body here"}}'
    )

    try:
        resp = llm.invoke([("system", prompt), ("human", f"Write follow-up {step}")])
        text = re.sub(r"```json\s*|\s*```", "", resp.content.strip()).strip()
        result = json.loads(text)
        return (
            result.get("subject", f"Following up — {seq['campaign_name']}"),
            result.get("body", ""),
        )
    except Exception:
        return (
            f"Following up — {seq['campaign_name']}",
            f"Hi {seq['first_name'] or 'there'},\n\nJust following up on my previous email about {service}.\n\nWould you be open to a quick call this week?\n\nBest regards,\nBITS Global Consulting Team",
        )


def send_followups():
    print("[agent4/followup] Checking pending follow-ups...")

    with get_db() as conn:
        cur = get_dict_cursor(conn)
        cur.execute("""
            SELECT s.sequence_id, s.campaign_id, s.contact_id,
                   s.current_step, s.max_steps,
                   c.email, c.first_name, c.last_name, c.job_title,
                   co.company_name,
                   camp.service_description, camp.campaign_name
            FROM crm.crm_follow_up_sequences s
            JOIN crm.crm_contacts c ON c.contact_id = s.contact_id
            LEFT JOIN crm.crm_companies co ON co.company_id = c.company_id
            LEFT JOIN crm.crm_campaigns camp ON camp.campaign_id = s.campaign_id
            WHERE s.status = 'active'
              AND s.last_reply_at IS NULL
              AND s.next_followup_at <= NOW()
              AND s.current_step < s.max_steps
              AND c.is_suppressed = FALSE
            ORDER BY s.next_followup_at ASC
            LIMIT 50
            """)
        sequences = cur.fetchall()
        cur.close()

    if not sequences:
        print("[agent4/followup] No pending follow-ups")
        return

    print(f"[agent4/followup] Sending {len(sequences)} follow-ups")

    from langchain_ollama import ChatOllama

    llm = ChatOllama(
        model="llama3.2",
        base_url="http://localhost:11434",
        temperature=0.4,
        timeout=60,
        num_predict=400,
    )

    for seq in sequences:
        try:
            email = seq["email"]
            if not email or "placeholder" in email.lower():
                continue

            step = int(seq["current_step"]) + 1
            subject, body = _generate_followup_content(llm, step, seq)

            success = email_service.send(
                EmailMessage(
                    to=email,
                    subject=subject,
                    body_text=body,
                    body_html=_build_followup_html(body),
                )
            )
            if not success:
                print(f"[agent4/followup] ✗ Failed to send FU{step} to {email}")
                continue

            # Single connection per sequence for INSERT + UPDATE
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO crm.crm_follow_up_emails
                        (sequence_id, contact_id, campaign_id,
                         step_number, direction, subject, body,
                         sent_at, delivery_status)
                    VALUES (%s, %s, %s, %s, 'outbound', %s, %s, NOW(), 'sent')
                    """,
                    (
                        str(seq["sequence_id"]),
                        str(seq["contact_id"]),
                        str(seq["campaign_id"]),
                        step,
                        subject,
                        body,
                    ),
                )

                if step >= int(seq["max_steps"]):
                    cur.execute(
                        """
                        UPDATE crm.crm_follow_up_sequences
                        SET current_step = %s, status = 'exhausted',
                            next_followup_at = NULL, updated_at = NOW()
                        WHERE sequence_id = %s
                        """,
                        (step, str(seq["sequence_id"])),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE crm.crm_follow_up_sequences
                        SET current_step = %s, status = 'active',
                            next_followup_at = NOW() + INTERVAL '3 days',
                            updated_at = NOW()
                        WHERE sequence_id = %s
                        """,
                        (step, str(seq["sequence_id"])),
                    )

                conn.commit()
                cur.close()

            print(f"[agent4/followup] ✓ FU{step} sent to {email}")

        except Exception as e:
            print(f"[agent4/followup] Error for sequence {seq.get('sequence_id')}: {e}")
