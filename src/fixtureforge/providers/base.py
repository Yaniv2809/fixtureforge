"""
Abstract base for all AI providers.
Any provider must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """
    Protocol for interchangeable AI backends.
    Implementations: GeminiProvider, OpenAIProvider, AnthropicProvider, OllamaProvider.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier (e.g. 'gemini-2.0-flash', 'gpt-4o-mini')."""
        ...

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate a single text response.
        Raise on hard errors; return error string on recoverable ones.
        """
        ...

    @abstractmethod
    def generate_batch_semantic(
        self, field_name: str, context: str, count: int
    ) -> list[str]:
        """
        Generate `count` realistic values for a semantic field in ONE API call.
        Returns a list of exactly `count` strings.
        """
        ...
