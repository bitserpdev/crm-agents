from langgraph.graph import StateGraph, END
from agent2.state import Agent2State
from agent2.nodes.fetch   import fetch_node
from agent2.nodes.extract import extract_node
from agent2.nodes.enrich  import enrich_node
from agent2.nodes.load    import load_node
from agent2.nodes.embed   import embed_node

def should_continue(state: Agent2State) -> str:
    if state["run_status"] in ("done", "failed"):
        return "done"
    if not state.get("raw_events"):
        return "done"
    return "continue"

def build_agent2_graph():
    g = StateGraph(Agent2State)
    g.add_node("fetch",   fetch_node)
    g.add_node("extract", extract_node)
    g.add_node("enrich",  enrich_node)
    g.add_node("load",    load_node)
    g.add_node("embed",   embed_node)

    g.set_entry_point("fetch")
    g.add_conditional_edges("fetch", should_continue,
        {"continue": "extract", "done": END})
    g.add_edge("extract", "enrich")
    g.add_edge("enrich",  "load")
    g.add_edge("load",    "embed")
    g.add_edge("embed",   END)

    return g.compile()
