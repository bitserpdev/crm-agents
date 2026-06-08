from agent.state import AgentState

def route_node(state: AgentState) -> AgentState:
    if state["run_status"] == "failed":
        return state

    if state["sources_pending"]:
        state["current_source"] = state["sources_pending"].pop(0)
        state["run_status"]     = "running"
        print(f"[route] Processing source: {state['current_source']}")
    else:
        state["current_source"] = None
        state["run_status"]     = "done"
        print("[route] All sources processed — done")

    return state

def should_continue(state: AgentState) -> str:
    if state["run_status"] in ("done", "failed"):
        return "done"
    return "extract"
