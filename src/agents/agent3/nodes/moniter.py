import os
import uuid
import json
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta

from core.llm import get_llm
from core.database import get_db, get_dict_cursor
from agents.agent3.prompts import INTENT_PROMPT, PERSONALIZE_PROMPT
from utils.email_reply import strip_quoted_reply

llm = get_llm()


def _decode_str(value):
    if not value:
        return ""
    parts = decode_header(value)
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="ignore")
        else:
            result += part
    return result


def _get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode("utf-8", errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="ignore")
    return body.strip()


def _extract_email(raw: str) -> str:
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        return raw.split("<")[1].split(">")[0].strip().lower()
    return raw.strip().lower()


def _classify_intent(body: str) -> dict:
    clean = body[:500].replace("<", "").replace(">", "")
    try:
        response = llm.invoke([("system", INTENT_PROMPT), ("human", clean)])
        text = response.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {
            "intent_label": "cold",
            "intent_score": 0.3,
            "summary": "Reply received",
        }


def _get_campaign_contacts(cur, campaign_id: str) -> dict:
    cur.execute(
        """
        SELECT LOWER(c.email) as email, c.contact_id
        FROM crm.crm_contacts c
        JOIN crm.crm_campaign_recipients r ON r.contact_id = c.contact_id
        JOIN crm.crm_campaign_runs cr ON cr.run_id = r.run_id
        WHERE cr.campaign_id = %s
          AND r.delivery_status = 'sent'
        """,
        (campaign_id,),
    )
    return {row["email"]: str(row["contact_id"]) for row in cur.fetchall()}


