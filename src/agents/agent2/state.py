from typing import TypedDict, List, Optional

class Agent2State(TypedDict):
    trigger_type:       str          # realtime | batch
    raw_events:         List[dict]   # fetched from lz_raw_events
    extracted_records:  List[dict]   # after LLM extraction
    enriched_records:   List[dict]   # after company/contact dedup
    loaded_records:     List[dict]   # successfully written to crm.*
    errors:             List[str]
    agent_trace_id:     str
    run_status:         str          # running | done | failed
    stats:              dict         # counts per entity type
