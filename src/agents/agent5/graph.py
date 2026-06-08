from langgraph.graph import StateGraph, END
from agents.agent5.state import Agent5State
from agents.agent5.nodes.fetch_job import fetch_job_node
from agents.agent5.nodes.analyze_job import analyze_job_node
from agents.agent5.nodes.generate_proposal import generate_proposal_node
from agents.agent5.nodes.review_proposal import review_proposal_node
from agents.agent5.nodes.save_proposal import save_proposal_node
from config.logger import get_logger

logger = get_logger("graph")

MAX_ITERATIONS = 3

def should_continue(state: Agent5State) -> str:
    review_status = state.get("review_status", "pending")
    iteration = state.get("iteration_count", 0)
    
    logger.debug(f"should_continue: review_status={review_status}, iteration={iteration}")
    
    if review_status == "approved":
        logger.info("Proposal approved!")
        return "approved"
    if iteration >= MAX_ITERATIONS:
        logger.warning(f"Max iterations ({MAX_ITERATIONS}) reached, forcing approval")
        return "approved"
    if review_status == "needs_revision":
        logger.info(f"Revision requested (iteration {iteration + 1}/{MAX_ITERATIONS})")
        return "needs_revision"
    
    logger.debug("Waiting for review...")
    return "needs_revision"

def build_agent5_graph():
    logger.info("Building Agent 5 graph...")
    
    g = StateGraph(Agent5State)
    g.add_node("fetch_job", fetch_job_node)
    g.add_node("analyze_job", analyze_job_node)
    g.add_node("generate_proposal", generate_proposal_node)
    g.add_node("review_proposal", review_proposal_node)
    g.add_node("save_proposal",     save_proposal_node) 

    g.set_entry_point("fetch_job")
    g.add_edge("fetch_job", "analyze_job")
    g.add_edge("analyze_job", "generate_proposal")
    g.add_edge("generate_proposal", "review_proposal")
    g.add_edge( "save_proposal", END)  # always save after review, even if needs_revision

    g.add_conditional_edges(
        "review_proposal",
        should_continue,
        {
            "needs_revision": "generate_proposal",
            "approved": "save_proposal",
        },
    )

    logger.info("Agent 5 graph built successfully")
    return g.compile()