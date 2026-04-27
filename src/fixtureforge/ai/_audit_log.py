"""
Audit log for FixtureForge AI features.

Every LLM call made by assert_semantic_match or SmartFailureAnalyzer
is appended here as a JSONL record. Zero API calls are made during import.

Log location: .fixtureforge_ai_log.jsonl  (project root / cwd)
Format:       one JSON object per line, UTF-8, append-only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_FILENAME = ".fixtureforge_ai_log.jsonl"


def _log_path() -> Path:
    """Return the audit log path relative to the current working directory."""
    return Path(os.getcwd()) / LOG_FILENAME


def log_event(event_type: str, data: dict[str, Any]) -> None:
    """
    Append one event record to the audit log.

    Args:
        event_type: Short label — e.g. "semantic_assert_llm", "failure_analysis".
        data:       Dict of arbitrary key-value pairs to record.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **data,
    }
    try:
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        # Never crash a test run because of a logging failure.
        pass
