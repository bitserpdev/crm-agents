from typing import TypedDict, List, Optional, Any

class AgentState(TypedDict):
    campaign_id:        str
    campaign_config:    dict
    sources_pending:    List[str]
    current_source:     Optional[str]
    raw_records:        List[dict]
    validated_records:  List[dict]
    errors:             List[str]
    agent_trace_id:     str
    run_status:         str          # running | done | failed
