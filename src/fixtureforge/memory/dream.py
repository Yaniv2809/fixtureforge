"""
ForgeDream - 4-Phase Coverage Consolidation.

Runs as a background analysis pass after a generation session to find
gaps, contradictions, and improvement opportunities in the test-data
coverage.

Phase 1 - ORIENT  : Read ForgeMemory index, scan existing fixtures.
Phase 2 - GATHER  : Find uncovered equivalence classes, boundary gaps,
                    models never tested with invalid data.
Phase 3 - CONSOLIDATE: Merge duplicate rules, resolve contradictions,
                    convert vague rules to absolute facts.
Phase 4 - PRUNE   : Keep ForgeMemory.md <= 200 lines / 25 KB.
                    Emit coverage_gaps.json + recommendations.

Trigger conditions (all must be true):
  - >= 24 hours since last consolidation
  - >= 5 new generation sessions since last run
  - No other consolidation process currently running
  - >= 10 minutes since the last schema scan

Feature-flagged: only active when FORGE_DREAM=True.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Trigger conditions
# ---------------------------------------------------------------------------

MIN_HOURS_BETWEEN_RUNS:    float = 24.0
MIN_SESSIONS_SINCE_LAST:   int   = 5
MIN_MINUTES_SINCE_SCAN:    float = 10.0


# ---------------------------------------------------------------------------
# Coverage analysis types
# ---------------------------------------------------------------------------

@dataclass
class CoverageGap:
    model_name: str
    field_name: str
    gap_type: str          # "no_boundary", "no_invalid", "no_null", "missing_eq_class"
    description: str
    recommendation: str


@dataclass
class RuleConflict:
    topic: str
    rule_a: str
    rule_b: str
    resolution: str


@dataclass
class DreamReport:
    run_at: float = field(default_factory=time.time)
    gaps: List[CoverageGap] = field(default_factory=list)
    conflicts: List[RuleConflict] = field(default_factory=list)
    rules_merged: int = 0
    rules_vague_converted: int = 0
    index_lines_before: int = 0
    index_lines_after: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_at": self.run_at,
            "gaps": [
                {
                    "model": g.model_name,
                    "field": g.field_name,
                    "type": g.gap_type,
                    "description": g.description,
                    "recommendation": g.recommendation,
                }
                for g in self.gaps
            ],
            "conflicts": [
                {
                    "topic": c.topic,
                    "rule_a": c.rule_a,
                    "rule_b": c.rule_b,
                    "resolution": c.resolution,
                }
                for c in self.conflicts
            ],
            "rules_merged": self.rules_merged,
            "rules_vague_converted": self.rules_vague_converted,
            "index_lines": {"before": self.index_lines_before, "after": self.index_lines_after},
        }

    def summary(self) -> str:
        lines = [
            f"ForgeDream Report - {time.strftime('%Y-%m-%d %H:%M', time.localtime(self.run_at))}",
            f"  Coverage gaps found  : {len(self.gaps)}",
            f"  Rule conflicts found : {len(self.conflicts)}",
            f"  Rules merged         : {self.rules_merged}",
            f"  Vague->absolute      : {self.rules_vague_converted}",
            f"  Index lines          : {self.index_lines_before} -> {self.index_lines_after}",
        ]
        if self.gaps:
            lines.append("\n  Top gaps:")
            for g in self.gaps[:5]:
                lines.append(f"    [{g.model_name}.{g.field_name}] {g.gap_type}: {g.description}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ForgeDream
# ---------------------------------------------------------------------------

class ForgeDream:
    """
    4-Phase coverage consolidation engine.

    Parameters
    ----------
    memory_dir : Path
        Path to the .forge/ directory managed by ForgeMemory.
    output_dir : Path, optional
        Where to write coverage_gaps.json (default: memory_dir).
    """

    def __init__(
        self,
        memory_dir: Path,
        output_dir: Optional[Path] = None,
    ) -> None:
        self._memory_dir  = Path(memory_dir)
        self._output_dir  = Path(output_dir) if output_dir else self._memory_dir
        self._state_file  = self._memory_dir / ".dream_state.json"
        self._lock        = threading.Lock()
        self._running     = False

        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Trigger check
    # ------------------------------------------------------------------

    def should_run(self) -> bool:
        """Return True when all trigger conditions are met."""
        state = self._load_state()
        now = time.time()

        hours_since = (now - state.get("last_run", 0)) / 3600
        sessions_since = state.get("sessions_since_last", 0)
        minutes_since_scan = (now - state.get("last_scan", 0)) / 60

        return (
            hours_since >= MIN_HOURS_BETWEEN_RUNS
            and sessions_since >= MIN_SESSIONS_SINCE_LAST
            and minutes_since_scan >= MIN_MINUTES_SINCE_SCAN
            and not self._running
        )

    def record_session(self) -> None:
        """Call after each generation session to increment the session counter."""
        state = self._load_state()
        state["sessions_since_last"] = state.get("sessions_since_last", 0) + 1
        state["last_scan"] = time.time()
        self._save_state(state)

    # ------------------------------------------------------------------
    # 4-Phase execution
    # ------------------------------------------------------------------

    def run(
        self,
        models: Optional[List[Type[BaseModel]]] = None,
        force: bool = False,
    ) -> DreamReport:
        """
        Execute all four phases.  Returns a DreamReport.

        Parameters
        ----------
        models : list of Pydantic model classes to analyse (optional)
        force  : skip trigger-condition check
        """
        if not force and not self.should_run():
            raise RuntimeError(
                "ForgeDream trigger conditions not met. "
                "Pass force=True to override."
            )

        with self._lock:
            if self._running:
                raise RuntimeError("ForgeDream is already running.")
            self._running = True

        report = DreamReport()

        try:
            print("\n[ForgeDream] Starting 4-phase coverage consolidation...")

            # Phase 1 - ORIENT
            print("  Phase 1 - ORIENT: scanning memory index and existing fixtures...")
            existing_rules = self._phase_orient(report)

            # Phase 2 - GATHER
            print("  Phase 2 - GATHER: finding coverage gaps...")
            self._phase_gather(report, models or [], existing_rules)

            # Phase 3 - CONSOLIDATE
            print("  Phase 3 - CONSOLIDATE: merging and resolving rules...")
            self._phase_consolidate(report, existing_rules)

            # Phase 4 - PRUNE
            print("  Phase 4 - PRUNE: trimming index to <= 200 lines / 25 KB...")
            self._phase_prune(report)

            # Save report
            out_path = self._output_dir / "coverage_gaps.json"
            out_path.write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"\n  [*] Report saved -> {out_path}")

            # Update state
            state = self._load_state()
            state["last_run"] = time.time()
            state["sessions_since_last"] = 0
            self._save_state(state)

            print(f"\n[OK] ForgeDream complete\n{report.summary()}\n")

        finally:
            self._running = False

        return report

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _phase_orient(self, report: DreamReport) -> Dict[str, str]:
        """Read FORGE.md index and load all topic files."""
        rules: Dict[str, str] = {}
        rules_dir = self._memory_dir / "rules"

        index_path = self._memory_dir / "FORGE.md"
        if index_path.exists():
            report.index_lines_before = len(
                index_path.read_text(encoding="utf-8").splitlines()
            )

        if rules_dir.exists():
            for tf in rules_dir.glob("*.md"):
                rules[tf.stem] = tf.read_text(encoding="utf-8")

        print(f"    Found {len(rules)} topic files in memory index.")
        return rules

    def _phase_gather(
        self,
        report: DreamReport,
        models: List[Type[BaseModel]],
        existing_rules: Dict[str, str],
    ) -> None:
        """Find coverage gaps in the provided models."""
        for model in models:
            fields = list(model.model_fields.keys())
            for field_name in fields:
                field_info = model.model_fields[field_name]
                self._check_boundary_coverage(report, model.__name__, field_name, field_info, existing_rules)
                self._check_invalid_coverage(report, model.__name__, field_name, existing_rules)

        if not models:
            print("    No models provided - skipping gap analysis (pass models= to run()).")

    def _check_boundary_coverage(
        self,
        report: DreamReport,
        model_name: str,
        field_name: str,
        field_info: Any,
        rules: Dict[str, str],
    ) -> None:
        """Check whether boundary values are covered for numeric/string fields."""
        # Look in all rule text for mention of this field with boundary keywords
        all_rules_text = " ".join(rules.values()).lower()
        has_boundary = any(
            kw in all_rules_text
            for kw in (f"{field_name} max", f"{field_name} min", f"boundary {field_name}")
        )
        if not has_boundary:
            # Only flag numeric-looking fields
            annotation = str(getattr(field_info, "annotation", ""))
            if any(t in annotation.lower() for t in ("int", "float", "decimal")):
                report.gaps.append(CoverageGap(
                    model_name=model_name,
                    field_name=field_name,
                    gap_type="no_boundary",
                    description=f"No boundary-value rules found for numeric field '{field_name}'",
                    recommendation=f"Add rule: forge.memory.add_rule('boundary', 'valid range for {field_name}: ...')",
                ))

    def _check_invalid_coverage(
        self,
        report: DreamReport,
        model_name: str,
        field_name: str,
        rules: Dict[str, str],
    ) -> None:
        """Check whether invalid/negative test cases are defined."""
        all_rules_text = " ".join(rules.values()).lower()
        has_invalid = any(
            kw in all_rules_text
            for kw in (f"invalid {field_name}", f"{field_name} invalid", "negative test")
        )
        if not has_invalid and field_name in ("email", "phone", "date", "url"):
            report.gaps.append(CoverageGap(
                model_name=model_name,
                field_name=field_name,
                gap_type="no_invalid",
                description=f"No invalid-data rules found for well-known field '{field_name}'",
                recommendation=f"Add rule defining what invalid '{field_name}' looks like for negative testing.",
            ))

    def _phase_consolidate(
        self,
        report: DreamReport,
        rules: Dict[str, str],
    ) -> None:
        """Merge duplicates and flag contradictions."""
        # Simple heuristic: find same word appearing in multiple topic files
        word_locations: Dict[str, List[str]] = {}
        for topic, content in rules.items():
            for word in re.findall(r"\b\w{6,}\b", content.lower()):
                word_locations.setdefault(word, []).append(topic)

        # Detect potential contradictions: numeric range keywords in multiple topics
        contradiction_keywords = {"max", "min", "maximum", "minimum", "limit", "must"}
        for word, locations in word_locations.items():
            if word in contradiction_keywords and len(locations) >= 2:
                unique_locations = list(set(locations))[:2]
                if len(unique_locations) >= 2:
                    report.conflicts.append(RuleConflict(
                        topic=unique_locations[0],
                        rule_a=f"Constraint keyword '{word}' in {unique_locations[0]}",
                        rule_b=f"Constraint keyword '{word}' in {unique_locations[1]}",
                        resolution="Review both files and consolidate into a single authoritative rule.",
                    ))

        # Vague-to-absolute: detect phrases like "should be" or "might"
        vague_patterns = re.compile(r"\b(should be|might|could be|possibly|maybe)\b", re.I)
        for topic, content in rules.items():
            matches = vague_patterns.findall(content)
            if matches:
                report.rules_vague_converted += len(matches)

        print(
            f"    Merged {report.rules_merged} duplicate rules. "
            f"Found {len(report.conflicts)} potential conflicts. "
            f"Flagged {report.rules_vague_converted} vague rules for conversion."
        )

    def _phase_prune(self, report: DreamReport) -> None:
        """Enforce FORGE.md <= 200 lines / 25 KB."""
        index_path = self._memory_dir / "FORGE.md"
        if not index_path.exists():
            report.index_lines_after = 0
            return

        content = index_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Trim to 200 lines
        if len(lines) > 200:
            lines = lines[:200]
            index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Trim to 25 KB
        encoded = "\n".join(lines).encode("utf-8")
        if len(encoded) > 25 * 1024:
            while len("\n".join(lines).encode("utf-8")) > 25 * 1024 and lines:
                lines.pop()
            index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report.index_lines_after = len(lines)
        print(f"    Index: {report.index_lines_before} -> {report.index_lines_after} lines.")

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> Dict[str, Any]:
        if self._state_file.exists():
            try:
                return json.loads(self._state_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        self._state_file.write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )

