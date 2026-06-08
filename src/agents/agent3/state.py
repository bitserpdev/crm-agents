from typing import TypedDict, List, Optional

class Agent3State(TypedDict):
    campaign_id:     str
    run_id:          str
    campaign:        dict
    contacts:        List[dict]   # filtered contacts to email
    personalized:    List[dict]   # {contact, subject, html, text}
    sent:            List[dict]   # successfully sent
    failed:          List[dict]   # failed sends
    errors:          List[str]
    agent_trace_id:  str
    run_status:      str          # running | done | failed
    stats:           dict
