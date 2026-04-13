"""
OpenAI provider — supports OpenAI API and Azure OpenAI.
Requires: pip install fixtureforge[openai]  (openai>=1.0)

Azure usage:
    OpenAIProvider(
        api_key="...",
        base_url="https://<resource>.openai.azure.com/",
        model="my-gpt4o-deployment",
        api_version="2024-02-01",   # passed via extra_kwargs
    )
"""
import json
from typing import Optional

from .base import LLMProvider
from .gemini import _parse_batch_response  # reuse helper


class OpenAIProvider(LLMProvider):
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: Optional[str] = None,
        **extra_kwargs,
    ):
        try:
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "OpenAI provider requires the 'openai' package.\n"
                "Install it with: pip install fixtureforge[openai]"
            ) from exc

        self._model = model
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client_kwargs.update(extra_kwargs)
        self._client = OpenAI(**client_kwargs)

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        return response.choices[0].message.content.strip()

    def generate_batch_semantic(self, field_name: str, context: str, count: int) -> list[str]:
        prompt = (
            f"Generate exactly {count} realistic, varied values for a database field named '{field_name}'.\n"
            f"Context/Scenario: {context or 'General realistic data'}\n\n"
            f"Return ONLY a valid JSON array of exactly {count} strings. "
            f"No markdown, no explanations."
        )
        system = "You are a test data generator. Output only raw valid JSON."
        raw = self.generate(prompt, system_prompt=system)
        return _parse_batch_response(raw, field_name, count)
