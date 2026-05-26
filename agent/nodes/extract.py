import os
from agent.state import AgentState

def extract_node(state: AgentState) -> AgentState:
    """Extract leads using Apify LinkedIn scraper."""
    campaign_cfg   = state.get("campaign_config", {})
    source_configs = campaign_cfg.get("source_configs", [])

    records = []

    for src in source_configs:
        if src.get("type") != "linkedin":
            continue

        print(f"[extract] No webhook events — polling linkedin")
        from connectors.apify_linkedin import ApifyLinkedInConnector
        connector = ApifyLinkedInConnector()
        profiles = connector.poll(src)
        print(f"[Apify] Got {len(profiles)} profiles")
        records.extend(profiles)

    print(f"[extract] Got {len(records)} records from linkedin")
    state["raw_records"] = records
    return state
