import json
from core.database import get_co nn # noqa: F401 — available for other nodes if needed
from core.redis import get_redis
from agent4.state import Agent4State

REPLY_QUEUE = "op:reply_queue"


def pop_reply_node(state: Agent4State) -> Agent4State:
    """Pop one reply from Redis queue and load basic info."""
    print("[agent4/pop_reply] Checking reply queue...")
    r = get_redis()

    item = r.lpop(REPLY_QUEUE)
    if not item:
        print("[agent4/pop_reply] Queue empty — nothing to process")
        state["run_status"] = "skipped"
        return state

    try:
        data = json.loads(item)
    except Exception:
        print(f"[agent4/pop_reply] Invalid queue item: {item}")
        state["run_status"] = "skipped"
        return state

    state["response_id"] = data.get("response_id", "")
    state["contact_id"]  = data.get("contact_id",  "")
    state["campaign_id"] = data.get("campaign_id", "")
    state["run_id"]      = data.get("run_id",      "")
    state["errors"]      = []

    print(f"[agent4/pop_reply] Popped reply from contact {state['contact_id']}")
    state["run_status"] = "running"
    return state