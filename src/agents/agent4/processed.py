"""Track whether Agent 4 already replied to a campaign response."""


def agent4_already_replied(cur, response_id: str) -> bool:
    """True if Agent 4 sent a reply for this response after it was received."""
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM crm.crm_activity_log a
            JOIN crm.crm_campaign_responses r ON r.contact_id = a.contact_id
            WHERE r.response_id = %s
              AND a.activity_type = 'agent4_reply'
              AND a.occurred_at >= r.responded_at
        ) AS replied
        """,
        (response_id,),
    )
    row = cur.fetchone()
    if not row:
        return False
    return bool(row["replied"] if isinstance(row, dict) else row[0])
