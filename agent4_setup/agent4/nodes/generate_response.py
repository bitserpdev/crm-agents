import json
from langchain_ollama import ChatOllama
from agent4.state import Agent4State

llm = ChatOllama(
    model="llama3.2",
    base_url="http://localhost:11434",
    temperature=0.4,
    timeout=60,
    num_predict=600,
)

SYSTEM_PROMPT = """You are a professional B2B sales representative at BITS Global Consulting.
Write a concise, professional email reply based on the conversation history and intent.

Rules:
- Keep it under 150 words
- Sound human, warm, and professional — NOT salesy
- Reference specific context from the conversation
- Always include a clear next step
- For hot/call_requested: propose a specific call time or share Teams link placeholder [TEAMS_LINK]
- For warm: ask a relevant question to move them forward
- For cold: provide one clear value statement and leave door open
- For unsubscribe: thank them politely and confirm removal
- Return ONLY JSON:
{
  "subject": "Re: <original subject>",
  "body": "email body here"
}
"""

def build_context(state: Agent4State) -> str:
    contact  = state["contact"]
    campaign = state["campaign"]
    history  = state["thread_history"]
    intent   = state["intent_label"]

    name     = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
    company  = contact.get("company_name", "your company")
    title    = contact.get("job_title", "")
    service  = campaign.get("service_description", "our services")

    ctx = f"""
Contact: {name}, {title} at {company}
Service we offer: {service}
Current intent: {intent}
Follow-up step: {(state.get('sequence') or {}).get('current_step', 0) + 1}

Conversation history:
"""
    for msg in history[-6:]:  # last 6 messages for context window
        direction = "US" if msg["direction"] == "outbound" else name
        ctx += f"\n[{direction}]: {msg['body'][:300]}\n"

    ctx += f"\nLatest reply from {name}:\n{state['response']['reply_body'][:500]}"
    return ctx

def generate_response_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    intent = state["intent_label"]
    print(f"[agent4/generate] Generating reply for intent={intent}")

    # Don't respond to unsubscribe with AI — use fixed template
    if intent == "unsubscribe":
        contact = state["contact"]
        name = contact.get("first_name", "there")
        state["reply_subject"] = "Re: Unsubscribe Request"
        state["reply_body"] = f"""Hi {name},

Thank you for letting us know. I've removed you from our mailing list and you won't receive any further emails from us.

We appreciate your time and wish you all the best.

Warm regards,
BITS Global Consulting Team"""
        return state

    try:
        context = build_context(state)
        response = llm.invoke([
            ("system", SYSTEM_PROMPT),
            ("human",  context)
        ])
        text = response.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())

        state["reply_subject"] = result.get("subject", "Following up")
        state["reply_body"]    = result.get("body", "")

    except Exception as e:
        print(f"[agent4/generate] LLM error: {e} — using fallback")
        contact  = state["contact"]
        name     = contact.get("first_name", "there")
        state["reply_subject"] = "Following up"
        state["reply_body"] = f"""Hi {name},

Thank you for your reply. I'd love to continue our conversation and explore how BITS Global Consulting can support your goals.

Would you be available for a quick 20-minute call this week?

Best regards,
BITS Global Consulting Team"""

    print(f"[agent4/generate] ✓ Reply generated: {state['reply_subject']}")
    return state
