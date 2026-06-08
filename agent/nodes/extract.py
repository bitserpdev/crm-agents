import os
from agent.state import AgentState
from connectors.registry import get_connector

def extract_node(state: AgentState) -> AgentState:
    """Extract leads using Apify LinkedIn scraper."""
    campaign_cfg   = state.get("campaign_config", {})
    source_configs = campaign_cfg.get("source_configs", [])

    records = []

    for src in source_configs:
        platform = src.get("type")
        if not platform:
            continue

        print(f"[extract] No webhook events — polling {platform}")
        connector = get_connector(platform)
        platform_records = connector.poll(src)
        print(f"[Apify] Got {len(platform_records)} records")
        records.extend(platform_records)

    print(f"[extract] Got {len(records)} records from {platform}")
    state["raw_records"] = records
    return state
