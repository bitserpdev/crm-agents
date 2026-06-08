import os 
from enum import Enum
from functools import lru_cache
from typing import Optional, Type
from langchain_ollama import ChatOllama
from pydantic import BaseModel

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL')
OLLAMA_LLM_MODEL = os.getenv('OLLAMA_LLM_MODEL')
OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL')

class LLMFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
    STRUCTURED = "structured"

class OllamaConfig:
    model: str = "llama3.2"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.4
    timeout: int = 45
    num_predict: int = 800

@lru_cache(maxsize=1)
def _base_llm(
    model: str = OllamaConfig.model,
    temperature: float = OllamaConfig.temperature,
    num_predict: int = OllamaConfig.num_predict,
) -> ChatOllama:
    return ChatOllama(
        model=model,
        base_url=OllamaConfig.base_url,
        temperature=temperature,
        timeout=OllamaConfig.timeout,
        num_predict=num_predict,
    )


def get_llm(
    fmt: LLMFormat = LLMFormat.TEXT,
    schema: Optional[Type[BaseModel]] = None,
    model: str = OllamaConfig.model,
    temperature: float = OllamaConfig.temperature,
    num_predict: int = OllamaConfig.num_predict,
):
    llm = _base_llm(model=model, temperature=temperature, num_predict=num_predict)

    if fmt == LLMFormat.JSON:
        return llm.bind(format="json")

    if fmt == LLMFormat.STRUCTURED:
        if schema is None:
            raise ValueError("A Pydantic schema is required for LLMFormat.STRUCTURED")
        return llm.with_structured_output(schema)

    return llm  # LLMFormat.TEXT — no binding