def _get_or_create_thread(cur, contact_id: str, subject: str) -> str:
    cur.execute(
        """
        SELECT thread_id FROM crm.crm_email_threads
        WHERE contact_id = %s
        ORDER BY last_message_at DESC LIMIT 1
        """,
        (contact_id,),
    )
    row = cur.fetchone()
    if row:
        thread_id = str(row["thread_id"])
        cur.execute(
            """
            UPDATE crm.crm_email_threads
            SET last_message_at = NOW(), thread_status = 'replied'
            WHERE thread_id = %s
            """,
            (thread_id,),
        )
        return thread_id

    thread_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO crm.crm_email_threads
            (thread_id, contact_id, imap_thread_id, subject,
             thread_status, last_message_at, created_at)
        VALUES (%s, %s, %s, %s, 'replied', NOW(), NOW())
        """,
        (
            thread_id,
            contact_id,
            f"reply_{thread_id[:8]}",
            subject[:255] if subject else "Re: Campaign Email",
        ),
    )
    return thread_id


def _queue_for_agent4(response_id: str, contact_id: str, campaign_id: str, run_id: str):
    from core.redis import get_redis
    from agents.agent4.queue import queue_response_for_agent4

    r = get_redis()
    queue_response_for_agent4(
        r,
        response_id,
        contact_id,
        campaign_id,
        run_id,
        queued_at=datetime.now().isoformat(),
    )


def monitor_replies(campaign_id: str):
    print(f"[agent3/monitor] Checking replies for campaign {campaign_id}")

    # ── Phase 1: load campaign data ───────────────────────────────────────────
    with get_db() as conn:
        cur = get_dict_cursor(conn)

        cur.execute(
            """
            SELECT run_id FROM crm.crm_campaign_runs
            WHERE campaign_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (campaign_id,),
        )
        run_row = cur.fetchone()
        if not run_row:
            print("[agent3/monitor] No campaign run found — skipping")
            cur.close()
            return

        run_id = str(run_row["run_id"])
        campaign_contacts = _get_campaign_contacts(cur, campaign_id)
        cur.close()

    if not campaign_contacts:
        print("[agent3/monitor] No sent emails found — skipping")
        return

    print(f"[agent3/monitor] Watching {len(campaign_contacts)} contacts")

    # ── Phase 2: connect to IMAP ──────────────────────────────────────────────
    try:
        mail = imaplib.IMAP4_SSL(os.getenv("SMTP_HOST"), 993)
        mail.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        mail.select("INBOX")
    except Exception as e:
        print(f"[agent3/monitor] IMAP connection failed: {e}")
        return

    since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
    status, data = mail.search(None, f"SINCE {since_date}")
    if status != "OK":
        mail.logout()
        return

    msg_ids = data[0].split()
    print(f"[agent3/monitor] Found {len(msg_ids)} messages in last 7 days")

    processed = skipped = already_done = 0
    contacts_seen: set[str] = set()

    # ── Phase 3: newest messages first — one ingest per contact per run ────────
    for msg_id in reversed(msg_ids):
        try:
            status, hdr_data = mail.fetch(msg_id, "(RFC822.HEADER)")
            if status != "OK" or not hdr_data[0]:
                continue

            hdr_msg = email.message_from_bytes(hdr_data[0][1])
            from_email = _extract_email(hdr_msg.get("From", ""))
            message_id = hdr_msg.get("Message-ID", "").strip()

            if from_email not in campaign_contacts:
                skipped += 1
                continue

            contact_id = campaign_contacts[from_email]

            if contact_id in contacts_seen:
                skipped += 1
                continue

            with get_db() as conn:
                cur = get_dict_cursor(conn)

                # Dedup by IMAP Message-ID only — allow multiple replies per contact
                cur.execute(
                    """
                    SELECT response_id, queued_for_agent4
                    FROM crm.crm_campaign_responses
                    WHERE imap_message_id = %s
                    LIMIT 1
                    """,
                    (message_id,),
                )
                existing = cur.fetchone()

                if existing:
                    already_done += 1
                    from agents.agent4.processed import agent4_already_replied

                    if agent4_already_replied(cur, str(existing["response_id"])):
                        contacts_seen.add(contact_id)
                        cur.close()
                        continue

                    if not existing.get("queued_for_agent4"):
                        _queue_for_agent4(
                            existing["response_id"], contact_id, campaign_id, run_id
                        )
                        cur.execute(
                            "UPDATE crm.crm_campaign_responses SET queued_for_agent4 = TRUE WHERE response_id = %s",
                            (existing["response_id"],),
                        )
                        conn.commit()
                        print(
                            f"[agent3/monitor] → Re-queued pending reply {existing['response_id'][:8]}..."
                        )
                    contacts_seen.add(contact_id)
                    cur.close()
                    continue

                # Fetch full message
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data[0]:
                    cur.close()
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                subject = _decode_str(msg.get("Subject", ""))
                body = strip_quoted_reply(_get_body(msg))

                if not body:
                    cur.close()
                    continue

                dedup_key = (
                    f"reply_{message_id}"[:60]
                    if message_id
                    else f"reply_{from_email}_{msg_id.decode()}"[:60]
                )
                intent = _classify_intent(body)
                intent_label = intent.get("intent_label", "cold")

                if intent_label == "out_of_office":
                    print(f"[agent3/monitor] Skipping out-of-office from {from_email}")
                    contacts_seen.add(contact_id)
                    cur.close()
                    skipped += 1
                    continue

                thread_id = _get_or_create_thread(cur, contact_id, subject)

                cur.execute(
                    """
                    INSERT INTO lz_raw_events
                        (event_id, received_at, source_platform,
                         raw_payload, dedup_key, processing_status)
                    VALUES (gen_random_uuid(), NOW(), 'email', %s, %s, 'done')
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        json.dumps(
                            {
                                "from": from_email,
                                "subject": subject,
                                "body": body[:2000],
                                "message_id": message_id,
                                "campaign_id": campaign_id,
                                "intent": intent,
                            }
                        ),
                        dedup_key,
                    ),
                )

                cur.execute(
                    """
                    INSERT INTO crm.crm_campaign_responses
                        (response_id, run_id, contact_id,
                         reply_body, intent_score, intent_label,
                         responded_at, imap_message_id, queued_for_agent4)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, NOW(), %s, FALSE)
                    RETURNING response_id
                    """,
                    (
                        run_id,
                        contact_id,
                        body[:5000],
                        intent.get("intent_score", 0.3),
                        intent_label,
                        message_id,
                    ),
                )
                inserted = cur.fetchone()

                if inserted:
                    response_id = str(inserted["response_id"])
                    _queue_for_agent4(response_id, contact_id, campaign_id, run_id)
                    cur.execute(
                        "UPDATE crm.crm_campaign_responses SET queued_for_agent4 = TRUE WHERE response_id = %s",
                        (response_id,),
                    )

                contacts_seen.add(contact_id)

                cur.execute(
                    """
                    INSERT INTO crm.crm_email_messages
                        (message_id, thread_id, direction, from_address,
                         to_addresses, subject, body_text,
                         received_at, sent_by_agent, imap_message_id)
                    VALUES (gen_random_uuid(), %s, 'inbound', %s, %s, %s, %s, NOW(), 'agent-3-monitor', %s)
                    """,
                    (
                        thread_id,
                        from_email,
                        [os.getenv("SMTP_USER")],
                        subject,
                        body[:5000],
                        message_id,
                    ),
                )

                cur.execute(
                    """
                    INSERT INTO crm.crm_activity_log
                        (activity_id, contact_id, activity_type,
                         activity_source, source_id, summary)
                    VALUES (gen_random_uuid(), %s, 'email_received', 'agent', 'agent-3-monitor', %s)
                    """,
                    (contact_id, intent.get("summary", "Reply received")),
                )

                if intent.get("intent_label") in ("hot", "warm", "call_requested"):
                    new_stage = (
                        "opportunity"
                        if intent["intent_label"] in ("hot", "call_requested")
                        else "engaged"
                    )
                    cur.execute(
                        """
                        UPDATE crm.crm_contacts
                        SET lifecycle_stage = %s, updated_at = NOW()
                        WHERE contact_id = %s
                        """,
                        (new_stage, contact_id),
                    )

                conn.commit()
                cur.close()
                processed += 1
                print(
                    f"[agent3/monitor] ✓ {from_email} — {intent.get('intent_label', '?')}"
                )

        except Exception as e:
            print(f"[agent3/monitor] Error processing message: {e}")
            import traceback

            traceback.print_exc()

    mail.logout()
    print(
        f"[agent3/monitor] Done — processed={processed} already_done={already_done} skipped={skipped}"
    )
