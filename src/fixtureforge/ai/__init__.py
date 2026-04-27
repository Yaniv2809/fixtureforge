"""
AI-powered generation and validation for FixtureForge.

Core (always available):
    from fixtureforge.ai import AIEngine, ResponseCache

v2.2.0 — Opt-in AI features (require GROQ_API_KEY for LLM mode):
    from fixtureforge.ai import assert_semantic_match, SemanticResult
    from fixtureforge.ai import SmartFailureAnalyzer
"""
from .engine import AIEngine
from .cache import ResponseCache
from .semantic_assert import assert_semantic_match, SemanticResult, SemanticAssertionError
from .failure_analyzer import SmartFailureAnalyzer

__all__ = [
    # Core
    "AIEngine",
    "ResponseCache",
    # v2.2.0 features
    "assert_semantic_match",
    "SemanticResult",
    "SemanticAssertionError",
    "SmartFailureAnalyzer",
]
