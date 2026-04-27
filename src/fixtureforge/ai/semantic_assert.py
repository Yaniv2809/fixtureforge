"""
assert_semantic_match — semantic validation for AI-generated or natural-language outputs.

Two modes:
  Local (default, use_llm=False):
      Cosine similarity on TF-IDF vectors built from stdlib only.
      Zero API calls. Zero cost. Always available offline.

  LLM (use_llm=True):
      Sends actual + expected_intent to Groq for a structured judgment.
      Requires GROQ_API_KEY. Every call is logged to .fixtureforge_ai_log.jsonl.

Usage:
    from fixtureforge.ai import assert_semantic_match

    # Local (no API key needed)
    result = assert_semantic_match(
        actual="The product was delivered on time and in perfect condition.",
        expected_intent="positive delivery experience",
    )

    # LLM-powered (explicit opt-in)
    result = assert_semantic_match(
        actual=chatbot_response,
        expected_intent="politely decline the refund request",
        use_llm=True,
        threshold=0.8,
    )
    # Raises SemanticAssertionError if result.passed is False
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from ._audit_log import log_event
from ._groq_client import LLMClientError, groq_complete

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass
class SemanticResult:
    """Return value of assert_semantic_match."""
    passed: bool
    score: float        # 0.0 – 1.0
    reason: str         # human-readable explanation
    method: str         # "local" or "llm"

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"SemanticResult({status} | score={self.score:.2f} "
            f"| method={self.method} | reason={self.reason!r})"
        )


class SemanticAssertionError(AssertionError):
    """Raised when assert_semantic_match fails."""

    def __init__(self, result: SemanticResult, actual: str, expected_intent: str) -> None:
        self.result = result
        self.actual = actual
        self.expected_intent = expected_intent
        super().__init__(
            f"\n\nSemantic assertion failed.\n"
            f"  Expected intent : {expected_intent!r}\n"
            f"  Actual output   : {actual!r}\n"
            f"  Score           : {result.score:.2f} (threshold not met)\n"
            f"  Method          : {result.method}\n"
            f"  Reason          : {result.reason}\n"
        )


# ---------------------------------------------------------------------------
# Local cosine similarity (stdlib only — no external dependencies)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> Counter:
    """Lowercase, split on whitespace, return token frequency counter."""
    tokens = text.lower().split()
    # strip punctuation from token edges
    cleaned = [t.strip(".,!?;:\"'()-[]{}") for t in tokens]
    return Counter(t for t in cleaned if t)


def _cosine_similarity(text_a: str, text_b: str) -> float:
    """
    TF-IDF cosine similarity between two strings using stdlib only.
    Returns a value in [0.0, 1.0].
    """
    vec_a = _tokenize(text_a)
    vec_b = _tokenize(text_b)

    if not vec_a or not vec_b:
        return 0.0

    # dot product over shared tokens
    shared = set(vec_a) & set(vec_b)
    dot = sum(vec_a[w] * vec_b[w] for w in shared)

    # magnitudes
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot / (mag_a * mag_b)


def _local_assert(actual: str, expected_intent: str, threshold: float) -> SemanticResult:
    score = _cosine_similarity(actual, expected_intent)
    passed = score >= threshold
    reason = (
        f"Cosine similarity {score:.2f} >= threshold {threshold:.2f}"
        if passed
        else f"Cosine similarity {score:.2f} < threshold {threshold:.2f}"
    )
    return SemanticResult(passed=passed, score=score, reason=reason, method="local")


# ---------------------------------------------------------------------------
# LLM-powered assertion via Groq
# ---------------------------------------------------------------------------

_LLM_SYSTEM = (
    "You are a test validation judge. "
    "Given an actual output and an expected intent, "
    "return ONLY valid JSON with no markdown, no explanation. "
    'Format: {"passed": bool, "score": float, "reason": str}'
)


def _llm_assert(
    actual: str,
    expected_intent: str,
    threshold: float,
    api_key: Optional[str],
) -> SemanticResult:
    user_msg = (
        f"Expected intent: {expected_intent}\n"
        f"Actual output: {actual}\n"
        f"Score threshold: {threshold}\n"
        "Does the actual output satisfy the expected intent? "
        "Return JSON only."
    )

    try:
        raw = groq_complete(system=_LLM_SYSTEM, user=user_msg, api_key=api_key)
        # strip markdown fences if model ignored instructions
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(raw)

        score = float(parsed.get("score", 0.0))
        passed = bool(parsed.get("passed", score >= threshold))
        reason = str(parsed.get("reason", ""))

        log_event("semantic_assert_llm", {
            "actual": actual[:200],
            "expected_intent": expected_intent[:200],
            "threshold": threshold,
            "score": score,
            "passed": passed,
            "reason": reason,
        })

        return SemanticResult(passed=passed, score=score, reason=reason, method="llm")

    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        # Graceful degradation: fall back to local on parse error
        log_event("semantic_assert_llm_parse_error", {"error": str(exc), "raw": raw[:300]})
        result = _local_assert(actual, expected_intent, threshold)
        result.reason = f"[LLM response unparseable, fell back to local] {result.reason}"
        result.method = "local_fallback"
        return result

    except LLMClientError as exc:
        # No API key or network error — fall back to local silently
        log_event("semantic_assert_llm_error", {"error": str(exc)})
        result = _local_assert(actual, expected_intent, threshold)
        result.reason = f"[LLM unavailable, fell back to local] {result.reason}"
        result.method = "local_fallback"
        return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assert_semantic_match(
    actual: str,
    expected_intent: str,
    use_llm: bool = False,
    threshold: float = 0.75,
    api_key: Optional[str] = None,
    raise_on_failure: bool = True,
) -> SemanticResult:
    """
    Assert that `actual` semantically matches `expected_intent`.

    Args:
        actual:           The string to validate (e.g. chatbot response, generated text).
        expected_intent:  Natural language description of what the output should convey.
        use_llm:          If True, use Groq for a more nuanced judgment.
                          Requires GROQ_API_KEY. Default: False (local cosine similarity).
        threshold:        Minimum score to pass. Range: [0.0, 1.0]. Default: 0.75.
        api_key:          Override GROQ_API_KEY env var (optional).
        raise_on_failure: If True (default), raise SemanticAssertionError on failure.

    Returns:
        SemanticResult(passed, score, reason, method)

    Raises:
        SemanticAssertionError: If the assertion fails and raise_on_failure=True.

    Examples:
        # Local — zero cost, always available
        assert_semantic_match(
            actual="Great experience, delivered next day!",
            expected_intent="positive customer review",
        )

        # LLM — richer judgment, requires API key
        result = assert_semantic_match(
            actual=model_output,
            expected_intent="professional refusal of the request",
            use_llm=True,
            threshold=0.8,
        )
        print(result.score, result.reason)
    """
    if not isinstance(actual, str) or not isinstance(expected_intent, str):
        raise TypeError(
            f"assert_semantic_match expects str arguments, "
            f"got actual={type(actual).__name__}, "
            f"expected_intent={type(expected_intent).__name__}"
        )

    if use_llm:
        result = _llm_assert(actual, expected_intent, threshold, api_key)
    else:
        result = _local_assert(actual, expected_intent, threshold)

    if not result.passed and raise_on_failure:
        raise SemanticAssertionError(result, actual, expected_intent)

    return result
