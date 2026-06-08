import os
import json
import redis
import threading
import uuid
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks

router = APIRouter(prefix="/api/agent5", tags=["Agent5"])
r = redis.from_url(os.getenv("REDIS_URL"))


class ReviewRequest(BaseModel):
    status: str  # approved | revision | rejected
    feedback: str = ""


# ─── Store proposal in Redis for frontend to fetch ───────────────────────────


def store_proposal(event_id: str, proposal_data: dict):
    """Store proposal in Redis with 1 hour expiry."""
    key = f"op:agent5:proposal:{event_id}"
    r.setex(key, 3600, json.dumps(proposal_data))
    print(f"[Agent5] Proposal stored for event {event_id}")


def get_proposal(event_id: str) -> dict:
    """Retrieve proposal from Redis."""
    key = f"op:agent5:proposal:{event_id}"
    data = r.get(key)
    if data:
        return json.loads(data)
    return None


def update_job_status(event_id: str, status: str, data: dict = None):
    """Update job status in Redis for frontend polling."""
    key = f"op:agent5:status:{event_id}"
    status_data = {
        "status": status,
        "updated_at": datetime.now().isoformat(),
        "data": data or {},
    }
    r.setex(key, 3600, json.dumps(status_data))


# ─── Background Runner ────────────────────────────────────────────────────────


def run_agent5_background(event_id: str):
    """Run Agent 5 in background thread and store results."""
    try:
        update_job_status(event_id, "running")

        from agents.agent5.graph import build_agent5_graph

        graph = build_agent5_graph()

        initial_state = {
            "event_id": event_id,
            "raw_payload": {},
            "title": "",
            "description": "",
            "url": "",
            "budget": {},
            "skills": [],
            "client": {},
            "proposal_id": None,
            "proposal_text": "",
            "proposal_version": 0,
            "review_status": "pending",
            "review_feedback": "",
            "iteration_count": 0,
            "submitted": False,
            "accepted": False,
            "email_campaign_triggered": False,
            "errors": [],
            "run_status": "running",
        }

        final_state = graph.invoke(initial_state)

        # Store the generated proposal in Redis for frontend
        proposal_data = {
            "event_id": event_id,
            "title": final_state.get("title", ""),
            "proposal_text": final_state.get("proposal_text", ""),
            "proposal_id": final_state.get("proposal_id"),
            "proposal_version": final_state.get("proposal_version", 0),
            "review_status": final_state.get("review_status", "pending"),
            "run_status": final_state.get("run_status", "done"),
            "errors": final_state.get("errors", []),
            "completed_at": datetime.now().isoformat(),
        }

        store_proposal(event_id, proposal_data)
        update_job_status(event_id, "completed", proposal_data)

        print(f"[Agent5] Job {event_id} completed successfully")

    except Exception as e:
        error_msg = str(e)
        print(f"[Agent5] Job {event_id} failed: {error_msg}")
        traceback.print_exc()

        error_data = {
            "event_id": event_id,
            "error": error_msg,
            "completed_at": datetime.now().isoformat(),
        }
        store_proposal(event_id, error_data)
        update_job_status(event_id, "failed", error_data)


# ─── API Endpoints ────────────────────────────────────────────────────────────


@router.post("/proposals/{proposal_id}/review")
def review_proposal(proposal_id: str, review: ReviewRequest):
    """Submit review for a proposal (human feedback)."""
    if review.status not in ("approved", "revision", "rejected"):
        raise HTTPException(
            status_code=400, detail="status must be: approved | revision | rejected"
        )

    key = f"op:proposal_review:{proposal_id}"
    try:
        r.rpush(
            key,
            json.dumps(
                {
                    "status": review.status,
                    "feedback": review.feedback,
                    "proposal_id": proposal_id,
                }
            ),
        )
        r.expire(key, 86400)  # expire after 24h
        print(
            f"[Agent5/review] Queued review for proposal {proposal_id}: {review.status}"
        )
        return {"status": "review_queued", "proposal_id": proposal_id}
    except redis.RedisError as e:
        print(f"[Agent5/review] Redis error: {e}")
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")


@router.post("/jobs/{event_id}/trigger")
def trigger_agent5(event_id: str, background_tasks: BackgroundTasks = None):
    from agents.agent5.graph import build_agent5_graph

    graph = build_agent5_graph()

    initial_state = {
        "event_id": event_id,
        "raw_payload": {},
        "title": "",
        "description": "",
        "url": "",
        "budget": {},
        "skills": [],
        "client": {},
        "proposal_id": None,
        "proposal_text": "",
        "proposal_version": 0,
        "review_status": "pending",
        "review_feedback": "",
        "iteration_count": 0,
        "submitted": False,
        "accepted": False,
        "email_campaign_triggered": False,
        "errors": [],
        "run_status": "running",
    }

    try:
        update_job_status(event_id, "running")
        final_state = graph.invoke(initial_state)  # synchronous

        proposal_data = {
            "event_id": event_id,
            "proposal_text": final_state.get("proposal_text", ""),
            "subject": final_state.get("subject", ""),
            "review_status": final_state.get("review_status", "pending_review"),
            "proposal_id": final_state.get("proposal_id"),
            "errors": final_state.get("errors", []),
        }

        store_proposal(event_id, proposal_data)
        update_job_status(event_id, "completed", proposal_data)

        # return proposal directly — no polling needed
        return {
            "status": "completed",
            "event_id": event_id,
            "proposal_text": final_state.get("proposal_text", ""),
            "subject": final_state.get("subject", ""),
            "review_status": final_state.get("review_status", "pending_review"),
            "errors": final_state.get("errors", []),
        }

    except Exception as e:
        update_job_status(event_id, "failed", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{event_id}/proposal")
def get_job_proposal(event_id: str):
    """Get the generated proposal for a job (poll this endpoint)."""
    import psycopg2
    import psycopg2.extras
    import redis

    r = redis.from_url(os.getenv("REDIS_URL"))

    # First check if proposal exists in database
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Look for proposal linked to this event (by checking cover_text for event_id)
    cur.execute(
        """
        SELECT proposal_id, proposal_title, cover_text as proposal_text, 
               proposal_status, generated_by_agent, created_at
        FROM crm.crm_proposals
        WHERE cover_text ILIKE %s
        ORDER BY created_at DESC
        LIMIT 1
    """,
        (f"%{event_id}%",),
    )

    proposal = cur.fetchone()

    if proposal:
        # Proposal found in database
        cur.close()
        conn.close()
        return {
            "event_id": event_id,
            "status": "completed",
            "proposal": {
                "text": proposal["proposal_text"],
                "title": proposal["proposal_title"],
                "review_status": proposal["proposal_status"],
                "proposal_id": proposal["proposal_id"],
                "created_at": proposal["created_at"],
            },
        }

    # Check if Agent 5 is still running for this job
    status_key = f"op:agent5:status:{event_id}"
    status_data = r.get(status_key)

    if status_data:
        status_info = json.loads(status_data)
        if status_info.get("status") == "running":
            cur.close()
            conn.close()
            return {
                "event_id": event_id,
                "status": "running",
                "proposal": None,
                "message": "Proposal generation in progress...",
            }

    # Check if proposal generation was triggered but not started
    trigger_key = f"op:agent5:trigger:{event_id}"
    if r.get(trigger_key):
        cur.close()
        conn.close()
        return {
            "event_id": event_id,
            "status": "queued",
            "proposal": None,
            "message": "Proposal generation queued...",
        }

    cur.close()
    conn.close()

    # No proposal found
    return {
        "event_id": event_id,
        "status": "pending",
        "proposal": None,
        "message": "No proposal yet. Click 'Write Proposal' to generate.",
    }


@router.get("/jobs/{event_id}/status")
def get_job_status(event_id: str):
    """Get the status of a job."""
    status_key = f"op:agent5:status:{event_id}"
    try:
        data = r.get(status_key)
        if not data:
            # Check if proposal exists
            proposal = get_proposal(event_id)
            if proposal:
                return {
                    "event_id": event_id,
                    "status": proposal.get("run_status", "done"),
                    "updated_at": proposal.get("completed_at"),
                }
            raise HTTPException(status_code=404, detail="Job not found")
        return json.loads(data)
    except redis.RedisError as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")


@router.get("/jobs/pending")
def get_pending_jobs(limit: int = 20):
    """Get Upwork jobs that don't have proposals yet."""
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Simplified query - get all Upwork jobs
    cur.execute(
        """
        SELECT 
            event_id, 
            raw_payload->>'title' as title, 
            raw_payload->>'budget' as budget,
            raw_payload->>'experience_level' as experience_level,
            raw_payload->>'url' as url,
            received_at
        FROM lz_raw_events
        WHERE source_platform = 'upwork'
          AND processing_status = 'done'
        ORDER BY received_at DESC
        LIMIT %s
    """,
        (limit,),
    )

    jobs = cur.fetchall()
    cur.close()
    conn.close()

    # Convert to list and add proposal status from Redis or DB
    result = []
    for job in jobs:
        # Check if proposal exists in crm_proposals
        proposal_status = "pending"
        proposal_id = None

        # You can optionally check existing proposals here
        # For now, just return pending status

        result.append(
            {
                "event_id": job["event_id"],
                "title": job["title"] or "Untitled",
                "budget": job.get("budget"),
                "experience_level": job.get("experience_level"),
                "url": job.get("url"),
                "posted_date": job.get("received_at"),
                "proposal_status": proposal_status,
                "proposal_id": proposal_id,
            }
        )

    return {"data": result}


@router.get("/proposals/{proposal_id}/pending")
def get_pending_proposal(proposal_id: str):
    """Check if a proposal is waiting for human review."""
    try:
        # proposal stored by generate_proposal_node
        key = f"op:proposal:{proposal_id}"
        data = r.get(key)
        if not data:
            raise HTTPException(status_code=404, detail="Proposal not found")
        return json.loads(data)
    except redis.RedisError as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")
