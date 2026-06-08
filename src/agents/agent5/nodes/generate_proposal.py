import os
import re
import uuid
import json
from agents.agent5.state import Agent5State
from langchain_ollama import ChatOllama
from agents.agent5.prompts import PROPOSAL_GENERATION_PROMPT

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")

llm = ChatOllama(
    model=OLLAMA_LLM_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.2,
    timeout=45,
)

def generate_proposal_node(state: Agent5State) -> Agent5State:

    state["iteration_count"] = state.get("iteration_count", 0) + 1
    print(f"[Agent5/generate] Generating proposal... iteration {state['iteration_count']}")

    # generate proposal_id once on first iteration
    if not state.get("proposal_id"):
        state["proposal_id"] = str(uuid.uuid4())


    print("[Agent5/generate] Generating proposal...")

    payload = state["raw_payload"]["raw"]
    analysis = state.get("job_analysis", {})

    title = payload.get("title", "")
    description = payload.get("description", "")
    budget = payload.get("budget", {})
    client = payload.get("client", {})

    # use enriched data from analyze_job_node
    pain_points = "\n".join(f"- {p}" for p in analysis.get("pain_points", []))
    goals = "\n".join(f"- {g}" for g in analysis.get("goals", []))
    requirements = analysis.get("requirements", payload.get("skills", []))
    selling_points = "\n".join(f"- {s}" for s in analysis.get("key_selling_points", []))
    client_type = analysis.get("client_type", "")

    prompt = PROPOSAL_GENERATION_PROMPT.format(
        title=title,
        description=description,
        budget=json.dumps(budget),
        skills=", ".join(requirements[:10]),
        client_info=json.dumps(client),
        client_type=client_type,
        pain_points=pain_points or "- Not specified",
        goals=goals or "- Not specified",
        selling_points=selling_points or "- Relevant BITS expertise",
    )

    print("[Agent5/generate] Calling LLM...")
    response = llm.invoke(prompt)
    proposal_text = response.content.strip()
    print("[Agent5/generate] LLM response:", proposal_text[:100], "...")

    if len(proposal_text) > 100:
        state["proposal_text"] = proposal_text
        print("[Agent5/generate] Proposal generated successfully")
    else:
        print("[Agent5/generate] Response too short, using fallback")
        state["proposal_text"] = (
            f"Dear Client,\n\nWe at BITS Global Consulting are excited about: {title}.\n\n"
            f"Our team specializes in Data Science, AI Agents, and Analytics.\n\n"
            f"Can we schedule a 15-minute discovery call?\n\nBest regards,\nBITS Team"
        )

    state["subject"]          = f"Proposal: {title}"
    state["proposal_version"] = state["iteration_count"]
    state["review_status"]    = "pending_review"
    state["run_status"]       = "running"
    
    return state
