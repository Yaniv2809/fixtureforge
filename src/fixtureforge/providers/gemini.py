"""
Google Gemini provider.
Requires: pip install fixtureforge[gemini]  (google-genai)
"""
import json
import time
from typing import Optional

from .base import LLMProvider

_SYSTEM_SEPARATOR = "\n\n---\n\n"


class GeminiProvider(LLMProvider):
    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        try:
            from google import genai  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "Google Gemini provider requires the 'google-genai' package.\n"
                "Install it with: pip install fixtureforge[gemini]"
            ) from exc

        self._model = model
        self._client = genai.Client(api_key=api_key)

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str, system_prompt: Optional[str] = None, retries: int = 5) -> str:
        full_prompt = f"{system_prompt}{_SYSTEM_SEPARATOR}{prompt}" if system_prompt else prompt

        for attempt in range(retries):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=full_prompt,
                )
                return response.text.strip()

            except Exception as exc:
                msg = str(exc)
                is_transient = any(code in msg for code in ["429", "503", "quota", "RESOURCE_EXHAUSTED"])
                if is_transient and attempt < retries - 1:
                    wait = 10 * (attempt + 1)
                    print(f"⏳ Gemini rate-limited. Waiting {wait}s... ({attempt + 1}/{retries})")
                    time.sleep(wait)
                else:
                    raise

        return "[AI Error: Max retries exceeded]"

    def generate_batch_semantic(self, field_name: str, context: str, count: int) -> list[str]:
        prompt = (
            f"Generate exactly {count} realistic, varied values for a database field named '{field_name}'.\n"
            f"Context/Scenario: {context or 'General realistic data'}\n\n"
            f"RULES:\n"
            f"- Return ONLY a valid JSON array of exactly {count} strings.\n"
            f"- No markdown, no explanations, no code blocks.\n"
            f"- Each value must be unique and realistic."
        )
        raw = self.generate(prompt)
        return _parse_batch_response(raw, field_name, count)


def _parse_batch_response(raw: str, field_name: str, count: int) -> list[str]:
    """Clean and parse a JSON array from an AI response."""
    cleaned = raw.strip()
    if "```" in cleaned:
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            values = [str(v) for v in result]
            # Pad or trim to exact count
            if len(values) < count:
                values += values * (count // len(values) + 1)
            return values[:count]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: repeat the raw value
    return [cleaned] * count
