import json
from agents.agent2.state import Agent2State
from core.llm import get_llm, LLMFormat
from core.logger import logger
from agents.agent2.prompt import EXTRACT_PROMPT

llm = get_llm(fmt=LLMFormat.JSON)

BAD_COMPANIES = {
    "python", "developer", "engineer", "manager", "analyst",
    "designer", "consultant", "django", "javascript", "react",
    "nodejs", "aws", "azure",
}


def extract_node(state: Agent2State) -> Agent2State:
    if not state["raw_events"]:
        state["run_status"] = "done"
        return state

    extracted = []
    total     = len(state["raw_events"])
    logger.info("[agent2/extract] Starting", total=total)

    for i, event in enumerate(state["raw_events"]):
        try:
            payload  = event.get("raw_payload", {})
            raw      = payload.get("raw", {})
            rec_type = payload.get("type", "profile")

            llm_input = {
                "type":            rec_type,
                "name":            payload.get("name", ""),
                "current_title":   raw.get("current_title", payload.get("current_title", "")),
                "headline":        payload.get("headline", raw.get("headline", "")),
                "company":         payload.get("company", raw.get("current_company", "")),
                "current_company": raw.get("current_company", ""),
                "email":           payload.get("email", raw.get("email", "")),
                "url":             payload.get("url", raw.get("url", "")),
                "location":        raw.get("location_normalized", payload.get("location", {})),
                "skills":          raw.get("skills", payload.get("skills", [])),
                "intent_score":    payload.get("intent_score", 0.5),
                "summary":         payload.get("summary", ""),
                "title":           payload.get("title", ""),
                "description":     payload.get("description", ""),
            }

            response = llm.invoke([
                ("system", EXTRACT_PROMPT),
                ("human",  json.dumps(llm_input, default=str)),
            ])

            if not response or not response.content:
                logger.warning("[agent2/extract] Empty LLM response", index=i)
                continue

            result = _parse_llm_response(response.content)
            if not result:
                continue

            result = _fix_email(result, llm_input)
            result = _fix_company(result, llm_input)

            if not isinstance(result.get("tags"), list):
                result["tags"] = []

            result["_event_id"]    = str(event["event_id"])
            result["_dedup_key"]   = event.get("dedup_key", "")
            result["_platform"]    = event.get("source_platform", "linkedin")
            result["_campaign_id"] = str(event["campaign_id"]) if event.get("campaign_id") else None
            result["_received_at"] = str(event.get("received_at", ""))

            extracted.append(result)
            logger.info("[agent2/extract] Extracted",
                        name=f"{result.get('first_name','')} {result.get('last_name','')}",
                        title=result.get("job_title", ""))

        except Exception as e:
            logger.error("[agent2/extract] Error", index=i, error=str(e))
            state["errors"].append(f"Extract error: {str(e)}")

    logger.info("[agent2/extract] Done", extracted=len(extracted), total=total)
    state["extracted_records"] = extracted
    return state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_llm_response(content: str) -> dict | None:
    text = content.strip()
    if "```" in text:
        parts = text.split("```")
        text  = parts[1] if len(parts) > 1 else parts[0]
        if text.startswith("json"):
            text = text[4:]
    s = text.find("{")
    e = text.rfind("}") + 1
    if s >= 0 and e > s:
        try:
            return json.loads(text[s:e].strip())
        except json.JSONDecodeError:
            return None
    return None


def _fix_email(result: dict, llm_input: dict) -> dict:
    email = result.get("email", "")
    if not email or "{linkedin_id}" in email or "@" not in email:
        url    = llm_input.get("url", "")
        url_id = url.rstrip("/").split("/")[-1] if url else "unknown"
        result["email"] = f"linkedin_{url_id}@placeholder.bits"
    return result


def _fix_company(result: dict, llm_input: dict) -> dict:
    company = result.get("company_name", "")
    if company.lower() in BAD_COMPANIES or len(company) < 2:
        result["company_name"] = (
            llm_input.get("current_company") or
            llm_input.get("company") or ""
        )
    return result