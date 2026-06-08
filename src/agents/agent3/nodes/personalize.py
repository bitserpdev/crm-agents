import os
from psycopg2.extras import Json
from core.llm import get_llm, LLMFormat
from agent3.state import Agent3State
from agent3.prompts import PERSONALIZE_PROMPT

llm = get_llm(fmt=LLMFormat.TEXT)

def personalize_node(state: Agent3State) -> Agent3State:
    if not state["contacts"]:
        state["run_status"] = "done"
        return state

    personalized = []
    total = len(state["contacts"])

    print(f"[agent3/personalize] Personalizing {total} emails with llama3.2...")

    for i, contact in enumerate(state["contacts"]):
        try:
            company_name = contact.get("company_name", "your company")
            print(
                f"[agent3/personalize] {i+1}/{total} — {contact.get('first_name','')} {contact.get('last_name','')} @ {company_name}"
            )

            # inject company name into prompt so LLM can't miss it
            prompt = PERSONALIZE_PROMPT.replace("{company_name}", company_name)

            sender_name = state["campaign"].get("sender_name") or os.getenv(
                "SENDER_NAME", "Zaid Ghauri"
            )
            sender_title = state["campaign"].get("sender_title") or os.getenv(
                "SENDER_TITLE", "Head of Data Solutions"
            )
            sender_email = state["campaign"].get("from_address", "")

            messages = [
                ("system", prompt),
                (
                    "human",
                    json.dumps(
                        {
                            "contact": {
                                "name": f"{contact.get('first_name','')} {contact.get('last_name','')}",
                                "job_title": contact.get("job_title", ""),
                                "company": company_name,
                                "industry": contact.get("industry", ""),
                                "city": contact.get("city", ""),
                                "country": contact.get("country", ""),
                                "tags": contact.get("tags", []),
                            },
                            "campaign_service": state["campaign"].get(
                                "service_description", ""
                            ),
                            "from_email": state["campaign"].get("from_address", ""),
                            "sender": {
                                "name": sender_name,
                                "title": sender_title,
                                "company": "BITS Global Consulting",
                                "email": sender_email,
                            },
                        },
                        default=str,
                    ),
                ),
            ]

            response = llm.invoke(messages)
            text = response.content.strip()

            # Strip markdown fences
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            result = json.loads(text.strip())

            personalized.append(
                {
                    "contact": contact,
                    "subject": result.get(
                        "subject",
                        f"Big Data Solutions for {contact.get('company_name','')}",
                    ),
                    "html": result.get("html", ""),
                    "text": result.get("text", ""),
                }
            )

        except Exception as e:
            print(f"[agent3/personalize] Error: {e}")
            # Fallback email
            name = (
                f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
            )
            company = contact.get("company_name", "your company")
            personalized.append(
                {
                    "contact": contact,
                    "subject": f"Big Data & Analytics Solutions for {company}",
                    "html": f"<p>Hi {name},</p><p>I wanted to reach out about how BITS Analytics can help {company} leverage big data to drive better decisions. Would you be open to a quick 15-minute call?</p><p>Best,<br>BITS Analytics Team</p>",
                    "text": f"Hi {name},\n\nI wanted to reach out about how BITS Analytics can help {company} leverage big data to drive better decisions.\n\nWould you be open to a quick 15-minute call?\n\nBest,\nBITS Analytics Team",
                }
            )

    print(f"[agent3/personalize] Personalized {len(personalized)}/{total} emails")
    state["personalized"] = personalized
    return state
