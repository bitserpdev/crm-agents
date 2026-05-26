import os, uuid, time, requests
import psycopg2, psycopg2.extras, redis as redis_lib
from psycopg2.extras import Json
from agent3.state import Agent3State
from agent3.graph_auth import get_access_token

GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/me/sendMail"
r = redis_lib.from_url(os.getenv("REDIS_URL"))

def _check_rate_limit(user_id: str) -> bool:
    window = int(time.time() // 3600)
    key    = f"op:email_throttle:{user_id}:{window}"
    count  = r.incr(key)
    if count == 1:
        r.expire(key, 3600)
    return count > 200  # max 200 emails/hour

def _send_email(token: str, to: str, subject: str,
                html: str, text: str) -> dict:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_USER")
    msg["To"] = to
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))) as server:
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        server.sendmail(os.getenv("SMTP_USER"), to, msg.as_string())
    return {"status_code": 202, "ok": True}

def send_node(state: Agent3State) -> Agent3State:
    if not state.get("personalized"):
        state["run_status"] = "done"
        return state

    sent   = []
    failed = []
    run_id = state["run_id"]
    campaign_id = state["campaign_id"]
    from_addr   = state["campaign"].get("from_address", "")

    try:
        token = get_access_token(campaign_id)
    except ValueError as e:
        state["errors"].append(str(e))
        state["run_status"] = "failed"
        return state

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    total = len(state["personalized"])

    print(f"[agent3/send] Sending {total} emails via Microsoft Graph...")

    for i, item in enumerate(state["personalized"]):
        contact = item["contact"]
        to_email = contact.get("email", "")

        # Skip placeholder emails
        if "@placeholder.bits" in to_email or not to_email:
            print(f"[agent3/send] Skipping placeholder email: {to_email}")
            failed.append({**item, "error": "placeholder email"})
            continue

        # Rate limit check
        if _check_rate_limit(from_addr):
            print("[agent3/send] Rate limit hit — pausing 1 hour")
            state["errors"].append("Rate limit reached")
            break

        print(f"[agent3/send] {i+1}/{total} → {to_email}")

        try:
            recipient_id = str(uuid.uuid4())
            server_url = os.getenv("SERVER_URL", "http://localhost:8000")
            tracking_pixel = f'<img src="{server_url}/api/agent3/track/open/{recipient_id}" width="1" height="1" style="display:none" />'
            html_with_pixel = item["html"] + tracking_pixel
            result = _send_email(
                token=token,
                to=to_email,
                subject=item["subject"],
                html=html_with_pixel,
                text=item["text"],
            )

            if result["ok"]:
                # INSERT crm_campaign_recipients
                cur.execute("""
                    INSERT INTO crm.crm_campaign_recipients
                        (recipient_id, run_id, contact_id,
                         delivery_status, sent_at)
                    VALUES (%s, %s, %s, 'sent', NOW())
                """, (recipient_id, run_id,
                      str(contact["contact_id"])))

                # INSERT crm_email_messages
                thread_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO crm.crm_email_threads
                        (thread_id, contact_id, imap_thread_id,
                         subject, thread_status, last_message_at)
                    VALUES (%s, %s, %s, %s, 'active', NOW())
                """, (thread_id, str(contact["contact_id"]),
                      f"agent3_{recipient_id}",
                      item["subject"]))

                cur.execute("""
                    INSERT INTO crm.crm_email_messages
                        (message_id, thread_id, direction,
                         from_address, to_addresses,
                         subject, body_html, body_text,
                         sent_at, sent_by_agent)
                    VALUES (%s, %s, 'outbound', %s, %s, %s, %s, %s, NOW(), 'agent-3-email')
                """, (str(uuid.uuid4()), thread_id,
                      from_addr, [to_email],
                      item["subject"], item["html"], item["text"]))

                conn.commit()
                sent.append({**item,
                             "recipient_id": recipient_id,
                             "thread_id": thread_id})
                print(f"[agent3/send] ✓ Sent to {to_email}")

                # Push to Redis queue for tracking
                r.lpush(f"op:campaign_run:{run_id}:queue",
                        str(contact["contact_id"]))
                r.hset(f"op:campaign_run:{run_id}:progress",
                       mapping={"sent_count": len(sent),
                                "failed_count": len(failed)})

                time.sleep(0.5)  # gentle rate limiting

            else:
                raise ValueError(f"Graph API returned {result['status_code']}")

        except Exception as e:
            conn.rollback()
            msg = f"Failed to send to {to_email}: {e}"
            print(f"[agent3/send] ✗ {msg}")
            failed.append({**item, "error": str(e)})

            # Record failed recipient
            cur.execute("""
                INSERT INTO crm.crm_campaign_recipients
                    (recipient_id, run_id, contact_id,
                     delivery_status, error_message)
                VALUES (%s, %s, %s, 'failed', %s)
            """, (str(uuid.uuid4()), run_id,
                  str(contact["contact_id"]), str(e)))
            conn.commit()

    cur.close(); conn.close()
    state["sent"]   = sent
    state["failed"] = failed
    print(f"[agent3/send] Done — {len(sent)} sent, {len(failed)} failed")
    return state
