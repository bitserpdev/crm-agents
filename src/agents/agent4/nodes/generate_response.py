import json
import re

from agents.agent4.state import Agent4State
from agents.agent4.prompts import SYSTEM_PROMPT, CLASSIFIER_PROMPT
from core.llm import get_llm, LLMFormat
from utils.email_reply import (
    extract_case_study_clients,
    has_proposed_meeting_time,
    is_scheduling_request,
    polish_reply_body,
    reply_has_unauthorized_scheduling,
    strip_quoted_reply,
    wants_more_info,
)

llm = get_llm(LLMFormat.JSON)


def is_substantive_info_request(text: str) -> bool:
    """Reply shares business context or asks to learn more — not a scheduling confirmation."""
    return wants_more_info(text)


def validate_situation(situation: str, state: Agent4State) -> str:
    """Override LLM misclassifications using thread state and reply content."""
    reply = clean_prospect_reply(state)
    sequence = state.get("sequence") or {}
    seq_status = sequence.get("status", "")
    has_zoom = bool(
        sequence.get("teams_meeting_url") or sequence.get("zoom_meeting_url")
    )
    scheduling = is_scheduling_request(reply)
    proposed_time = has_proposed_meeting_time(reply)

    # Substantive info replies can contain words like "establishing" / "commonly"
    # that previously triggered false send_zoom — require scheduling intent too.
    if (
        proposed_time
        and is_substantive_info_request(reply)
        and not scheduling
        and not any(p in reply.lower() for p in ("works for me", "i'm available", "i am available"))
    ):
        print("[agent4/classify] Ignoring false proposed_time — prospect asked for info, not a slot")
        proposed_time = False

    if proposed_time:
        if situation != "send_zoom":
            print(f"[agent4/classify] {situation} → send_zoom (prospect proposed date/time)")
        return "send_zoom"

    if situation == "send_zoom" and not proposed_time:
        override = "more_info" if wants_more_info(reply) else "ask_availability"
        print(f"[agent4/classify] send_zoom → {override} (no explicit date/time in reply)")
        return override

    if wants_more_info(reply) and not scheduling and not proposed_time:
        if situation in ("warm", "ask_availability", "cold", "general_reply"):
            print(f"[agent4/classify] {situation} → more_info (prospect wants details first)")
            return "more_info"

    if situation == "general_reply" and seq_status != "call_scheduled" and not has_zoom:
        override = "more_info" if wants_more_info(reply) else "warm"
        print(f"[agent4/classify] general_reply → {override} (no meeting scheduled yet)")
        return override

    if situation == "ask_availability" and not scheduling and wants_more_info(reply):
        print("[agent4/classify] ask_availability → more_info (prospect asked for details first)")
        return "more_info"

    if situation == "warm" and not scheduling and wants_more_info(reply):
        print("[agent4/classify] warm → more_info (substantive questions in reply)")
        return "more_info"

    return situation


def clean_prospect_reply(state: Agent4State) -> str:
    """Return the prospect reply with quoted thread content removed."""
    raw = state.get("response", {}).get("reply_body", "")
    return strip_quoted_reply(raw)


# ─────────────────────────────────────────────
# CLASSIFIER
# ─────────────────────────────────────────────

def classify_situation(state: Agent4State) -> str:
    """
    Detect the correct situation from the prospect reply.
    Rule-based checks run first; LLM handles ambiguous cases only.
    """
    contact = state["contact"]
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    history = state["thread_history"]
    reply = clean_prospect_reply(state)[:500]
    sequence = state.get("sequence") or {}

    scheduling = is_scheduling_request(reply)
    proposed_time = has_proposed_meeting_time(reply)

    # ── Rule-based fast path (do not trust LLM for clear cases) ──
    if wants_more_info(reply) and not proposed_time and not scheduling:
        print("[agent4/classify] Rule match → more_info (prospect asked for details)")
        return "more_info"

    if proposed_time:
        print("[agent4/classify] Rule match → send_zoom (explicit date/time in reply)")
        return "send_zoom"

    if wants_more_info(reply) and not scheduling:
        print("[agent4/classify] Rule match → more_info (prospect asked for details)")
        return "more_info"

    if scheduling and not proposed_time:
        print("[agent4/classify] Rule match → ask_availability (scheduling request, no time yet)")
        return "ask_availability"

    thread_text = ""
    for msg in history[-4:]:
        who = "BITS" if msg["direction"] == "outbound" else name
        thread_text += f"\n[{who}]: {msg['body'][:300]}\n"

    seq_ctx = (
        f"\nThread state: asked_availability={sequence.get('asked_availability', False)}, "
        f"meeting_scheduled={sequence.get('status') == 'call_scheduled'}, "
        f"has_meeting_link={bool(sequence.get('teams_meeting_url'))}"
    )

    context = (
        f"Conversation so far:\n{thread_text}"
        f"\nLatest reply from {name}:\n{reply}"
        f"{seq_ctx}"
    )

    try:
        classifier_llm = get_llm(LLMFormat.JSON)
        response = classifier_llm.invoke([
            ("system", CLASSIFIER_PROMPT),
            ("human", context)
        ])
        text = re.sub(r"```json\s*|\s*```", "", response.content.strip()).strip()
        result = json.loads(text)
        situation = result.get("situation", "warm")
        reasoning = result.get("reasoning", "")
        situation = validate_situation(situation, state)
        print(f"[agent4/classify] situation={situation} | reason={reasoning}")
        return situation
    except Exception as e:
        print(f"[agent4/classify] Failed: {e} — defaulting to warm")
        return "warm"


