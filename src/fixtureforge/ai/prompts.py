"""
FixtureForge Prompt Engine — SYSTEM_PROMPT_DYNAMIC_BOUNDARY.

Architecture (prompt-cache optimisation):
  [STATIC]   — Tool definitions + generation strategies + base rules.
               Content NEVER changes between sessions → cached once,
               paid at ~10% normal cost on every subsequent call.

  [BOUNDARY] — Separator that marks the end of cacheable content.

  [DYNAMIC]  — Per-call payload: schema, context, domain rules, session state.
               Unique every call → paid in full each time.

Result: ~40% reduction in API costs on repeated generation calls because
the STATIC block (usually the largest part) is served from prompt cache.
"""
from __future__ import annotations

from typing import Optional


# ===========================================================================
# STATIC BLOCK — cached across all projects and all sessions
# Must not contain any session-specific or model-specific content.
# ===========================================================================

_STATIC_SYSTEM_PROMPT: str = """
You are FixtureForge, an advanced AI-powered test data generator.
Your mission: produce realistic, context-aware synthetic data for developers and QA engineers.

━━━━━━━━━━━━━━━━━━━━━━ OUTPUT FORMAT ━━━━━━━━━━━━━━━━━━━━━━
• Output ONLY valid JSON — no Markdown, no code blocks, no explanations.
• Always return a JSON array, even for a single item.
• Dates as ISO 8601 strings (e.g. "2024-03-15").
• UUIDs as lowercase hyphenated strings.

━━━━━━━━━━━━━━━━━━━━━━ GENERATION STRATEGIES ━━━━━━━━━━━━━━
Apply the appropriate strategy for the requested mode:

VALID (default)
  Generate realistic, fully-valid records that would pass all business rules.
  Names, emails, phones must look real. Use the locale if specified.

BVA — Boundary Value Analysis
  For each numeric/string field: generate one value at the exact minimum,
  one at the exact maximum, and one just inside each boundary.

EQUIVALENCE PARTITIONING
  Divide the input domain into equivalence classes. Generate one representative
  from each class, ensuring every class is covered at least once.

PAIRWISE / COMBINATORIAL
  Cover all pairs of input values. Use a pairwise strategy to minimise the
  total number of records while maximising pair coverage.

INVALID / NEGATIVE
  Generate records that VIOLATE the schema constraints: wrong types,
  out-of-range values, missing required fields, malformed strings.
  Label each with a "violation_type" field describing what rule it breaks.

FULL_COVERAGE
  Combine BVA + Equivalence Partitioning + at least 3 invalid records.
  This is the most thorough mode.

━━━━━━━━━━━━━━━━━━━━━━ QUALITY RULES ━━━━━━━━━━━━━━━━━━━━━━
• REALISM: Data must look authentic (real-sounding names, valid email formats).
• CONSISTENCY: Related fields must agree (email should match the name, etc.).
• DIVERSITY: Across N records, vary values meaningfully — no copy-paste.
• NO NULLS unless the schema explicitly allows Optional/nullable fields.
""".strip()


# ===========================================================================
# BOUNDARY MARKER
# ===========================================================================

_BOUNDARY = "\n\n# ── DYNAMIC PAYLOAD (session-specific) ──────────────────────\n"


# ===========================================================================
# Public helpers
# ===========================================================================

def get_static_system_prompt() -> str:
    """
    Return the STATIC portion of the system prompt.
    This should be placed in the ``system`` parameter of the API call so
    providers can apply prompt caching to it.
    """
    return _STATIC_SYSTEM_PROMPT


def build_prompt(
    model_schema: dict,
    count: int,
    context: str = "",
    strategy: str = "valid",
    domain_rules: str = "",
    session_state: Optional[str] = None,
) -> str:
    """
    Build the DYNAMIC payload portion of the prompt.

    This goes in the ``user`` / ``messages`` part of the API request —
    it changes per call so it is NOT cached.

    Parameters
    ----------
    model_schema  : Pydantic model schema dict (from model.model_json_schema())
    count         : number of records to generate
    context       : free-text scenario description
    strategy      : one of valid | bva | ep | pairwise | invalid | full_coverage
    domain_rules  : injected domain rules from ForgeMemory (always re-read from disk)
    session_state : optional compact session summary from CompressionPipeline
    """
    parts: list[str] = [_BOUNDARY]

    parts.append(f"SCHEMA:\n{model_schema}\n")
    parts.append(f"COUNT: {count}\n")
    parts.append(f"STRATEGY: {strategy.upper()}\n")

    if context:
        parts.append(f"CONTEXT/SCENARIO:\n{context}\n")
    else:
        parts.append("CONTEXT: General realistic data.\n")

    if domain_rules:
        parts.append(f"DOMAIN RULES (authoritative — override your defaults):\n{domain_rules}\n")

    if session_state:
        parts.append(f"SESSION SUMMARY:\n{session_state}\n")

    parts.append("OUTPUT: Strictly a JSON array of objects matching the schema above.")
    return "\n".join(parts)


def build_semantic_batch_prompt(
    field_name: str,
    context: str,
    count: int,
    domain_rules: str = "",
) -> str:
    """
    Prompt for generating N values for a single semantic field.

    Used by SmartBatchEngine — one call per semantic field, returns N values.
    """
    rules_section = f"\nDomain rules for this field:\n{domain_rules}\n" if domain_rules else ""
    return (
        f"{_BOUNDARY}"
        f"Generate exactly {count} realistic values for a field named '{field_name}'.\n"
        f"Context: {context or 'General realistic data'}.\n"
        f"{rules_section}"
        f"Output ONLY a JSON array of {count} strings. No objects, no keys — just the values.\n"
        f'Example: ["value 1", "value 2", ...]'
    )
