import os 
from langgraph.graph import StateGraph, END
from agents.agent6.state import Agent6State
from agents.agent6.nodes.fetch_jobs import fetch_jobs_node
from agents.agent6.nodes.deduplicate import deduplicate_jobs_node
from agents.agent6.nodes.build_email import build_email_node
from agents.agent6.nodes.send_email import send_email_node
from agents.agent6.nodes.record import record_node
from config.logger import get_logger

logger = get_logger("agent6.graph")


def build_agent6_graph():
    """Build the Agent 6 graph for daily digest."""
    logger.info("Building Agent 6 graph...")

    g = StateGraph(Agent6State)

    # Add nodes
    g.add_node("fetch_jobs", fetch_jobs_node)
    g.add_node("deduplicate", deduplicate_jobs_node)
    g.add_node("build_email", build_email_node)
    g.add_node("send_email", send_email_node)
    g.add_node("record", record_node)

    # Set edges
    g.set_entry_point("fetch_jobs")
    g.add_edge("fetch_jobs", "deduplicate")
    g.add_edge("deduplicate", "build_email")
    g.add_edge("build_email", "send_email")
    g.add_edge("send_email", "record")
    g.add_edge("record", END)

    logger.info("Agent 6 graph built successfully")
    return g.compile()


def run_agent6(filters: dict = None, recipient_email: str = None):
    """Convenience function to run Agent 6."""
    from dotenv import load_dotenv

    load_dotenv()

    if recipient_email is None:
        recipient_email = os.getenv("UPWORK_DIGEST_EMAIL")

    if filters is None:
        filters = {
            "query": os.getenv("UPWORK_DIGEST_QUERY", "python developer data engineer"),
            "jobType": ["hourly", "fixed"],
            "experienceLevel": ["intermediate", "expert"],
            "maxJobAge": {"value": 24, "unit": "hours"},
        }

    initial_state = {
        "filters": filters,
        "recipient_email": recipient_email,
        "jobs": [],
        "unique_jobs": [],
        "email_sent": False,
        "email_html": "",
        "email_text": "",
        "jobs_count": 0,
        "last_run_date": "",
        "sent_emails": [],
        "errors": [],
        "run_status": "running",
    }

    graph = build_agent6_graph()
    result = graph.invoke(initial_state)

    return result
