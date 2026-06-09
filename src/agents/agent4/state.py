from typing import TypedDict, Optional, Any

class Agent4State(TypedDict):
    response_id:       str
    contact_id:        str
    campaign_id:       str
    contact:           dict
    campaign:          dict
    response:          dict
    sequence:          Optional[dict]
    thread_history:    list
    intent_label:      str
    intent_score:      float
    reply_subject:     str
    reply_body:        str
    call_situation:    str
    zoom_meeting_url: Optional[str]
    sent:              bool
    run_status:        str
    errors:            list
