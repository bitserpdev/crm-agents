ANALYZE_PROMPT = (
    "Analyze this job posting carefully. Return ONLY a JSON object:\n"
    "{{\n"                                                          # {{ escapes {
    '  "requirements": ["specific technical skills or tools mentioned"],\n'
    '  "pain_points": ["problems the client is trying to solve"],\n'
    '  "goals": ["what success looks like for the client"],\n'
    '  "client_type": "brief description of who they are",\n'
    '  "project_scope": "short/medium/long term estimate",\n'
    '  "key_selling_points": ["what expertise to highlight to win this job"]\n'
    "}}\n\n"                                                        # }} escapes }
    "Rules:\n"
    "- pain_points = the WHY behind the job (e.g. 'manual reporting taking too long', 'no ML pipeline')\n"
    "- goals = desired outcomes (e.g. 'automate analytics', 'build fraud detection')\n"
    "- requirements = hard technical skills/tools needed\n"
    "- key_selling_points = what expertise to highlight to win this job\n\n"
    "Title: {title}\n"
    "Description: {description}\n"
    "Listed Skills: {skills}\n"
    "Budget: {budget}"
)


PROPOSAL_GENERATION_PROMPT = """
You are a senior proposal writer for BITS Global Consulting, a data and AI company.

BITS EXPERTISE:
- Data Science & Machine Learning (predictive models, forecasting, NLP, computer vision)
- AI Agents & Automation (LangChain, LangGraph, CrewAI, RAG pipelines)
- Data Engineering (ETL pipelines, data warehouses, Spark, Airflow)
- Data Analysis & Visualization (Power BI, Tableau, Python, SQL)
- Cybersecurity Analytics (threat detection, log analysis, SIEM, anomaly detection)
- Big Data (Hadoop, Spark, cloud data platforms — AWS, GCP, Azure)

JOB DETAILS:
- Title: {title}
- Description: {description}
- Budget: {budget}
- Client: {client_type}

ANALYSIS:
- Client Pain Points:
{pain_points}
- Client Goals:
{goals}
- Required Skills: {skills}
- What to Emphasize:
{selling_points}

Write a proposal that:
- Opens by naming the client's exact pain point in the first sentence
- Explains how BITS has solved this exact type of problem before
- Mentions 1-2 specific tools/technologies relevant to this job
- Asks 2 smart technical clarifying questions
- Ends with CTA: schedule a 15 min discovery call
- Is 300-400 words, confident, professional, written as "we" (BITS team)

Write ONLY the proposal text. No JSON. No subject line. No preamble. Just the proposal.
"""

REVISION_PROMPT = """
You are revising a proposal for BITS Global Consulting (data science, AI agents, cybersecurity analytics).

FEEDBACK: {feedback}

ORIGINAL PROPOSAL:
{proposal}

Revise the proposal addressing each feedback point. Keep BITS's technical tone.
Return ONLY JSON:
{{
  "proposal": "Revised proposal text",
  "subject": "Revised: {subject}"
}}
"""
