"""
SmartFailureAnalyzer — AI-powered pytest failure diagnostics.

Hooks into pytest's report pipeline and analyzes FAILED tests using Groq.
Prints a structured diagnosis to the console after each failure.

IMPORTANT:
  - Never modifies test results or retry logic
  - Never changes the failure status of any test
  - Only activated on explicit opt-in (add to conftest.py)
  - Requires GROQ_API_KEY — silently skips analysis if not set

Setup (conftest.py):
    from fixtureforge.ai import SmartFailureAnalyzer
    pytest_plugins = [SmartFailureAnalyzer()]   # pass an instance

Or register via pytest plugin list:
    # conftest.py
    from fixtureforge.ai.failure_analyzer import SmartFailureAnalyzer
    def pytest_configure(config):
        config.pluginmanager.register(SmartFailureAnalyzer(), "fixtureforge-analyzer")
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

from ._audit_log import log_event
from ._groq_client import LLMClientError, groq_complete

# ---------------------------------------------------------------------------
# Terminal encoding safety
# Detect if the terminal supports Unicode box-drawing characters.
# Windows cmd / PowerShell with cp1255 / cp1252 encoding cannot render them.
# ---------------------------------------------------------------------------

def _supports_unicode() -> bool:
    enc = getattr(sys.stdout, "encoding", None) or ""
    return enc.lower().replace("-", "") in ("utf8", "utf8sig")


_USE_UNICODE = _supports_unicode()


def _box(title: str, lines: list[str]) -> str:
    """Render a labeled box. ASCII-safe on non-UTF-8 terminals."""
    if _USE_UNICODE:
        width = max(len(title) + 4, max((len(l) for l in lines), default=0) + 4, 50)
        top    = f"\u2554{'=' * (width - 2)}\u2557"
        header = f"\u2551  {title:<{width - 4}}  \u2551"
        sep    = f"\u2560{'-' * (width - 2)}\u2563"
        bottom = f"\u255a{'=' * (width - 2)}\u255d"
        body   = "\n".join(f"\u2551  {l:<{width - 4}}  \u2551" for l in lines)
        return "\n".join([top, header, sep, body, bottom])
    else:
        width = max(len(title) + 4, max((len(l) for l in lines), default=0) + 4, 50)
        border = "+" + "=" * (width - 2) + "+"
        divider = "+" + "-" * (width - 2) + "+"
        header = f"|  {title:<{width - 4}}  |"
        body   = "\n".join(f"|  {l:<{width - 4}}  |" for l in lines)
        return "\n".join([border, header, divider, body, border])


# ---------------------------------------------------------------------------
# Groq prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a senior QA engineer and Python expert. "
    "Analyze test failures and provide concise, actionable diagnostics. "
    "Return ONLY valid JSON — no markdown, no explanation outside the JSON. "
    "Format: {"
    '"explanation": "one sentence describing what went wrong", '
    '"likely_cause": "root cause in plain English", '
    '"suggested_fix": "specific code-level action to resolve it"'
    "}"
)

_TAIL_LINES = 20  # number of traceback lines to send


# ---------------------------------------------------------------------------
# SmartFailureAnalyzer plugin
# ---------------------------------------------------------------------------

class SmartFailureAnalyzer:
    """
    pytest plugin that analyzes FAILED tests with Groq AI.

    Behavior:
    - Triggers only when a test's call phase fails
    - Sends: test ID + exception type + exception message + last 20 traceback lines
    - Prints a structured analysis block to stdout
    - Logs every interaction to .fixtureforge_ai_log.jsonl
    - NEVER modifies report.passed or any test state

    Registration (conftest.py):
        from fixtureforge.ai import SmartFailureAnalyzer
        def pytest_configure(config):
            config.pluginmanager.register(SmartFailureAnalyzer(), "forge-analyzer")
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key
        self._analyzed: int = 0

    # ------------------------------------------------------------------
    # pytest hook
    # ------------------------------------------------------------------

    def pytest_runtest_logreport(self, report: Any) -> None:
        """Called by pytest after each test phase (setup / call / teardown)."""
        if report.when != "call" or not report.failed:
            return

        # Skip if GROQ_API_KEY is not available — never block the test run
        key = self._api_key or os.environ.get("GROQ_API_KEY", "")
        if not key:
            return

        self._analyze(report, api_key=key)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def _extract_failure_info(self, report: Any) -> dict[str, str]:
        """Pull structured info out of a pytest report object."""
        nodeid = getattr(report, "nodeid", "unknown_test")
        longrepr = report.longrepr

        # longrepr can be a string, tuple, or ExceptionInfo object
        if isinstance(longrepr, str):
            full_tb = longrepr
            exc_type = "UnknownError"
            exc_msg  = longrepr[:300]
        elif isinstance(longrepr, tuple):
            # (path, lineno, message) format from some pytest versions
            full_tb = "\n".join(str(p) for p in longrepr)
            exc_type = "Error"
            exc_msg  = str(longrepr[-1])[:300]
        else:
            # ExceptionInfo / ReprExceptionInfo
            full_tb  = str(longrepr)
            lines    = full_tb.splitlines()
            exc_type = "UnknownError"
            exc_msg  = ""
            # find the last "E  " line — that's the exception message
            for line in reversed(lines):
                stripped = line.strip()
                if stripped.startswith("E "):
                    exc_msg = stripped[2:].strip()
                    break
            # find exception class name
            for line in reversed(lines):
                for keyword in ("Error", "Exception", "Failure", "assert"):
                    if keyword in line:
                        exc_type = line.strip()[:80]
                        break

        # last N lines of traceback (avoid huge prompts)
        tail_lines = full_tb.splitlines()[-_TAIL_LINES:]
        tail = "\n".join(tail_lines)

        return {
            "nodeid": nodeid,
            "exc_type": exc_type,
            "exc_msg": exc_msg,
            "tail": tail,
        }

    def _call_groq(self, info: dict[str, str], api_key: str) -> dict[str, str]:
        """Send failure info to Groq and parse structured JSON response."""
        user_msg = (
            f"Test: {info['nodeid']}\n"
            f"Error type: {info['exc_type']}\n"
            f"Error message: {info['exc_msg']}\n"
            f"Traceback (last {_TAIL_LINES} lines):\n{info['tail']}"
        )
        raw = groq_complete(
            system=_SYSTEM_PROMPT,
            user=user_msg,
            api_key=api_key,
        )
        # strip markdown fences if model ignored instructions
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(clean)
        return {
            "explanation":   str(parsed.get("explanation", "")),
            "likely_cause":  str(parsed.get("likely_cause", "")),
            "suggested_fix": str(parsed.get("suggested_fix", "")),
        }

    def _print_analysis(self, info: dict[str, str], analysis: dict[str, str]) -> None:
        """Print the analysis block to stdout — encoding-safe."""
        label = "FixtureForge AI Analysis"
        lines = [
            f"Test   : {info['nodeid']}",
            "",
            f"Cause  : {analysis['likely_cause']}",
            "",
            f"Detail : {analysis['explanation']}",
            "",
            f"Fix    : {analysis['suggested_fix']}",
        ]
        box = _box(label, lines)
        # Write via sys.stdout with explicit encoding fallback
        try:
            print("\n" + box + "\n", flush=True)
        except UnicodeEncodeError:
            safe = (box
                    .encode(sys.stdout.encoding or "ascii", errors="replace")
                    .decode(sys.stdout.encoding or "ascii"))
            print("\n" + safe + "\n", flush=True)

    def _analyze(self, report: Any, api_key: str) -> None:
        """Full analysis pipeline for one failed test."""
        info = self._extract_failure_info(report)

        try:
            analysis = self._call_groq(info, api_key=api_key)
        except (LLMClientError, json.JSONDecodeError, KeyError) as exc:
            log_event("failure_analysis_error", {
                "nodeid": info["nodeid"],
                "error": str(exc),
            })
            return  # silently skip — never interrupt the test session

        self._print_analysis(info, analysis)
        self._analyzed += 1

        log_event("failure_analysis", {
            "nodeid":       info["nodeid"],
            "exc_type":     info["exc_type"],
            "explanation":  analysis["explanation"],
            "likely_cause": analysis["likely_cause"],
            "suggested_fix": analysis["suggested_fix"],
        })

    # ------------------------------------------------------------------
    # Summary (optional hook)
    # ------------------------------------------------------------------

    def pytest_terminal_summary(self, terminalreporter: Any, exitstatus: int) -> None:
        """Append a one-line summary at the end of the pytest session."""
        if self._analyzed > 0:
            terminalreporter.write_sep(
                "-",
                f"FixtureForge AI: analyzed {self._analyzed} failure(s) -- "
                f"see .fixtureforge_ai_log.jsonl for full audit trail",
            )
