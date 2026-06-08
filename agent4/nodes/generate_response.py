import json
import re

from agent4.state import Agent4State
from agents.agent4.prompts import SYSTEM_PROMPT
from core.llm import get_llm, LLMFormat

llm = get_llm(LLMFormat.TEXT)

CALL_KEYWORDS = [
    "call", "meeting", "available", "availability", "schedule",
    "free", "talk", "discuss", "connect", "chat", "zoom", "teams",
    "video", "phone", "time", "slot", "book", "appointment",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "morning", "afternoon", "am", "pm", "week",
]


def detect_call_intent(text: str) -> bool:
    return any(kw in text.lower() for kw in CALL_KEYWORDS)


def build_context(state: Agent4State) -> str:
    contact   = state["contact"]
    campaign  = state["campaign"]
    history   = state["thread_history"]
    situation = state.get("call_situation", "warm")

    name    = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    company = contact.get("company_name", "your company")
    title   = contact.get("job_title", "")
    service = campaign.get("service_description", "our services")

    ctx = (
        f"Contact: {name}, {title} at {company}\n"
        f"Service: {service}\n"
        f"Situation: {situation}\n\n"
        f"Recent conversation:\n"
    )
    for msg in history[-6:]:
        who  = "BITS" if msg["direction"] == "outbound" else name
        ctx += f"\n[{who}]: {msg['body'][:350]}\n"

    ctx += f"\nLatest message from {name}:\n{state['response']['reply_body'][:500]}"

    if situation == "send_zoom":
        ctx += "\n\nIMPORTANT: Put [ZOOM_LINK] in the email body where the meeting link goes."

    return ctx


def generate_response_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    intent     = state["intent_label"]
    sequence   = state.get("sequence") or {}
    reply_body = state.get("response", {}).get("reply_body", "")
    seq_status = sequence.get("status", "active")
    situation  = "warm"  # safe default; always overwritten below

    print(f"[agent4/generate] intent={intent} seq_status={seq_status}")

    if seq_status == "call_scheduled":
        situation = "general_reply"
        state["call_situation"] = situation
        print("[agent4/generate] Call already scheduled — general reply only")

    elif intent == "unsubscribe":
        name = state["contact"].get("first_name", "there")
        state["reply_subject"] = "Re: Unsubscribe Request"
        state["reply_body"]    = (
            f"Hi {name},\n\n"
            "Thank you for letting us know. I've removed you from our mailing list "
            "and you won't receive any further emails from us.\n\n"
            "We appreciate your time and wish you all the best.\n\n"
            "Warm regards,\nBITS Global Consulting Team"
        )
        state["call_situation"] = "unsubscribe"
        return state

    else:
        is_call_intent     = intent in ("hot", "call_requested") or detect_call_intent(reply_body)
        asked_availability = sequence.get("asked_availability", False)
        has_zoom_meeting   = bool(sequence.get("zoom_meeting_url"))

        if is_call_intent and has_zoom_meeting:
            situation = "general_reply"
        elif is_call_intent and asked_availability:
            situation = "send_zoom"
            state["intent_label"] = "call_requested"
        elif is_call_intent and not asked_availability:
            situation = "ask_availability"
            state["intent_label"] = "call_requested"
        else:
            situation = intent if intent in ("warm", "cold") else "warm"

        state["call_situation"] = situation

    print(
        f"[agent4/generate] situation={situation} "
        f"asked_avail={sequence.get('asked_availability')} "
        f"has_zoom={bool(sequence.get('zoom_meeting_url'))}"
    )

    # Generate with LLM
    try:
        context  = build_context(state)
        response = llm.invoke([("system", SYSTEM_PROMPT), ("human", context)])
        text     = re.sub(r"```json\s*|\s*```", "", response.content.strip()).strip()
        result   = json.loads(text)

        state["reply_subject"] = result.get("subject", "Following up")
        state["reply_body"]    = result.get("body", "")

    except Exception as e:
        print(f"[agent4/generate] LLM error: {e} — using fallback")
        name = state["contact"].get("first_name", "there")
        state["reply_subject"] = "Following up"

        fallbacks = {
            "ask_availability": (
                f"Hi {name},\n\nThank you for your interest — I'd love to set up a quick call "
                f"to explore how BITS Global Consulting can support your goals.\n\n"
                f"What times work best for you this week or next?\n\n"
                f"Best regards,\nBITS Global Consulting Team"
            ),
            "send_zoom": (
                f"Hi {name},\n\nI've set up a Zoom meeting for us at the time you mentioned. "
                f"Please use the link below to join:\n\n[ZOOM_LINK]\n\n"
                f"Looking forward to speaking with you!\n\n"
                f"Best regards,\nBITS Global Consulting Team"
            ),
            "general_reply": (
                f"Hi {name},\n\nThank you for your message. Looking forward to our upcoming call — "
                f"please let me know if there's anything specific you'd like to cover.\n\n"
                f"Best regards,\nBITS Global Consulting Team"
            ),
        }
        state["reply_body"] = fallbacks.get(
            situation,
            f"Hi {name},\n\nThank you for getting back to me. I'd love to understand your needs "
            f"better — would you be open to a quick 20-minute call this week?\n\n"
            f"Best regards,\nBITS Global Consulting Team",
        )

    print(f"[agent4/generate] ✓ {state['reply_subject']} (situation={situation})")
    return state