# ─────────────────────────────────────────────
# CONTEXT BUILDER
# ─────────────────────────────────────────────

def build_context(state: Agent4State) -> str:
    contact = state["contact"]
    campaign = state["campaign"]
    history = state["thread_history"]
    situation = state.get("call_situation", "warm")

    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    company = contact.get("company_name", "your company")
    title = contact.get("job_title", "")
    service = campaign.get("service_description", "our services")

    ctx = (
        f"Contact: {name}, {title} at {company}\n"
        f"Service: {service}\n"
        f"YOUR TASK — Situation: {situation}\n"
        f"Intent detected: {state.get('intent_label', '')}\n\n"
        f"Recent conversation:\n"
    )

    for msg in history[-6:]:
        who = "BITS" if msg["direction"] == "outbound" else name
        ctx += f"\n[{who}]: {msg['body'][:350]}\n"

    prospect_reply = clean_prospect_reply(state)
    ctx += f"\nLatest message from {name}:\n{prospect_reply[:500]}"

    case_studies = extract_case_study_clients(history)
    if case_studies:
        ctx += (
            f"\n\nCase studies mentioned in this thread (use these names explicitly): "
            f"{', '.join(case_studies)}"
        )

    # Situation-specific instructions injected into context
    instructions = {
        "ask_availability": (
            "\n\nCRITICAL: No call has been scheduled yet. Do NOT suggest specific days "
            "(e.g. Tuesday, Wednesday) — the prospect did not mention any. Ask open-endedly "
            "what days and times work for them. Mention you can share case studies on the call."
        ),
        "send_zoom": (
            "\n\nCRITICAL: The prospect proposed a specific date/time for a call. "
            "Confirm the exact date and time they stated. Send the meeting link — put [ZOOM_LINK] "
            "exactly where the link should go. Do NOT pitch services or case studies — "
            "keep it short: confirm time, share link, express enthusiasm."
        ),
        "more_info": (
            f"\n\nCRITICAL: The prospect asked for more information about your services. "
            f"Answer their specific questions using this service context: {service}. "
            f"Acknowledge their situation in one short sentence — do NOT mirror their wording back. "
            f"Describe 2-3 concrete capabilities with outcomes they have not already mentioned. "
            f"Use ONLY client names from this thread's case-study list (if any) — never invent others. "
            f"Under 120 words. End with one soft question about a brief call. "
            f"Do NOT suggest next week, this week, or any specific day/time."
        ),
        "general_reply": (
            "\n\nCRITICAL: A call is already scheduled. Do NOT ask for availability again. "
            "Acknowledge their message warmly and ask if there is anything specific "
            "they would like to cover on the call."
        ),
        "warm": (
            "\n\nCRITICAL: Prospect is interested but not ready to commit. "
            "Add one specific value point, then make a soft ask for a 15-minute call."
        ),
        "not_interested": (
            "\n\nCRITICAL: Prospect is politely declining. Respect their decision, "
            "leave the door open briefly, and keep it under 3 sentences."
        ),
    }

    ctx += instructions.get(situation, "")
    return ctx


# ─────────────────────────────────────────────
# FALLBACKS
# ─────────────────────────────────────────────

