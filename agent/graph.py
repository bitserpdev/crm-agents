from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.plan     import plan_node
from agent.nodes.route    import route_node, should_continue
from agent.nodes.extract  import extract_node
from agent.nodes.validate import validate_node
from agent.nodes.load     import load_node

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("plan",     plan_node)
    g.add_node("route",    route_node)
    g.add_node("extract",  extract_node)
    g.add_node("validate", validate_node)
    g.add_node("load",     load_node)

    g.set_entry_point("plan")
    g.add_edge("plan",    "route")
    g.add_conditional_edges(
        "route",
        should_continue,
        {"extract": "extract", "done": END}
    )
    g.add_edge("extract",  "validate")
    g.add_edge("validate", "load")
    g.add_edge("load",     "route")   # loop back for next source

    return g.compile()
