"""
AIEngine — thin orchestration layer over any LLMProvider.

Responsibilities:
  - Route generate() / generate_batch_semantic() calls to the active provider
  - Transparently check/populate ResponseCache before hitting the API
  - Provide a consistent interface so the rest of the codebase never imports
    provider-specific classes directly
"""
from typing import TYPE_CHECKING, Optional

from .cache import ResponseCache

if TYPE_CHECKING:
    from ..providers.base import LLMProvider


class AIEngine:
    """
    Wraps an LLMProvider with optional response caching.
    Pass provider=None for deterministic-only mode.
    """

    def __init__(
        self,
        provider: Optional["LLMProvider"] = None,
        use_cache: bool = True,
    ):
        self.provider = provider
        self.cache: Optional[ResponseCache] = ResponseCache() if use_cache else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self.provider is not None

    def generate_text(self, prompt: str, cache_key: Optional[str] = None) -> str:
        """
        Generate a single text value.
        Uses cache when cache_key is provided and cache is enabled.
        """
        if not self.provider:
            return "[AI Error: No provider configured]"

        # Cache lookup
        if self.cache and cache_key:
            hit = self.cache.get(cache_key, None, {})
            if hit and isinstance(hit, str):
                return hit

        result = self.provider.generate(prompt)

        # Cache store (only on success)
        if self.cache and cache_key and not result.startswith("[AI Error"):
            self.cache.set(cache_key, None, {}, result)

        return result

    def generate_semantic_batch(
        self, field_name: str, context: str, count: int
    ) -> list[str]:
        """
        Generate `count` values for one semantic field in a single API call.
        Falls back to repeated placeholders when no provider is configured.
        """
        if not self.provider:
            return [f"[AI Placeholder for {field_name}]"] * count

        cache_key = f"batch|{field_name}|{context or ''}|{count}"

        # Cache lookup
        if self.cache:
            hit = self.cache.get(cache_key, None, {})
            if hit and isinstance(hit, list) and len(hit) == count:
                return hit

        values = self.provider.generate_batch_semantic(field_name, context, count)

        # Cache store
        if self.cache and values:
            self.cache.set(cache_key, None, {}, values)

        return values