def get_fallback_body(situation: str, name: str) -> str:
    fallbacks = {
        "ask_availability": (
            f"Hi {name},\n\nThank you for your interest — great to hear data governance "
            f"is a priority for your team.\n\nI'd love to set up a quick call and share "
            f"some relevant case studies. Could you confirm which days work best so I can "
            f"send over a calendar invite?\n\nBest regards,\nBITS Global Consulting Team"
        ),
        "send_zoom": (
            f"Hi {name},\n\nThank you — I've confirmed our call at the time you proposed. "
            f"Here is the meeting link:\n\n[ZOOM_LINK]\n\n"
            f"Looking forward to speaking with you.\n\n"
            f"Best regards,\nBITS Global Consulting Team"
        ),
        "more_info": (
            f"Hi {name},\n\n"
            f"Great to hear you're focused on data governance — inconsistent quality across "
            f"systems is exactly what our framework addresses. We typically start with a data "
            f"catalog and ownership model, then layer automated quality checks and compliance "
            f"controls so teams can move fast without losing control. For Vodafone, this cut "
            f"reporting errors and sped up audit readiness significantly.\n\n"
            f"Would a quick 15-minute call work to walk through how this applies to your setup?\n\n"
            f"Best regards,\nBITS Global Consulting Team"
        ),
        "general_reply": (
            f"Hi {name},\n\nThank you for your message — looking forward to our upcoming call. "
            f"Please let me know if there's anything specific you'd like to cover.\n\n"
            f"Best regards,\nBITS Global Consulting Team"
        ),
        "warm": (
            f"Hi {name},\n\nThank you for getting back to me. I'd love to understand your "
            f"needs better — would you be open to a quick 20-minute call this week?\n\n"
            f"Best regards,\nBITS Global Consulting Team"
        ),
        "not_interested": (
            f"Hi {name},\n\nCompletely understood — I appreciate you letting me know. "
            f"Feel free to reach out if anything changes down the line.\n\n"
            f"Best regards,\nBITS Global Consulting Team"
        ),
    }
    return fallbacks.get(
        situation,
        f"Hi {name},\n\nThank you for your message. I'll follow up with more details shortly.\n\n"
        f"Best regards,\nBITS Global Consulting Team"
    )


# ─────────────────────────────────────────────
# MAIN NODE
# ─────────────────────────────────────────────

def generate_response_node(state: Agent4State) -> Agent4State:
    if state.get("run_status") in ("skipped", "failed"):
        return state

    intent = state["intent_label"]
    name = state["contact"].get("first_name", "there")

    print(f"[agent4/generate] intent={intent}")

    if intent == "out_of_office":
        state["run_status"] = "skipped"
        state["call_situation"] = "out_of_office"
        print("[agent4/generate] Skipping out-of-office auto-reply")
        return state

    # ── Hard exit: unsubscribe ──────────────────
    if intent == "unsubscribe":
        state["reply_subject"] = "Re: Unsubscribe Request"
        state["reply_body"] = (
            f"Hi {name},\n\n"
            "Thank you for letting us know. I've removed you from our mailing list "
            "and you won't receive any further emails from us.\n\n"
            "We appreciate your time and wish you all the best.\n\n"
            "Warm regards,\nBITS Global Consulting Team"
        )
        state["call_situation"] = "unsubscribe"
        state["run_status"] = "done"
        return state

    # ── Classify situation ──────────────────────
    sequence = state.get("sequence") or {}
    if sequence.get("status") == "call_scheduled":
        situation = "general_reply"
        print("[agent4/generate] Call already scheduled — general reply only")
    else:
        situation = classify_situation(state)

    # Hard gate: never send a meeting link unless prospect named a date/time
    prospect_reply = clean_prospect_reply(state)
    if situation == "send_zoom" and not has_proposed_meeting_time(prospect_reply):
        situation = "more_info" if wants_more_info(prospect_reply) else "ask_availability"
        print(f"[agent4/generate] Blocked send_zoom — no explicit time → {situation}")

    state["call_situation"] = situation

    # ── Hard exit: not interested ───────────────
    if situation == "not_interested":
        state["reply_subject"] = "Re: Following Up"
        state["reply_body"] = get_fallback_body("not_interested", name)
        state["run_status"] = "done"
        return state

    # ── Generate reply via LLM ──────────────────
    try:
        context = build_context(state)
        response = llm.invoke([("system", SYSTEM_PROMPT), ("human", context)])
        text = re.sub(r"```json\s*|\s*```", "", response.content.strip()).strip()
        result = json.loads(text)
        state["reply_subject"] = result.get("subject", "Following up")
        state["reply_body"] = result.get("body", "")
        print(f"[agent4/generate] ✓ LLM reply generated (situation={situation})")

    except Exception as e:
        print(f"[agent4/generate] LLM error: {e} — using fallback")
        state["reply_subject"] = "Following up"
        state["reply_body"] = get_fallback_body(situation, name)

    state["reply_body"] = polish_reply_body(
        state.get("reply_body", ""),
        clean_prospect_reply(state),
        situation,
        state.get("thread_history", []),
    )

    # If sanitization stripped a hallucinated meeting reply, use the situation fallback.
    polished = (state.get("reply_body") or "").strip()
    prospect_reply = clean_prospect_reply(state)
    needs_fallback = situation in ("more_info", "warm", "ask_availability") and (
        len(polished.split()) < 25
        or reply_has_unauthorized_scheduling(polished, prospect_reply, situation)
    )
    if needs_fallback:
        fallback_situation = "more_info" if wants_more_info(prospect_reply) else situation
        print(f"[agent4/generate] Invalid or incomplete reply — using {fallback_situation} fallback")
        state["reply_body"] = get_fallback_body(fallback_situation, name)
        state["reply_body"] = polish_reply_body(
            state["reply_body"],
            prospect_reply,
            fallback_situation,
            state.get("thread_history", []),
        )

    print(f"[agent4/generate] ✓ {state['reply_subject']} (situation={situation})")
    return state