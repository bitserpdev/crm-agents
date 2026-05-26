import json, re
from langchain_ollama import ChatOllama
from agent4.state import Agent4State

llm = ChatOllama(
    model="llama3.2",
    base_url="http://localhost:11434",
    temperature=0.4,
    timeout=60,
    num_predict=600,
)

CALL_KEYWORDS = [
    "call", "meeting", "available", "availability", "schedule",
    "free", "talk", "discuss", "connect", "chat", "zoom", "teams",
    "video", "phone", "time", "slot", "book", "appointment",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "morning", "afternoon", "am", "pm", "week"
]

def detect_call_intent(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in CALL_KEYWORDS)

SYSTEM_PROMPT = """You are a professional B2B sales representative at BITS Global Consulting.
Write a concise, professional email reply based on the conversation and situation.

Rules:
- Under 120 words maximum
- Warm, human, professional — never robotic or salesy
- Reference specific details from their message
- Sign off: BITS Global Consulting Team

Situation rules:
- ask_availability: They want a call. Ask ONE question: what times work this week or next? Nothing else.
- send_teams: You have their availability. Confirm the time, include [TEAMS_LINK], express excitement.
- general_reply: They replied after call was scheduled. Respond professionally and warmly. Keep conversation going.
- warm: Ask one thoughtful question to understand their needs. Hint toward a call.
- cold: One clear value statement. Leave door open gently. No pressure.
- unsubscribe: Thank them, confirm removal. Short and respectful.

Return ONLY valid JSON — no markdown, no explanation:
{"subject": "Re: <their subject>", "body": "email body"}"""

def build_context(state: Agent4State) -> str:
    contact   = state["contact"]
    campaign  = state["campaign"]
    history   = state["thread_history"]
    situation = state.get("call_situation", "warm")

    name    = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
    company = contact.get("company_name", "your company")
    title   = contact.get("job_title", "")
    service = campaign.get("service_description", "our services")

    ctx = f"Contact: {name}, {title} at {company}\nService: {service}\nSituation: {situation}\n\nRecent conversation:\n"

    for msg in history[-6:]:
        who = "BITS" if msg["direction"] == "outbound" else name
        ctx += f"\n[{who}]: {msg['body'][:350]}\n"

    ctx += f"\nLatest message from {name}:\n{state['response']['reply_body'][:500]}"

    if situation == "send_teams":
        ctx += "\n\nIMPORTANT: Put [TEAMS_LINK] in the email body where the meeting link goes."

    return ctx

def generate_response_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    intent     = state["intent_label"]
    sequence   = state.get("sequence") or {}
    reply_body = state.get("response", {}).get("reply_body", "")
    seq_status = sequence.get("status", "active")

    print(f"[agent4/generate] intent={intent} seq_status={seq_status}")

    # ── If sequence already call_scheduled — just reply professionally ───────
    # Do NOT ask for availability again, do NOT create another meeting
    if seq_status in ("call_scheduled",):
        state["call_situation"] = "general_reply"
        situation = "general_reply"
        print(f"[agent4/generate] Call already scheduled — general reply only")

    # ── Unsubscribe — fixed template ─────────────────────────────────────────
    elif intent == "unsubscribe":
        name = state["contact"].get("first_name", "there")
        state["reply_subject"] = "Re: Unsubscribe Request"
        state["reply_body"] = f"""Hi {name},

Thank you for letting us know. I've removed you from our mailing list and you won't receive any further emails from us.

We appreciate your time and wish you all the best.

Warm regards,
BITS Global Consulting Team"""
        state["call_situation"] = "unsubscribe"
        return state

    else:
        # ── Detect call intent ───────────────────────────────────────────────
        is_call_intent = (
            intent in ("hot", "call_requested") or
            detect_call_intent(reply_body)
        )

        asked_availability = sequence.get("asked_availability", False)
        has_teams_meeting  = bool(sequence.get("teams_meeting_url"))

        if is_call_intent and has_teams_meeting:
            situation = "general_reply"
        elif is_call_intent and asked_availability:
            # They replied with their availability → send Teams link now
            situation = "send_teams"
            state["intent_label"] = "call_requested"
        elif is_call_intent and not asked_availability:
            # First time call mentioned → ask for availability ONCE
            situation = "ask_availability"
            state["intent_label"] = "call_requested"
        else:
            situation = intent if intent in ("warm", "cold") else "warm"

        state["call_situation"] = situation

    print(f"[agent4/generate] situation={situation} asked_avail={sequence.get('asked_availability')} has_teams={bool(sequence.get('teams_meeting_url'))}")

    # ── Generate with LLM ────────────────────────────────────────────────────
    try:
        context  = build_context(state)
        response = llm.invoke([("system", SYSTEM_PROMPT), ("human", context)])
        text = re.sub(r"```json\s*|\s*```", "", response.content.strip()).strip()
        result = json.loads(text)
        state["reply_subject"] = result.get("subject", "Following up")
        state["reply_body"]    = result.get("body", "")

    except Exception as e:
        print(f"[agent4/generate] LLM error: {e} — fallback")
        name = state["contact"].get("first_name", "there")
        state["reply_subject"] = "Following up"

        if situation == "ask_availability":
            state["reply_body"] = f"""Hi {name},

Thank you for your interest — I'd love to set up a quick call to explore how BITS Global Consulting can support your goals.

What times work best for you this week or next?

Best regards,
BITS Global Consulting Team"""

        elif situation == "send_teams":
            state["reply_body"] = f"""Hi {name},

I've set up a Teams meeting for us at the time you mentioned. Please use the link below to join:

[TEAMS_LINK]

Looking forward to speaking with you!

Best regards,
BITS Global Consulting Team"""

        elif situation == "general_reply":
            state["reply_body"] = f"""Hi {name},

Thank you for your message. Looking forward to our upcoming call — please let me know if there's anything specific you'd like to cover.

Best regards,
BITS Global Consulting Team"""

        else:
            state["reply_body"] = f"""Hi {name},

Thank you for getting back to me. I'd love to understand your needs better — would you be open to a quick 20-minute call this week?

Best regards,
BITS Global Consulting Team"""

    print(f"[agent4/generate] ✓ {state['reply_subject']} (situation={situation})")
    return state
