import json
import os

import psycopg2
from psycopg2.extras import RealDictCursor

from agents.agent4.processed import agent4_already_replied


def normalize_reply_queue(r) -> int:
    """
    Collapse the reply queue to one pending item per contact (newest first).
    Drops items Agent 4 already handled.
    Returns the number of items left in the queue.
    """
    raw_items = r.lrange("op:reply_queue", 0, -1)
    if not raw_items:
        return 0

    parsed: list[dict] = []
    for raw in raw_items:
        try:
            parsed.append(json.loads(raw))
        except json.JSONDecodeError:
            continue

    if not parsed:
        r.delete("op:reply_queue")
        return 0

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=RealDictCursor)

    best_by_contact: dict[str, tuple] = {}
    for item in parsed:
        response_id = item.get("response_id")
        contact_id = str(item.get("contact_id", ""))
        if not response_id or not contact_id:
            continue
        if agent4_already_replied(cur, response_id):
            continue

        cur.execute(
            """
            SELECT responded_at, intent_label
            FROM crm.crm_campaign_responses
            WHERE response_id = %s
            """,
            (response_id,),
        )
        row = cur.fetchone()
        if not row:
            continue
        if row.get("intent_label") == "out_of_office":
            continue

        ts = row["responded_at"]
        prev = best_by_contact.get(contact_id)
        if not prev or ts > prev[0]:
            best_by_contact[contact_id] = (ts, item)

    cur.close()
    conn.close()

    r.delete("op:reply_queue")
    for _, item in sorted(best_by_contact.values(), key=lambda x: x[0]):
        # lpush newest last so the head of the list is the most recent reply
        r.lpush("op:reply_queue", json.dumps(item))

    return len(best_by_contact)


def queue_response_for_agent4(r, response_id: str, contact_id: str, campaign_id: str, run_id: str, *, queued_at: str):
    """Push a response onto the queue, replacing any older pending item for the same contact."""
    queue_item = json.dumps(
        {
            "response_id": str(response_id),
            "contact_id": str(contact_id),
            "campaign_id": str(campaign_id),
            "run_id": str(run_id),
            "queued_at": queued_at,
        }
    )

    for raw in r.lrange("op:reply_queue", 0, -1):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            r.lrem("op:reply_queue", 1, raw)
            continue
        if str(data.get("contact_id")) == str(contact_id):
            r.lrem("op:reply_queue", 1, raw)

    r.lpush("op:reply_queue", queue_item)
