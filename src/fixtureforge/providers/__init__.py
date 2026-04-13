"""
AI provider package.
Import the factory or a specific provider class directly.

Examples:
    from fixtureforge.providers import create_provider
    from fixtureforge.providers import GeminiProvider, OpenAIProvider

    provider = create_provider()                           # auto-detect
    provider = create_provider("anthropic", model="claude-sonnet-4-6")
    provider = create_provider("groq", model="llama-3.1-8b-instant")
    provider = create_provider("ollama", model="mistral")
"""
from .base import LLMProvider
from .factory import create_provider

# Lazy re-exports so users get nice error messages if extras not installed
__all__ = [
    "LLMProvider",
    "create_provider",
    "GeminiProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GroqProvider",
    "OllamaProvider",
]


def __getattr__(name: str):
    _map = {
        "GeminiProvider":    (".gemini",    "GeminiProvider"),
        "OpenAIProvider":    (".openai",    "OpenAIProvider"),
        "AnthropicProvider": (".anthropic", "AnthropicProvider"),
        "GroqProvider":      (".groq",      "GroqProvider"),
        "OllamaProvider":    (".ollama",    "OllamaProvider"),
    }
    if name in _map:
        import importlib
        module_suffix, class_name = _map[name]
        module = importlib.import_module(module_suffix, package=__package__)
        return getattr(module, class_name)
    raise AttributeError(f"module 'fixtureforge.providers' has no attribute {name!r}")
