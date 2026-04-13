"""
FixtureForge v2.0 — Compile-time Feature Flags.

Flags control which subsystems are active at runtime.
Override any flag via environment variable:
    FORGE_FLAG_DREAM=1      enables ForgeDream
    FORGE_FLAG_SWARMS=0     disables DataSwarms
    FORGE_FLAG_ANTI_DIST=1  enables anti-distillation

Version strategy:
    v2.0  ships:  MCP, SWARMS, PERMISSIONS, COMPRESSION
    v2.x  ships:  KAIROS, DREAM, ULTRAPLAN, VOICE, ANTI_DIST
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Default flag values — edit here or override via env vars
# ---------------------------------------------------------------------------

FORGE_FLAGS: dict[str, bool] = {
    # ── Shipped in v2.0 ───────────────────────────────────────────────────
    "FORGE_SWARMS":       True,   # Parallel DataSwarm generation
    "FORGE_MCP":          True,   # MCP server mode
    "FORGE_PERMISSIONS":  True,   # safe/sensitive/dangerous gates
    "FORGE_COMPRESSION":  True,   # Three-layer compression pipeline
    # ── Feature-gated (built but not shipped) ────────────────────────────
    "FORGE_DREAM":        False,  # ForgeDream 4-phase coverage consolidation
    "FORGE_KAIROS":       False,  # Proactive background model watcher
    "FORGE_ULTRAPLAN":    False,  # Opus-class complex model analysis
    "FORGE_ANTI_DIST":    False,  # Anti-distillation decoy schemas
    "FORGE_VOICE":        False,  # Voice-driven fixture generation (future)
}

# ---------------------------------------------------------------------------
# Apply environment-variable overrides at import time
# Each flag "FORGE_XYZ" maps to env var "FORGE_FLAG_XYZ"
# ---------------------------------------------------------------------------

for _flag_name in list(FORGE_FLAGS.keys()):
    _env_key = "FORGE_FLAG_" + _flag_name[len("FORGE_"):]   # e.g. FORGE_FLAG_DREAM
    _env_val = os.environ.get(_env_key)
    if _env_val is not None:
        FORGE_FLAGS[_flag_name] = _env_val.strip().lower() in ("1", "true", "yes", "on")


def is_enabled(flag: str) -> bool:
    """Return True if *flag* is active.  Unknown flags are False."""
    return FORGE_FLAGS.get(flag, False)


def flag_summary() -> dict[str, bool]:
    """Return a snapshot of all flag values (useful for diagnostics)."""
    return dict(FORGE_FLAGS)
