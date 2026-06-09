from psycopg2.extras import Json
from core.database import get_conn, get_dict_cursor
from agent3.state import Agent3State


def record_node(state: Agent3State) -> Agent3State:
    run_id = state["run_id"]
    sent = len(state.get("sent", []))
    failed = len(state.get("failed", []))

    conn = get_conn()
    cur = get_dict_cursor(conn)

    # Update campaign run final stats
    cur.execute(
        """
        UPDATE crm.crm_campaign_runs
        SET run_status   = %s,
            sent_count   = %s,
            failed_count = %s,
            completed_at = NOW()
        WHERE run_id = %s
    """,
        ("completed" if not state["errors"] else "failed", sent, failed, run_id),
    )

    # Log agent action
    cur.execute(
        """
        INSERT INTO crm.crm_agent_actions
            (action_id, agent_id, action_type,
             entity_type, entity_id, action_detail, outcome)
        VALUES (gen_random_uuid(), 'agent-3-email',
                'email_campaign_sent', 'campaign', %s, %s, %s)
    """,
        (
            state["campaign_id"],
            Json(
                {
                    "run_id": run_id,
                    "sent": sent,
                    "failed": failed,
                    "contact_ids": [
                        (e.get("contact") or {}).get("id")
                        or (e.get("contact") or {}).get("contact_id")
                        for e in state.get("sent", [])
                    ],
                    "errors": state["errors"][:3],
                }
            ),
            "success" if sent > 0 else "failed",
        ),
    )

    conn.commit()
    cur.close()
    conn.close()

    state["stats"] = {
        "sent": sent,
        "failed": failed,
        "total": len(state.get("contacts", [])),
    }
    state["run_status"] = "done"
    print(f"[agent3/record] Campaign run recorded — {sent} sent, {failed} failed")
    return state
