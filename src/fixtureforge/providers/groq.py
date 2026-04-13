"""
Groq provider — ultra-fast inference via Groq's OpenAI-compatible API.
Requires: pip install fixtureforge[openai]  (same openai package)

Set env var:  GROQ_API_KEY=gsk_...
Or pass:      Forge(provider_name="groq", api_key="gsk_...")

Popular models (free tier available):
  llama-3.3-70b-versatile   ← default (smart, fast)
  llama-3.1-8b-instant      ← cheapest / fastest
  mixtral-8x7b-32768        ← large context window
  gemma2-9b-it              ← Google Gemma via Groq
"""
from typing import Optional

from .openai import OpenAIProvider

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(OpenAIProvider):
    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        super().__init__(api_key=api_key, model=model, base_url=GROQ_BASE_URL)
