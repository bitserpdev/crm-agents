import json
from langchain_ollama import ChatOllama
from agent.state import AgentState
from agent.prompts import VALIDATION_PROMPT

llm = ChatOllama(
    model="llama3.2",
    base_url="http://localhost:11434",
    temperature=0,
    timeout=45,
    num_predict=256,
)

MANAGEMENT_TIERS = {
    "c_suite": ["ceo", "cto", "cfo", "coo", "cmo", "ciso", "chief"],
    "vp": ["vp ", "vice president", "svp", "evp"],
    "director": ["director"],
    "manager": ["manager", "head of", "lead"],
    "individual": ["engineer", "analyst", "developer", "specialist", "consultant"],
}


def _tier_match(title: str, tier: str) -> bool:
    t = title.lower()
    keywords = MANAGEMENT_TIERS.get(tier.lower(), [tier.lower()])
    return any(k in t for k in keywords)


def _apply_linkedin_filters(record: dict, filters: dict, mode: str) -> bool:
    if not filters:
        return True
    checks = []

    if filters.get("industry"):
        val = (
            record.get("industry")
            or record.get("company_industry")
            or record.get("headline")
            or ""
        ).lower()
        checks.append(filters["industry"].lower() in val)

    if filters.get("region"):
        val = (record.get("location") or "").lower()
        checks.append(filters["region"].lower() in val)

    if filters.get("management_tier"):
        val = (
            record.get("current_title")
            or record.get("title")
            or record.get("headline")
            or ""
        ).lower()
        checks.append(_tier_match(val, filters["management_tier"]))

    if filters.get("email"):
        email_val = record.get("email") or ""
        email_filter = filters["email"]
        if isinstance(email_filter, bool):
            checks.append(bool(email_val))
        else:
            domain = str(email_filter).lstrip("@").lower()
            checks.append(
                domain in email_val.lower()
                if "@" in str(email_filter)
                else bool(email_val)
            )

    if filters.get("phone"):
        checks.append(bool(record.get("phone")))

    if filters.get("domain"):
        email_val = (record.get("email") or "").lower()
        url_val = (record.get("url") or record.get("profile_url") or "").lower()
        domain = filters["domain"].lower().lstrip("@")
        checks.append(domain in email_val or domain in url_val)

    if not checks:
        return True
    return any(checks) if mode == "any" else all(checks)


def validate_node(state: AgentState) -> AgentState:
    if not state["raw_records"]:
        print("[validate] No records to validate")
        return state

    campaign_cfg = state.get("campaign_config", {})
    lf = campaign_cfg.get("linkedin_filters") or {}
    match_mode = campaign_cfg.get("filter_match_mode", "all")

    if not lf:
        for src in campaign_cfg.get("source_configs", []):
            if src.get("type") == "linkedin" and src.get("linkedin_filters"):
                lf = src["linkedin_filters"]
                match_mode = src.get("filter_match_mode", match_mode)
                break

    if lf:
        print(f"[validate] LinkedIn filters active (mode={match_mode}): {lf}")

    validated = []
    total = len(state["raw_records"])
    print(f"[validate] Validating {total} records...")

    for i, record in enumerate(state["raw_records"]):
        platform = record.get("platform", "")

        if platform == "upwork":
            title = record.get("title", "").strip()
            if not title:
                print(f"[validate] Upwork job {i+1}/{total} rejected: missing title")
                continue
            print(f"[validate] Upwork job auto-validated: {title[:50]}")
            validated.append(record)
            continue

        try:
            name = (record.get("name") or "").strip()
            title = (
                record.get("current_title")
                or record.get("title")
                or record.get("headline")
                or ""
            ).strip()
            email = (record.get("email") or "").strip()

            print(
                f"[validate] {i+1}/{total} — {record.get('type','?')} | {name[:40]} | {title[:40]}"
            )

            if not title:
                print(f"[validate] Rejected: no title or headline")
                continue

            # Generate email placeholder if missing
            if not email:
                company = record.get("current_company") or record.get("company") or ""
                website = record.get("company_website") or ""
                if website:
                    domain = (
                        website.replace("https://", "")
                        .replace("http://", "")
                        .split("/")[0]
                    )
                    first = name.split()[0].lower() if name else "contact"
                    email = f"linkedin_{first}@{domain}"
                    record["email"] = email
                else:
                    slug = record.get("url", "").split("/in/")[-1].strip(
                        "/"
                    ) or name.lower().replace(" ", "-")
                    email = f"linkedin_{slug}@placeholder.bits"
                    record["email"] = email

            if lf and not _apply_linkedin_filters(record, lf, match_mode):
                print(f"[validate] Rejected: failed LinkedIn filters ({match_mode})")
                continue

            messages = [
                ("system", VALIDATION_PROMPT),
                (
                    "human",
                    json.dumps(
                        {
                            "type": record.get("type"),
                            "name": name,
                            "title": title,
                            "headline": record.get("headline", ""),
                            "company": record.get(
                                "current_company", record.get("company", "")
                            ),
                            "location": record.get("location", ""),
                            "email": email,
                        },
                        default=str,
                    ),
                ),
            ]

            response = llm.invoke(messages)

            # ── FIX: handle None response from Ollama ──────────────────────
            if response is None or response.content is None:
                print(f"[validate] Ollama returned None — keeping record with defaults")
                validated.append({**record, "intent_score": 0.5})
                continue

            text = response.content.strip()

            if not text:
                print(
                    f"[validate] Empty Ollama response — keeping record with defaults"
                )
                validated.append({**record, "intent_score": 0.5})
                continue
            # ──────────────────────────────────────────────────────────────

            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            # Find JSON object boundaries safely
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            result = json.loads(text.strip())

            if result.get("is_valid"):
                validated.append(
                    {
                        **record,
                        **result.get("enriched_fields", {}),
                        "intent_score": result.get("enriched_fields", {}).get(
                            "intent_score", 0.5
                        ),
                    }
                )
                print(f"[validate] ✓ Accepted: {name}")
            else:
                print(f"[validate] Rejected by LLM: {result.get('reason','')}")

        except json.JSONDecodeError as e:
            print(
                f"[validate] JSON parse error on record {i+1}: {e} — keeping with defaults"
            )
            validated.append({**record, "intent_score": 0.5})
        except Exception as e:
            print(f"[validate] Error on record {i+1}: {e} — keeping with defaults")
            validated.append({**record, "intent_score": 0.5})

    print(f"[validate] {len(validated)}/{total} records passed")
    state["validated_records"] = validated
    return state
