import os, uuid, json, imaplib, email
from email.header import decode_header
from datetime import datetime, timedelta

from pydantic import Json
from core.llm import get_llm
from core.database import get_conn, get_dict_cursor
from agents.agent3.prompts import INTENT_PROMPT, PERSONALIZE_PROMPT

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
    """Push reply to Redis queue for Agent 4."""
    import redis as redis_lib

    _r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    queue_item = {
        "response_id": str(response_id),
        "contact_id": str(contact_id),
        "campaign_id": str(campaign_id),
        "run_id": str(run_id),
        "queued_at": datetime.now().isoformat(),
    }
    _r.rpush("op:reply_queue", json.dumps(queue_item))
    print(f"[agent3/monitor] → Queued for Agent 4: {response_id[:8]}...")


def monitor_replies(campaign_id: str):
    print(f"[agent3/monitor] Checking replies for campaign {campaign_id}")

    conn = get_conn()
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
        print(f"[agent3/monitor] No campaign run found — skipping")
        cur.close()
        conn.close()
        return
    run_id = str(run_row["run_id"])

    campaign_contacts = _get_campaign_contacts(cur, campaign_id)
    if not campaign_contacts:
        print(f"[agent3/monitor] No sent emails found — skipping")
        cur.close()
        conn.close()
        return

    print(f"[agent3/monitor] Watching {len(campaign_contacts)} contacts")

    try:
        mail = imaplib.IMAP4_SSL(os.getenv("SMTP_HOST"), 993)
        mail.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        mail.select("INBOX")
    except Exception as e:
        print(f"[agent3/monitor] IMAP connection failed: {e}")
        cur.close()
        conn.close()
        return

    since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
    status, data = mail.search(None, f"SINCE {since_date}")
    if status != "OK":
        mail.logout()
        cur.close()
        conn.close()
        return

    msg_ids = data[0].split()
    print(f"[agent3/monitor] Found {len(msg_ids)} messages in last 7 days")

    processed = skipped = already_done = 0

    for msg_id in msg_ids:
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

            # CHECK IF ALREADY PROCESSED
            cur.execute(
                """
                SELECT response_id, queued_for_agent4 
                FROM crm.crm_campaign_responses
                WHERE imap_message_id = %s OR (contact_id = %s AND reply_body IS NOT NULL)
                LIMIT 1
            """,
                (message_id, contact_id),
            )
            existing = cur.fetchone()

            if existing:
                already_done += 1
                # If exists but not queued, queue it now
                if not existing.get("queued_for_agent4"):
                    _queue_for_agent4(
                        existing["response_id"], contact_id, campaign_id, run_id
                    )
                    cur.execute(
                        """
                        UPDATE crm.crm_campaign_responses
                        SET queued_for_agent4 = TRUE
                        WHERE response_id = %s
                    """,
                        (existing["response_id"],),
                    )
                    conn.commit()
                    print(
                        f"[agent3/monitor] → Re-queued existing reply {existing['response_id'][:8]}..."
                    )
                continue

            # Get full message
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data[0]:
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            subject = _decode_str(msg.get("Subject", ""))
            body = _get_body(msg)

            if not body:
                continue

            dedup_key = (
                f"reply_{message_id}"[:60]
                if message_id
                else f"reply_{from_email}_{msg_id.decode()}"[:60]
            )
            intent = _classify_intent(body)
            thread_id = _get_or_create_thread(cur, contact_id, subject)

            # Insert into landing zone
            cur.execute(
                """
                INSERT INTO lz_raw_events
                    (event_id, received_at, source_platform,
                     raw_payload, dedup_key, processing_status)
                VALUES (gen_random_uuid(), NOW(), 'email', %s, %s, 'done')
                ON CONFLICT DO NOTHING
            """,
                (
                    Json(
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

            # Insert campaign response and get ID
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
                    intent.get("intent_label", "cold"),
                    message_id,
                ),
            )
            inserted = cur.fetchone()

            if inserted:
                response_id = str(inserted["response_id"])
                _queue_for_agent4(response_id, contact_id, campaign_id, run_id)

                # Mark as queued
                cur.execute(
                    """
                    UPDATE crm.crm_campaign_responses
                    SET queued_for_agent4 = TRUE
                    WHERE response_id = %s
                """,
                    (response_id,),
                )

            # Insert email message
            cur.execute(
                """
                INSERT INTO crm.crm_email_messages
                    (message_id, thread_id, direction, from_address,
                     to_addresses, subject, body_text,
                     received_at, sent_by_agent, imap_message_id)
                VALUES (gen_random_uuid(), %s, 'inbound', %s,
                        %s, %s, %s, NOW(), 'agent-3-monitor', %s)
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

            # Activity log
            cur.execute(
                """
                INSERT INTO crm.crm_activity_log
                    (activity_id, contact_id, activity_type,
                     activity_source, source_id, summary)
                VALUES (gen_random_uuid(), %s,
                        'email_received', 'agent', 'agent-3-monitor', %s)
            """,
                (contact_id, intent.get("summary", "Reply received")),
            )

            # Update lifecycle stage
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
            processed += 1
            print(f"[agent3/monitor] ✓ {from_email} — {intent.get('intent_label','?')}")

        except Exception as e:
            conn.rollback()
            print(f"[agent3/monitor] Error processing message: {e}")
            import traceback

            traceback.print_exc()

    cur.close()
    conn.close()
    mail.logout()
    print(
        f"[agent3/monitor] Done — processed={processed} already_done={already_done} skipped={skipped}"
    )
