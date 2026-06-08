from agent.state import AgentState

def load_node(state: AgentState) -> AgentState:
    if not state["validated_records"]:
        print("[load] No validated records to load")
        return state

    # Import here to avoid circular imports
    from landing.postgres import write_to_landing_zone

    success = 0
    for record in state["validated_records"]:
        try:
            write_to_landing_zone(
                record       = record,
                campaign_id  = state["campaign_id"],
                trace_id     = state["agent_trace_id"]
            )
            success += 1
        except Exception as e:
            msg = f"[load] Failed to write record: {e}"
            print(msg)
            state["errors"].append(msg)

    print(f"[load] Wrote {success}/{len(state['validated_records'])} records to landing zone")
    return state
