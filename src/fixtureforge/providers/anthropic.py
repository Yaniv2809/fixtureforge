"""
Anthropic Claude provider.
Requires: pip install fixtureforge[anthropic]  (anthropic)

Model tiers (as of 2026):
  - claude-haiku-4-5-20251001   → fast, cheap  (Tier 3 tasks)
  - claude-sonnet-4-6           → balanced      (Tier 4 tasks)
  - claude-opus-4-6             → most capable  (complex reasoning)
"""
from typing import Optional

from .base import LLMProvider
from .gemini import _parse_batch_response


class AnthropicProvider(LLMProvider):
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        try:
            import anthropic  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "Anthropic provider requires the 'anthropic' package.\n"
                "Install it with: pip install fixtureforge[anthropic]"
            ) from exc

        self._model = model
        self._client = anthropic.Anthropic(api_key=api_key)

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        kwargs = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        return response.content[0].text.strip()

    def generate_batch_semantic(self, field_name: str, context: str, count: int) -> list[str]:
        prompt = (
            f"Generate exactly {count} realistic, varied values for a database field named '{field_name}'.\n"
            f"Context/Scenario: {context or 'General realistic data'}\n\n"
            f"Return ONLY a valid JSON array of exactly {count} strings. "
            f"No markdown, no explanations."
        )
        system = "You are a test data generator. Output only raw valid JSON arrays."
        raw = self.generate(prompt, system_prompt=system)
        return _parse_batch_response(raw, field_name, count)
