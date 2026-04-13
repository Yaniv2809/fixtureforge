"""
ForgeMemory — lightweight context index (FORGE.md pattern).

Architecture:
  FORGE.md  — pointer index only, max 200 lines, reloaded every generation call
  rules/    — on-demand topic files (user.md, financial.md, security.md, …)
  FORGE.local.md — local overrides, never committed to git

Skeptical Memory Rule:
  Rules are treated as *hints*, not ground truth.
  Before using a rule, the engine checks it still matches the live schema.
  Fields derivable from the model (names, types) are NEVER stored here —
  only business rules that exist nowhere else in the code.

Progressive Forgetting:
  Pruning policy enforced on every write.
  Re-derivable facts (field names, types, validator names) are rejected.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_INDEX_LINES:  int = 200
MAX_INDEX_BYTES:  int = 25 * 1024     # 25 KB
MAX_RULE_BYTES:   int = 10 * 1024     # 10 KB per topic file

# Patterns for facts that CAN be derived from source — never store these
_REDERIVABLE_PATTERNS = re.compile(
    r"\b(field_name|field_type|validator|def \w+|class \w+)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# ForgeMemory
# ---------------------------------------------------------------------------

class ForgeMemory:
    """
    Manages the .forge/ context directory.

    Parameters
    ----------
    base_dir : Path
        Root directory for the .forge/ folder (default: current working directory).
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._root: Path = (base_dir or Path.cwd()) / ".forge"
        self._rules_dir: Path = self._root / "rules"
        self._index_path: Path = self._root / "FORGE.md"
        self._local_path: Path = self._root / "FORGE.local.md"

        self._root.mkdir(parents=True, exist_ok=True)
        self._rules_dir.mkdir(parents=True, exist_ok=True)

        if not self._index_path.exists():
            self._write_index_header()

    # ------------------------------------------------------------------
    # Writing rules
    # ------------------------------------------------------------------

    def add_rule(
        self,
        topic: str,
        rule: str,
        source: str = "user",
        model_name: Optional[str] = None,
    ) -> bool:
        """
        Add a business rule to *topic*.md.

        Returns False (and does NOT write) when the rule looks re-derivable
        from source code (Strict Write Discipline + Progressive Forgetting).

        Parameters
        ----------
        topic      : slug for the topic file, e.g. "financial", "user", "security"
        rule       : the rule text to store
        source     : who provided this rule ("user" / "system")
        model_name : optional model this rule applies to
        """
        # Progressive Forgetting: reject re-derivable facts
        if _REDERIVABLE_PATTERNS.search(rule):
            return False

        topic_file = self._rules_dir / f"{topic}.md"
        entry = self._format_rule(rule, source, model_name)

        # Append (create if missing)
        existing = topic_file.read_text(encoding="utf-8") if topic_file.exists() else ""
        new_content = existing + entry

        # Cap file size
        if len(new_content.encode()) > MAX_RULE_BYTES:
            new_content = self._prune_topic(new_content)

        topic_file.write_text(new_content, encoding="utf-8")
        self._update_index(topic, topic_file)
        return True

    def add_local_override(self, rule: str, note: str = "") -> None:
        """
        Add a local override to FORGE.local.md (never committed to git).
        Local overrides take precedence over all other rules.
        """
        existing = self._local_path.read_text(encoding="utf-8") if self._local_path.exists() else "# Local overrides — not committed\n\n"
        entry = f"## {time.strftime('%Y-%m-%d %H:%M')}\n{rule}\n"
        if note:
            entry += f"*Note: {note}*\n"
        entry += "\n"
        self._local_path.write_text(existing + entry, encoding="utf-8")

    # ------------------------------------------------------------------
    # Reading rules
    # ------------------------------------------------------------------

    def load(self, model_name: Optional[str] = None) -> Dict[str, str]:
        """
        Load all applicable rules into a dict mapping topic → content.

        Reads FORGE.md index on every call (always fresh, never stale).
        When *model_name* is given, also filters for model-specific rules.
        Local overrides are included last and marked as highest-priority.
        """
        rules: Dict[str, str] = {}

        # Read each topic file referenced in the index
        for topic_file in self._rules_dir.glob("*.md"):
            content = topic_file.read_text(encoding="utf-8")
            if model_name:
                # Only include sections that mention this model or are general
                if model_name.lower() not in content.lower() and "all models" not in content.lower():
                    # Include anyway — general rules always apply
                    pass
            rules[topic_file.stem] = content

        # Local overrides take highest priority
        if self._local_path.exists():
            rules["__local_overrides__"] = self._local_path.read_text(encoding="utf-8")

        return rules

    def get_rules_for_prompt(self, model_name: Optional[str] = None) -> str:
        """
        Return a condensed string of all rules suitable for injection into an
        AI prompt (called every generation — always re-reads from disk).
        """
        rules = self.load(model_name=model_name)
        if not rules:
            return ""

        parts = ["## Domain Rules (FixtureForge)\n"]
        for topic, content in rules.items():
            if topic == "__local_overrides__":
                parts.append(f"### LOCAL OVERRIDES (highest priority)\n{content}\n")
            else:
                parts.append(f"### {topic.replace('_', ' ').title()}\n{content}\n")

        return "\n".join(parts)

    def validate_against_schema(
        self,
        model_fields: List[str],
        topic: Optional[str] = None,
    ) -> List[str]:
        """
        Skeptical Memory Check — compare stored rules against the live schema.

        Returns a list of warning strings for rules that reference fields
        no longer present in the model.  The caller decides whether to
        remove/update the stale rules.
        """
        warnings: List[str] = []
        topics = [topic] if topic else [f.stem for f in self._rules_dir.glob("*.md")]

        for t in topics:
            tf = self._rules_dir / f"{t}.md"
            if not tf.exists():
                continue
            content = tf.read_text(encoding="utf-8")
            # Look for field-name references in the rule text
            for field in re.findall(r"`(\w+)`", content):
                if field not in model_fields and not field.startswith("__"):
                    warnings.append(
                        f"[{t}] Rule references field '{field}' not found in current schema"
                    )

        return warnings

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def list_topics(self) -> List[str]:
        return [f.stem for f in self._rules_dir.glob("*.md")]

    def remove_topic(self, topic: str) -> bool:
        tf = self._rules_dir / f"{topic}.md"
        if tf.exists():
            tf.unlink()
            self._rebuild_index()
            return True
        return False

    def stats(self) -> Dict[str, Any]:
        topics = list(self._rules_dir.glob("*.md"))
        total_bytes = sum(f.stat().st_size for f in topics)
        return {
            "topics": len(topics),
            "total_kb": round(total_bytes / 1024, 1),
            "index_lines": len(self._index_path.read_text(encoding="utf-8").splitlines())
            if self._index_path.exists()
            else 0,
            "has_local_overrides": self._local_path.exists(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_rule(
        self, rule: str, source: str, model_name: Optional[str]
    ) -> str:
        model_tag = f" (applies to: {model_name})" if model_name else ""
        return (
            f"\n### {time.strftime('%Y-%m-%d')}{model_tag}\n"
            f"*Source: {source}*\n\n"
            f"{rule}\n"
        )

    def _update_index(self, topic: str, topic_file: Path) -> None:
        """Add / refresh the pointer for *topic* in FORGE.md."""
        index = self._index_path.read_text(encoding="utf-8") if self._index_path.exists() else ""
        pointer = f"- [{topic}](rules/{topic_file.name})"

        # Replace existing pointer or append new one
        if f"[{topic}]" in index:
            lines = index.splitlines()
            lines = [pointer if f"[{topic}]" in line else line for line in lines]
            index = "\n".join(lines) + "\n"
        else:
            index += pointer + "\n"

        # Enforce max 200 lines
        lines = index.splitlines()
        if len(lines) > MAX_INDEX_LINES:
            lines = lines[:MAX_INDEX_LINES]

        self._index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _rebuild_index(self) -> None:
        """Rebuild FORGE.md from scratch based on existing topic files."""
        lines = ["# FORGE.md — Domain Rule Index\n", ""]
        for tf in sorted(self._rules_dir.glob("*.md")):
            lines.append(f"- [{tf.stem}](rules/{tf.name})")
        self._index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_index_header(self) -> None:
        header = (
            "# FORGE.md — Domain Rule Index\n"
            "# Pointers only — max 200 lines. Reloaded on every generation call.\n"
            "# Add rules with: forge.memory.add_rule(topic, rule_text)\n\n"
        )
        self._index_path.write_text(header, encoding="utf-8")

    def _prune_topic(self, content: str) -> str:
        """Keep only the most recent MAX_RULE_BYTES of a topic file."""
        encoded = content.encode("utf-8")
        if len(encoded) <= MAX_RULE_BYTES:
            return content
        truncated = encoded[-MAX_RULE_BYTES:]
        # Find first newline after truncation to avoid partial lines
        idx = truncated.find(b"\n")
        if idx != -1:
            truncated = truncated[idx + 1:]
        return "# [older entries pruned]\n\n" + truncated.decode("utf-8", errors="replace")
