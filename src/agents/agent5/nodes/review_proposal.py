from agents.agent5.state import Agent5State

def review_proposal_node(state: Agent5State) -> Agent5State:
    print("[Agent5/review] Reviewing proposal...")

    proposal = state.get("proposal_text", "")
    errors = []

    # basic quality checks
    if len(proposal) < 200:
        errors.append("Proposal too short (< 200 chars)")

    if not any(tech in proposal for tech in [
        "data", "analytics", "ML", "AI", "pipeline",
        "Python", "model", "automation", "insight"
    ]):
        errors.append("Proposal missing BITS technical keywords")

    if proposal.strip().startswith("Dear Client,\n\nWe at BITS"):
        errors.append("Proposal is generic fallback template")

    if errors:
        print(f"[Agent5/review] Failed: {errors}")
        state["review_status"]   = "needs_revision"
        state["review_feedback"] = "; ".join(errors)
    else:
        print("[Agent5/review] Proposal approved")
        state["review_status"]   = "approved"
        state["review_feedback"] = ""

    return state