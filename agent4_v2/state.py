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
    response:           dict
    thread_history:     List[dict]
    sequence:           Optional[dict]

    # Generated
    reply_subject:      str
    reply_body:         str
    intent_label:       str
    intent_score:       float
    call_situation:     str        # ask_availability | send_teams | general_reply | warm | cold | unsubscribe
    teams_meeting_url:  Optional[str]

    # Output
    sent:               bool
    errors:             List[str]
    run_status:         str
