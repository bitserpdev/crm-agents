from langgraph.graph import StateGraph, END
from agent3.state import Agent3State
from agent3.nodes.fetch       import fetch_node
from agent3.nodes.personalize import personalize_node
from agent3.nodes.send        import send_node
from agent3.nodes.record      import record_node

def should_continue(state: Agent3State) -> str:
    if state["run_status"] in ("done", "failed"):
        return "done"
    if not state.get("contacts"):
        return "done"
    return "continue"

def build_agent3_graph():
    g = StateGraph(Agent3State)
    g.add_node("fetch",       fetch_node)
    g.add_node("personalize", personalize_node)
    g.add_node("send",        send_node)
    g.add_node("record",      record_node)

    g.set_entry_point("fetch")
    g.add_conditional_edges("fetch", should_continue,
        {"continue": "personalize", "done": END})
    g.add_edge("personalize", "send")
    g.add_edge("send",        "record")
    g.add_edge("record",      END)

    return g.compile()
