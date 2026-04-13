"""
Provider factory — auto-detect or explicitly create an LLM provider.

Priority when no provider_name is given:
  1. FIXTUREFORGE_PROVIDER env var
  2. GOOGLE_API_KEY   → Gemini
  3. OPENAI_API_KEY   → OpenAI
  4. ANTHROPIC_API_KEY → Anthropic (Claude Haiku)
  5. GROQ_API_KEY     → Groq (llama-3.3-70b-versatile)
  6. Ollama reachable locally → Ollama (llama3.2)
  7. None  → deterministic-only mode

Explicit usage:
    provider = create_provider("openai", model="gpt-4o")
    provider = create_provider("anthropic", model="claude-sonnet-4-6")
    provider = create_provider("groq", model="llama-3.1-8b-instant")
    provider = create_provider("ollama", model="mistral")
    provider = create_provider("gemini")   # uses GOOGLE_API_KEY
"""
import importlib
import os
from typing import Optional

from .base import LLMProvider

# Maps provider name → (env var for key, relative module, class name, default model)
# Relative module paths work regardless of how the package is installed.
_REGISTRY = {
    "gemini":    ("GOOGLE_API_KEY",    ".gemini",    "GeminiProvider",    "gemini-2.0-flash"),
    "openai":    ("OPENAI_API_KEY",    ".openai",    "OpenAIProvider",    "gpt-4o-mini"),
    "anthropic": ("ANTHROPIC_API_KEY", ".anthropic", "AnthropicProvider", "claude-haiku-4-5-20251001"),
    "groq":      ("GROQ_API_KEY",      ".groq",      "GroqProvider",      "llama-3.3-70b-versatile"),
}


def create_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> Optional[LLMProvider]:
    """
    Resolve and instantiate an LLM provider.
    Returns None when no provider is available (deterministic-only mode).
    """
    name = (provider_name or os.getenv("FIXTUREFORGE_PROVIDER", "")).lower().strip()

    if not name:
        name = _auto_detect()

    if not name:
        return None

    # --- Ollama (no API key needed) ---
    if name == "ollama":
        from .ollama import OllamaProvider  # noqa: PLC0415
        return OllamaProvider(
            model=model or OllamaProvider.DEFAULT_MODEL,
            base_url=kwargs.get("base_url", OllamaProvider.DEFAULT_BASE_URL),
        )

    # --- Cloud providers ---
    if name not in _REGISTRY:
        known = ", ".join(["gemini", "openai", "anthropic", "groq", "ollama"])
        raise ValueError(f"Unknown provider '{name}'. Choose one of: {known}")

    env_var, module_suffix, class_name, default_model = _REGISTRY[name]
    resolved_key = api_key or os.getenv(env_var)

    if not resolved_key:
        raise ValueError(
            f"Provider '{name}' requires an API key.\n"
            f"Pass api_key= or set the {env_var} environment variable."
        )

    module = importlib.import_module(module_suffix, package=__package__)
    cls = getattr(module, class_name)

    init_kwargs = {"api_key": resolved_key, "model": model or default_model}
    init_kwargs.update(kwargs)
    return cls(**init_kwargs)


def _auto_detect() -> Optional[str]:
    """Detect which provider is available from environment."""
    if os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GROQ_API_KEY"):
        return "groq"

    # Try Ollama last (local)
    from .ollama import OllamaProvider  # noqa: PLC0415
    if OllamaProvider.is_available():
        return "ollama"

    return None
