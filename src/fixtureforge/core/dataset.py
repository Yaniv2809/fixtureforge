"""
ForgeDataset — large-result persistence.

When a generation result exceeds INLINE_THRESHOLD characters, it is written to
disk and replaced with a short preview in memory.  This mirrors the pattern
where large tool results are spilled to disk and only a small preview is kept
in the active context window.

    INLINE_THRESHOLD = 50_000 chars  (~50 KB)
    PREVIEW_SIZE     = 2_000  chars  (~2 KB headline)

Usage:
    from fixtureforge.core.dataset import ForgeDataset

    dataset = ForgeDataset(items)               # wrap any list of Pydantic models
    print(dataset.preview())                    # always fast
    full = dataset.load()                       # re-loads from disk if spilled
    dataset.save("my_output.json")              # explicit export
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

INLINE_THRESHOLD: int = 50_000   # chars
PREVIEW_SIZE:     int = 2_000    # chars


class ForgeDataset(Generic[T]):
    """
    Wraps a list of generated model instances with automatic disk-spill logic.

    After ``wrap()``, call ``preview()`` for a quick summary or ``load()``
    to get all records back.  If the dataset was small enough to stay inline,
    ``load()`` is free (no disk I/O).
    """

    def __init__(
        self,
        items: List[T],
        spill_dir: Optional[Path] = None,
    ) -> None:
        self._inline: Optional[List[T]]    = None
        self._spill_path: Optional[Path]   = None
        self._model_name: str              = ""
        self._count: int                   = len(items)
        self._spill_dir: Path              = spill_dir or Path(tempfile.gettempdir()) / "fixtureforge"
        self._spill_dir.mkdir(parents=True, exist_ok=True)

        if items:
            self._model_name = type(items[0]).__name__

        self._maybe_spill(items)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preview(self, n: int = 5) -> str:
        """
        Return a short summary string — never triggers disk I/O.
        Shows the first ``n`` records inline.
        """
        location = (
            f"[spilled → {self._spill_path}]"
            if self._spill_path
            else "[inline]"
        )
        header = (
            f"ForgeDataset<{self._model_name}> "
            f"— {self._count} records {location}\n"
        )

        if self._inline is not None:
            sample = self._inline[:n]
        else:
            sample = self._load_raw()[:n]

        lines = []
        for i, item in enumerate(sample):
            raw = json.dumps(item.model_dump(), ensure_ascii=False)
            lines.append(f"  [{i}] {raw[:200]}")

        more = (
            f"  ... and {self._count - n} more records."
            if self._count > n
            else ""
        )
        return header + "\n".join(lines) + ("\n" + more if more else "")

    def load(self) -> List[T]:
        """Return all records. Re-hydrates from disk if the dataset was spilled."""
        if self._inline is not None:
            return self._inline
        return self._load_raw()

    def save(self, path: str | Path) -> Path:
        """Write all records to *path* as a JSON array. Returns the final path."""
        out = Path(path)
        records = self.load()
        out.write_text(
            json.dumps([r.model_dump() for r in records], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return out

    @property
    def count(self) -> int:
        return self._count

    @property
    def is_spilled(self) -> bool:
        return self._spill_path is not None

    def __len__(self) -> int:
        return self._count

    def __repr__(self) -> str:
        spill_info = f", spilled={self._spill_path}" if self._spill_path else ""
        return f"ForgeDataset<{self._model_name}>({self._count} records{spill_info})"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_spill(self, items: List[T]) -> None:
        """Decide inline vs spill based on serialized size."""
        if not items:
            self._inline = []
            return

        raw = json.dumps([item.model_dump() for item in items], ensure_ascii=False)

        if len(raw) <= INLINE_THRESHOLD:
            self._inline = items
            return

        # Spill to disk
        spill_file = self._spill_dir / f"forge_{self._model_name}_{id(items)}.json"
        spill_file.write_text(raw, encoding="utf-8")
        self._spill_path = spill_file

        size_kb = len(raw) / 1024
        print(
            f"   💾 Dataset spilled to disk: {self._count} records "
            f"({size_kb:.1f} KB) → {spill_file.name}\n"
            f"      {PREVIEW_SIZE}-char preview kept in memory."
        )

    def _load_raw(self) -> List[Any]:
        """Read back spilled data. Returns plain dicts — caller reassembles models."""
        if not self._spill_path or not self._spill_path.exists():
            return []
        data = json.loads(self._spill_path.read_text(encoding="utf-8"))
        return data
