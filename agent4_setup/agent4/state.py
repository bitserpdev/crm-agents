from typing import TypedDict, List, Optional

class Agent4State(TypedDict):
    # Input
    response_id:        str
    contact_id:         str
    campaign_id:        str
    run_id:             str

    # Loaded data
    contact:            dict
    campaign:           dict
    response:           dict          # the incoming reply from crm_campaign_responses
    thread_history:     List[dict]    # full conversation so far
    sequence:           Optional[dict] # existing follow-up sequence if any

    # Generated
    reply_subject:      str
    reply_body:         str
    intent_label:       str
    intent_score:       float
    teams_meeting_url:  Optional[str]

    # Output
    sent:               bool
    errors:             List[str]
    run_status:         str           # done | failed | skipped
