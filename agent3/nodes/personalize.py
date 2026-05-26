import json
from langchain_ollama import ChatOllama
from agent3.state import Agent3State

llm = ChatOllama(
    model="llama3.2",
    base_url="http://localhost:11434",
    temperature=0.4,
    timeout=45,
    num_predict=800,
)

PERSONALIZE_PROMPT = """
You are an expert B2B sales email writer for BITS — a Big Data & Analytics company.

Write a personalized, professional cold outreach email to the contact below.
The email should:
- Be warm but professional
- Reference their specific role, company, and industry
- Explain how BITS Big Data & Analytics services can help THEIR business specifically
- Include 2-3 specific benefits relevant to their industry
- Have a clear call to action (schedule a 15-min call)
- Be concise — max 180 words body
- NOT sound like a template or mass email

Return ONLY valid JSON, no markdown:
{
  "subject": "email subject line",
  "html": "full HTML email body with <p> tags",
  "text": "plain text version"
}
"""

def personalize_node(state: Agent3State) -> Agent3State:
    if not state["contacts"]:
        state["run_status"] = "done"
        return state

    personalized = []
    total = len(state["contacts"])
    service_desc = state["campaign"].get("service_description",
                   "Big Data & Analytics solutions")

    print(f"[agent3/personalize] Personalizing {total} emails with llama3.2...")

    for i, contact in enumerate(state["contacts"]):
        try:
            print(f"[agent3/personalize] {i+1}/{total} — {contact.get('first_name','')} {contact.get('last_name','')} @ {contact.get('company_name','')}")

            messages = [
                ("system", PERSONALIZE_PROMPT),
                ("human", json.dumps({
                    "contact": {
                        "name":       f"{contact.get('first_name','')} {contact.get('last_name','')}",
                        "job_title":  contact.get("job_title", ""),
                        "company":    contact.get("company_name", ""),
                        "industry":   contact.get("industry", ""),
                        "city":       contact.get("city", ""),
                        "country":    contact.get("country", ""),
                        "tags":       contact.get("tags", []),
                    },
                    "service_description": service_desc,
                    "sender_name": "BITS Analytics Team",
                    "from_email":  state["campaign"].get("from_address", ""),
                }, default=str))
            ]

            response = llm.invoke(messages)
            text = response.content.strip()

            # Strip markdown fences
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            start = text.find("{")
            end   = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            result = json.loads(text.strip())

            personalized.append({
                "contact":  contact,
                "subject":  result.get("subject", f"Big Data Solutions for {contact.get('company_name','')}"),
                "html":     result.get("html", ""),
                "text":     result.get("text", ""),
            })

        except Exception as e:
            print(f"[agent3/personalize] Error: {e}")
            # Fallback email
            name = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
            company = contact.get("company_name", "your company")
            personalized.append({
                "contact": contact,
                "subject": f"Big Data & Analytics Solutions for {company}",
                "html": f"<p>Hi {name},</p><p>I wanted to reach out about how BITS Analytics can help {company} leverage big data to drive better decisions. Would you be open to a quick 15-minute call?</p><p>Best,<br>BITS Analytics Team</p>",
                "text": f"Hi {name},\n\nI wanted to reach out about how BITS Analytics can help {company} leverage big data to drive better decisions.\n\nWould you be open to a quick 15-minute call?\n\nBest,\nBITS Analytics Team",
            })

    print(f"[agent3/personalize] Personalized {len(personalized)}/{total} emails")
    state["personalized"] = personalized
    return state
