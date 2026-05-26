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

# Keywords to detect call intent as backup to LLM classification
CALL_KEYWORDS = [
    "call", "meeting", "available", "availability", "schedule",
    "free", "talk", "discuss", "connect", "chat", "zoom", "teams",
    "video", "phone", "time", "slot", "book", "appointment"
]

def detect_call_intent(text: str) -> bool:
    """Keyword-based call intent detection as backup."""
    t = text.lower()
    return any(kw in t for kw in CALL_KEYWORDS)

SYSTEM_PROMPT = """You are a professional B2B sales representative at BITS Global Consulting.
Write a concise, professional email reply based on the conversation history and current situation.

Rules:
- Keep it under 150 words
- Sound human, warm, and professional — NOT salesy
- Reference specific context from the conversation
- Always sign off as: BITS Global Consulting Team

Situation-specific rules:
- ask_availability: Contact wants a call. Ask ONE clear question: what times work for them this week or next.
- send_teams: You have their availability. Send the Teams meeting link [TEAMS_LINK] with a warm confirmation.
- warm: Ask one relevant question to understand their needs better and move toward a call.
- cold: Provide one clear value statement, leave the door open gently.
- unsubscribe: Thank them politely, confirm removal.
- general_reply: Reply professionally to whatever they said, keep the conversation moving forward.

Return ONLY valid JSON:
{
  "subject": "Re: <original subject>",
  "body": "email body here"
}"""

def build_context(state: Agent4State) -> str:
    contact   = state["contact"]
    campaign  = state["campaign"]
    history   = state["thread_history"]
    situation = state.get("call_situation", state["intent_label"])

    name    = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
    company = contact.get("company_name", "your company")
    title   = contact.get("job_title", "")
    service = campaign.get("service_description", "our services")

    ctx = f"""
Contact: {name}, {title} at {company}
Service we offer: {service}
Current situation: {situation}
Follow-up step: {(state.get('sequence') or {}).get('current_step', 0) + 1}

Conversation history (most recent last):
"""
    for msg in history[-8:]:
        direction = "BITS" if msg["direction"] == "outbound" else name
        ctx += f"\n[{direction}]: {msg['body'][:400]}\n"

    ctx += f"\nLatest reply from {name}:\n{state['response']['reply_body'][:500]}"

    if situation == "send_teams":
        ctx += "\n\nNOTE: Include [TEAMS_LINK] in your email where the meeting link should appear."

    return ctx

def generate_response_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    intent     = state["intent_label"]
    sequence   = state.get("sequence") or {}
    reply_body = state.get("response", {}).get("reply_body", "")

    print(f"[agent4/generate] intent={intent}")

    # ── Unsubscribe — fixed template, no LLM ────────────────────────────────
    if intent == "unsubscribe":
        name = state["contact"].get("first_name", "there")
        state["reply_subject"] = "Re: Unsubscribe Request"
        state["reply_body"] = f"""Hi {name},

Thank you for letting us know. I've removed you from our mailing list and you won't receive any further emails from us.

We appreciate your time and wish you all the best.

Warm regards,
BITS Global Consulting Team"""
        state["call_situation"] = "unsubscribe"
        return state

    # ── Detect call intent (LLM label + keyword backup) ─────────────────────
    is_call_intent = (
        intent in ("hot", "call_requested") or
        detect_call_intent(reply_body)
    )

    # ── Determine exact situation based on call flow state ───────────────────
    asked_availability = sequence.get("asked_availability", False)
    has_teams_meeting  = bool(sequence.get("teams_meeting_url"))

    if is_call_intent and has_teams_meeting:
        # Teams link already sent — just reply professionally to their response
        situation = "general_reply"
    elif is_call_intent and asked_availability:
        # We already asked for availability — now create Teams meeting and send link
        situation = "send_teams"
        state["intent_label"] = "call_requested"
    elif is_call_intent and not asked_availability:
        # First time call mentioned — ask what time works
        situation = "ask_availability"
        state["intent_label"] = "call_requested"
    else:
        situation = intent  # warm / cold / general

    state["call_situation"] = situation
    print(f"[agent4/generate] situation={situation} asked_avail={asked_availability} has_teams={has_teams_meeting}")

    # ── Generate reply with LLM ──────────────────────────────────────────────
    try:
        context  = build_context(state)
        response = llm.invoke([
            ("system", SYSTEM_PROMPT),
            ("human",  context)
        ])
        text = response.content.strip()
        text = re.sub(r"```json\s*|\s*```", "", text).strip()
        result = json.loads(text)

        state["reply_subject"] = result.get("subject", "Following up")
        state["reply_body"]    = result.get("body", "")

    except Exception as e:
        print(f"[agent4/generate] LLM error: {e} — using fallback")
        name = state["contact"].get("first_name", "there")
        state["reply_subject"] = "Following up"
        if situation == "ask_availability":
            state["reply_body"] = f"""Hi {name},

Thank you for your interest! I'd love to set up a quick call to explore how BITS Global Consulting can support your goals.

What times work best for you this week or next?

Best regards,
BITS Global Consulting Team"""
        elif situation == "send_teams":
            state["reply_body"] = f"""Hi {name},

I've set up a Teams meeting for us — please use the link below to join:

[TEAMS_LINK]

Looking forward to speaking with you!

Best regards,
BITS Global Consulting Team"""
        else:
            state["reply_body"] = f"""Hi {name},

Thank you for your reply. I'd love to continue our conversation and explore how we can support your goals.

Would you be open to a quick 20-minute call this week?

Best regards,
BITS Global Consulting Team"""

    print(f"[agent4/generate] ✓ Generated: {state['reply_subject']} (situation={situation})")
    return state
