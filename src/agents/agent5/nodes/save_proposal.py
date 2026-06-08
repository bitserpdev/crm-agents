import os
import uuid
import psycopg2
import psycopg2.extras
from agents.agent5.state import Agent5State


def save_proposal_node(state: Agent5State) -> Agent5State:
    print("[Agent5/save] Saving proposal to DB...")

    conn = None
    try:
        # generate proposal_id first
        proposal_id = state.get("proposal_id") or str(uuid.uuid4())
        state["proposal_id"] = proposal_id

        payload = state["raw_payload"]["raw"]
        title = payload.get("title", "")

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
                INSERT INTO crm.crm_proposals (
                    proposal_id, 
                    proposal_title,
                    scope_text, 
                    cover_text,
                    proposal_status,
                    generated_by_agent
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (proposal_id) DO UPDATE SET
                    cover_text    = EXCLUDED.cover_text,
                    proposal_status = EXCLUDED.proposal_status
            """,
            (
                proposal_id,
                title,
                payload.get("description", ""),  # scope_text = job description
                state.get("proposal_text", ""),  # cover_text = generated proposal
                "pending_review",
                "agent5",
            ),
        )

        conn.commit()
        print(f"[Agent5/save] Saved proposal {proposal_id}")

    except Exception as e:
        print(f"[Agent5/save] DB error: {e}")
        state["errors"].append(f"DB save failed: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    state["review_status"] = "approved"
    state["run_status"] = "completed"
    return state
