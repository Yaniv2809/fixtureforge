"""
Three-Layer Compression Pipeline for FixtureForge sessions.

Mirrors the MicroCompact → AutoCompact → FullCompact pattern:

  MicroForgeCompact  — drop stale field-analysis blobs; zero API calls
  AutoForgeCompact   — near session budget: emit structured summary + circuit-breaker
  FullForgeCompact   — compress everything; re-inject only the critical schemas

Used internally by ForgeSession to keep the working context lean.

    POST_COMPRESSION_BUDGET  = 50_000  tokens  (equivalent)
    AUTO_COMPACT_BUFFER      = 13_000  tokens  (trigger threshold)
    CIRCUIT_BREAKER_MAX      = 3       failures before abort
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


POST_COMPRESSION_BUDGET: int = 50_000
AUTO_COMPACT_BUFFER:      int = 13_000
CIRCUIT_BREAKER_MAX:      int = 3


# ---------------------------------------------------------------------------
# Session state that gets compressed
# ---------------------------------------------------------------------------

@dataclass
class ForgeSessionState:
    """
    Mutable snapshot of an active generation session.

    field_analyses   — per-field AI results that accumulate and can grow stale
    schema_snapshots — the schemas that were active when each batch ran
    generation_log   — high-level log entries (model, count, timestamp)
    token_estimate   — rough token estimate for the full state
    """
    field_analyses:   Dict[str, Any]        = field(default_factory=dict)
    schema_snapshots: List[Dict[str, Any]]  = field(default_factory=list)
    generation_log:   List[Dict[str, Any]]  = field(default_factory=list)
    token_estimate:   int                   = 0

    def add_generation(self, model_name: str, count: int, fields: List[str]) -> None:
        entry = {
            "model": model_name,
            "count": count,
            "fields": fields,
            "ts": time.time(),
        }
        self.generation_log.append(entry)
        # Rough token estimate: ~4 chars per token
        self.token_estimate += len(json.dumps(entry)) // 4

    def add_field_analysis(self, field_key: str, analysis: Any) -> None:
        self.field_analyses[field_key] = analysis
        self.token_estimate += len(json.dumps({field_key: analysis})) // 4

    def is_near_budget(self) -> bool:
        return self.token_estimate >= (POST_COMPRESSION_BUDGET - AUTO_COMPACT_BUFFER)

    def is_over_budget(self) -> bool:
        return self.token_estimate >= POST_COMPRESSION_BUDGET


# ---------------------------------------------------------------------------
# Layer 1 — MicroForgeCompact
# ---------------------------------------------------------------------------

class MicroForgeCompact:
    """
    Lightweight, zero-API-call compaction.
    Drops field_analyses older than a recency threshold, keeping only
    the N most recently used ones.
    """

    KEEP_RECENT: int = 20

    def compact(self, state: ForgeSessionState) -> int:
        """
        Remove stale field analyses in-place.
        Returns number of entries removed.
        """
        if len(state.field_analyses) <= self.KEEP_RECENT:
            return 0

        keys = list(state.field_analyses.keys())
        to_remove = keys[: len(keys) - self.KEEP_RECENT]
        for k in to_remove:
            del state.field_analyses[k]

        removed_tokens = sum(
            len(json.dumps({k: state.field_analyses.get(k, "")}) ) // 4
            for k in to_remove
        )
        state.token_estimate = max(0, state.token_estimate - removed_tokens)
        return len(to_remove)


# ---------------------------------------------------------------------------
# Layer 2 — AutoForgeCompact
# ---------------------------------------------------------------------------

class AutoForgeCompact:
    """
    Triggered near the session token budget.
    Emits a structured summary replacing verbose logs.
    Includes a circuit-breaker that stops retrying after MAX_FAILURES.
    """

    def __init__(self) -> None:
        self._failure_count: int = 0

    @property
    def is_broken(self) -> bool:
        """True when the circuit-breaker has tripped."""
        return self._failure_count >= CIRCUIT_BREAKER_MAX

    def compact(self, state: ForgeSessionState) -> Optional[Dict[str, Any]]:
        """
        Compress the generation log into a structured summary.
        Returns the summary dict, or None if the circuit-breaker is tripped.
        """
        if self.is_broken:
            return None

        try:
            summary = self._build_summary(state)
            # Replace verbose log with summary
            state.generation_log.clear()
            state.generation_log.append({"__summary__": summary})
            # Recalculate token estimate
            state.token_estimate = len(json.dumps(summary)) // 4 + len(
                json.dumps(state.field_analyses)
            ) // 4
            self._failure_count = 0   # reset on success
            return summary

        except Exception as exc:
            self._failure_count += 1
            remaining = CIRCUIT_BREAKER_MAX - self._failure_count
            print(
                f"⚠️  AutoForgeCompact failed ({self._failure_count}/{CIRCUIT_BREAKER_MAX}): {exc}"
                + (f" — {remaining} retries left." if remaining > 0 else " — circuit breaker OPEN.")
            )
            return None

    def _build_summary(self, state: ForgeSessionState) -> Dict[str, Any]:
        log = [e for e in state.generation_log if "__summary__" not in e]
        model_counts: Dict[str, int] = {}
        for entry in log:
            model_counts[entry["model"]] = model_counts.get(entry["model"], 0) + entry.get("count", 0)

        return {
            "type": "auto_compact_summary",
            "models_generated": model_counts,
            "total_records": sum(model_counts.values()),
            "unique_models": len(model_counts),
            "field_analyses_cached": len(state.field_analyses),
            "compressed_at": time.time(),
        }


# ---------------------------------------------------------------------------
# Layer 3 — FullForgeCompact
# ---------------------------------------------------------------------------

class FullForgeCompact:
    """
    Full compression: discard everything except critical schemas.
    Leaves the session with a clean POST_COMPRESSION_BUDGET of tokens.
    Re-injects only schemas actively referenced in the last N batches.
    """

    CRITICAL_SCHEMA_BUDGET:    int = 5_000   # tokens per schema
    RECENT_SCHEMAS_TO_KEEP:    int = 3

    def compact(
        self,
        state: ForgeSessionState,
        critical_schemas: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Wipe the session state and rebuild it from *critical_schemas*.

        Parameters
        ----------
        state            : session state to compress in-place
        critical_schemas : schemas to re-inject (most recently used first)

        Returns the compact manifest describing what survived.
        """
        original_estimate = state.token_estimate

        # --- Wipe everything ---
        state.field_analyses.clear()
        state.generation_log.clear()
        state.schema_snapshots.clear()
        state.token_estimate = 0

        # --- Re-inject critical schemas up to budget ---
        kept_schemas: List[str] = []
        schemas_to_keep = (critical_schemas or [])[:self.RECENT_SCHEMAS_TO_KEEP]

        for schema in schemas_to_keep:
            schema_tokens = len(json.dumps(schema)) // 4
            if schema_tokens > self.CRITICAL_SCHEMA_BUDGET:
                continue   # too large to inject
            state.schema_snapshots.append(schema)
            state.token_estimate += schema_tokens
            kept_schemas.append(schema.get("model_name", "unknown"))

        manifest = {
            "type": "full_compact_manifest",
            "tokens_before": original_estimate,
            "tokens_after": state.token_estimate,
            "savings_pct": round(
                100 * (1 - state.token_estimate / max(original_estimate, 1)), 1
            ),
            "schemas_re_injected": kept_schemas,
            "post_budget": POST_COMPRESSION_BUDGET,
            "compressed_at": time.time(),
        }
        print(
            f"   🗜️  FullForgeCompact: {manifest['tokens_before']:,} → "
            f"{manifest['tokens_after']:,} tokens "
            f"({manifest['savings_pct']}% reduction)"
        )
        return manifest


# ---------------------------------------------------------------------------
# CompressionPipeline — orchestrator
# ---------------------------------------------------------------------------

class CompressionPipeline:
    """
    Orchestrates all three layers in priority order.

    Call ``maybe_compact(state)`` after every generation batch.
    The pipeline selects the cheapest layer that brings the state back
    under budget.
    """

    def __init__(self) -> None:
        self._micro = MicroForgeCompact()
        self._auto  = AutoForgeCompact()
        self._full  = FullForgeCompact()

    def maybe_compact(
        self,
        state: ForgeSessionState,
        critical_schemas: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """
        Run compression if needed.  Returns the layer that ran, or None.
        """
        if not state.is_near_budget():
            return None

        # Layer 1: try micro-compact first (zero cost)
        removed = self._micro.compact(state)
        if removed > 0:
            print(f"   🗜️  MicroForgeCompact: removed {removed} stale field analyses")
        if not state.is_near_budget():
            return "micro"

        # Layer 2: auto-compact (structured summary)
        if not self._auto.is_broken:
            summary = self._auto.compact(state)
            if summary:
                print(
                    f"   🗜️  AutoForgeCompact: summarised {summary.get('total_records', '?')} "
                    f"records across {summary.get('unique_models', '?')} models"
                )
            if not state.is_over_budget():
                return "auto"

        # Layer 3: full compact (last resort)
        self._full.compact(state, critical_schemas=critical_schemas)
        return "full"
