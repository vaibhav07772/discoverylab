"""LLM Client for DiscoveryLab"""
import os
import json
import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)

load_dotenv()
logger = logging.getLogger(__name__)


def get_llm(model: str = None, temperature: float = 0.3,
            json_mode: bool = False, max_tokens: int = 4000):
    """Get Groq LLM instance"""
    model = model or os.getenv("DEFAULT_MODEL", "openai/gpt-oss-20b")
    
    kwargs = {
        "model": model,
        "api_key": os.getenv("GROQ_API_KEY"),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    
    return ChatGroq(**kwargs)


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def safe_invoke(llm, prompt):
    """Invoke with auto-retry"""
    return llm.invoke(prompt)


def safe_json_invoke(llm, prompt) -> dict:
    """Invoke and parse JSON"""
    response = safe_invoke(llm, prompt)
    raw = response.content.strip()
    
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise