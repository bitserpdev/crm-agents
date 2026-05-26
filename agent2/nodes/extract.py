import json
from langchain_ollama import ChatOllama
from agent2.state import Agent2State

llm = ChatOllama(
    model="llama3.2",
    base_url="http://localhost:11434",
    temperature=0,
    timeout=40,
    num_predict=600,
)

EXTRACT_PROMPT = """
You are a CRM data extraction agent. Extract structured fields from a raw LinkedIn record.
Return ONLY a valid JSON object. No explanation. No markdown. No extra text.

Rules:
- first_name: first word of name field
- last_name: remaining words of name field (empty string if single name)
- job_title: use current_title or headline field — NOT company name
- company_name: use company or current_company field — must be a real company name, NOT a job title or skill
- company_domain: guess lowercase domain from company_name (e.g. "Google" → "google.com"), empty string if unknown
- email: use email field if present, otherwise use the last part of linkedin URL as: linkedin_URLID@placeholder.bits where URLID is extracted from the url field
- city: extract city name only from location field
- country_code: 2-letter ISO code (US, GB, IN, PK, AU etc) from location, empty string if unknown
- contact_type: always "prospect" for new LinkedIn records
- lifecycle_stage: always "subscriber" for new LinkedIn records
- intent_score: use existing intent_score value from input, default 0.5
- lead_score: multiply intent_score by 100 and round to integer
- tags: array of 3-5 lowercase skill/industry tags from skills, headline, or job_title (e.g. ["python", "backend", "aws", "senior"])
- summary: one sentence description of the person

For PROFILE records return exactly:
{
  "record_type": "profile",
  "first_name": "",
  "last_name": "",
  "email": "",
  "job_title": "",
  "linkedin_url": "",
  "company_name": "",
  "company_domain": "",
  "city": "",
  "country_code": "",
  "contact_type": "prospect",
  "lifecycle_stage": "subscriber",
  "intent_score": 0.5,
  "lead_score": 50,
  "tags": [],
  "summary": ""
}

For JOB records return exactly:
{
  "record_type": "job",
  "job_title": "",
  "company_name": "",
  "company_domain": "",
  "city": "",
  "country_code": "",
  "description": "",
  "source_detail": "",
  "intent_score": 0.5,
  "lead_score": 50,
  "tags": []
}
"""

def _extract_url_id(url: str) -> str:
    """Extract the profile ID from a LinkedIn URL."""
    if not url:
        return "unknown"
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else "unknown"

def extract_node(state: Agent2State) -> Agent2State:
    if not state["raw_events"]:
        state["run_status"] = "done"
        return state

    extracted = []
    total = len(state["raw_events"])
    print(f"[agent2/extract] Extracting {total} records with llama3.2...")

    for i, event in enumerate(state["raw_events"]):
        try:
            payload = event.get("raw_payload", {})
            raw     = payload.get("raw", {})
            rec_type = payload.get("type", "profile")

            print(f"[agent2/extract] {i+1}/{total} — {rec_type} | {payload.get('name', payload.get('title','?'))[:40]}")

            # Build enriched input for LLM
            llm_input = {
                "type":          rec_type,
                "name":          payload.get("name", ""),
                "current_title": raw.get("current_title", payload.get("current_title", "")),
                "headline":      payload.get("headline", raw.get("headline", "")),
                "company":       payload.get("company", raw.get("current_company", "")),
                "current_company": raw.get("current_company", ""),
                "email":         payload.get("email", raw.get("email", "")),
                "url":           payload.get("url", raw.get("url", "")),
                "location":      raw.get("location_normalized", payload.get("location", {})),
                "skills":        raw.get("skills", payload.get("skills", [])),
                "intent_score":  payload.get("intent_score", 0.5),
                "summary":       payload.get("summary", ""),
                "title":         payload.get("title", ""),
                "description":   payload.get("description", ""),
            }

            messages = [
                ("system", EXTRACT_PROMPT),
                ("human",  json.dumps(llm_input, default=str))
            ]

            response = llm.invoke(messages)
            text = response.content.strip()

            # Strip markdown fences
            if "```" in text:
                parts = text.split("```")
                text = parts[1] if len(parts) > 1 else parts[0]
                if text.startswith("json"):
                    text = text[4:]

            # Find JSON object in response
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            result = json.loads(text.strip())

            # Fix email if still has literal placeholder
            email = result.get("email", "")
            if not email or "{linkedin_id}" in email or "@" not in email:
                url_id = _extract_url_id(llm_input.get("url", ""))
                result["email"] = f"linkedin_{url_id}@placeholder.bits"

            # Fix company_name if it looks like a job title
            company = result.get("company_name", "")
            bad_companies = ["python", "developer", "engineer", "manager",
                             "analyst", "designer", "consultant", "django",
                             "javascript", "react", "nodejs", "aws", "azure"]
            if company.lower() in bad_companies or len(company) < 2:
                result["company_name"] = llm_input.get("current_company", "") or \
                                         llm_input.get("company", "") or ""

            # Ensure tags is a list
            if not isinstance(result.get("tags"), list):
                result["tags"] = []

            # Attach metadata
            result["_event_id"]    = str(event["event_id"])
            result["_dedup_key"]   = event.get("dedup_key", "")
            result["_platform"]    = event.get("source_platform", "linkedin")
            result["_campaign_id"] = str(event.get("campaign_id", "")) if event.get("campaign_id") else None
            result["_received_at"] = str(event.get("received_at", ""))

            extracted.append(result)
            print(f"[agent2/extract] ✓ {result.get('first_name','')} {result.get('last_name','')} | {result.get('job_title','')} @ {result.get('company_name','')}")

        except Exception as e:
            print(f"[agent2/extract] Error on event {i+1}: {e}")
            state["errors"].append(f"Extract error: {str(e)}")

    print(f"[agent2/extract] Extracted {len(extracted)}/{total}")
    state["extracted_records"] = extracted
    return state
