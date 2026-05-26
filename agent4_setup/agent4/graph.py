from langgraph.graph import StateGraph, END
from agent4.state import Agent4State
from agent4.nodes.pop_reply import pop_reply_node
from agent4.nodes.load_thread import load_thread_node
from agent4.nodes.generate_response import generate_response_node
from agent4.nodes.send_reply import send_reply_node
from agent4.nodes.schedule_followups import schedule_followups_node
from agent4.nodes.record import record_node

def should_continue(state: Agent4State) -> str:
    if state.get("run_status") in ("skipped", "failed"):
        return "record"
    return "load_thread"

def build_graph():
    g = StateGraph(Agent4State)

    g.add_node("pop_reply",          pop_reply_node)
    g.add_node("load_thread",        load_thread_node)
    g.add_node("generate_response",  generate_response_node)
    g.add_node("send_reply",         send_reply_node)
    g.add_node("schedule_followups", schedule_followups_node)
    g.add_node("record",             record_node)

    g.set_entry_point("pop_reply")
    g.add_conditional_edges("pop_reply", should_continue,
                            {"load_thread": "load_thread",
                             "record":      "record"})
    g.add_edge("load_thread",        "generate_response")
    g.add_edge("generate_response",  "send_reply")
    g.add_edge("send_reply",         "schedule_followups")
    g.add_edge("schedule_followups", "record")
    g.add_edge("record",             END)

    return g.compile()

agent4_graph = build_graph()

def run_agent4():
    """Entry point called by scheduler."""
    initial_state = Agent4State(
        response_id="", contact_id="", campaign_id="", run_id="",
        contact={}, campaign={}, response={}, thread_history=[],
        sequence=None, reply_subject="", reply_body="",
        intent_label="", intent_score=0.0,
        teams_meeting_url=None, sent=False,
        errors=[], run_status="pending"
    )
    result = agent4_graph.invoke(initial_state)
    return result
