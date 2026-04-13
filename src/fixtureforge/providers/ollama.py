"""
Ollama provider — local models (Llama 3.2, Mistral, Phi, Gemma, …).
Requires: Ollama running locally  (https://ollama.com)
No extra pip package needed — uses the standard 'requests' library.

Usage:
    forge = Forge(provider_name="ollama", model="llama3.2")
    # Or use the default auto-detection when no cloud keys are present.
"""
import json
from typing import Optional

from .base import LLMProvider
from .gemini import _parse_batch_response

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


class OllamaProvider(LLMProvider):
    DEFAULT_MODEL = "llama3.2"
    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL):
        if not _HAS_REQUESTS:
            raise ImportError(
                "Ollama provider requires the 'requests' package.\n"
                "Install it with: pip install requests"
            )
        self._model = model
        self._base_url = base_url.rstrip("/")

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = _requests.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

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

    @classmethod
    def is_available(cls, base_url: str = DEFAULT_BASE_URL) -> bool:
        """Check if an Ollama server is reachable."""
        if not _HAS_REQUESTS:
            return False
        try:
            _requests.get(base_url, timeout=1)
            return True
        except Exception:
            return False
