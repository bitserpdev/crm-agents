import os 
import json
from agents.agent5.state import Agent5State
from langchain_ollama import ChatOllama
from agents.agent5.prompts import ANALYZE_PROMPT
from config.logger import get_logger

logger = get_logger("analyze_job")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")

llm = ChatOllama(
    model=OLLAMA_LLM_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.2,
    timeout=45,
    format="json",
)

def analyze_job_node(state: Agent5State) -> Agent5State:

    logger.info("Starting analyze_job_node...")
    logger.debug(f"State keys: {list(state.keys())}")

    payload = state["raw_payload"]["raw"]
    title = payload.get("title", "")
    description = payload.get("description", "")

    logger.info("[Agent5/analyze] Analyzing job posting.. ")

    prompt = ANALYZE_PROMPT.format(
        title=title,
        description=description,
        skills=payload.get("skills", []),
        budget=payload.get("budget", {})
    )

    logger.info("[Agent5/analyze] Calling LLM...")
    response = llm.invoke(prompt)

    try:
        logger.info("[Agent5/analyze] Parsing analysis response...")
        analysis = json.loads(response.content)

        state["job_analysis"] = analysis
    except:
        state["job_analysis"] = {"requirements": [], "pain_points": [], "goals": []}
    return state
