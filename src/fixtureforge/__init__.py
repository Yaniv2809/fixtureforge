"""
FixtureForge v2.0 — Agentic Test Data Harness.

Quick start (auto-detects AI provider from env vars):
    from fixtureforge import Forge
    from pydantic import BaseModel

    class User(BaseModel):
        id: int
        name: str
        email: str
        bio: str

    forge = Forge()
    users = forge.create_batch(User, count=50, context="SaaS platform users")

Parallel DataSwarm (multiple models, shared cache):
    results = forge.swarm([User, Order, Product], counts=[10, 50, 100])
    # → {"User": [...], "Order": [...], "Product": [...]}

Permission gates (safe / sensitive / dangerous):
    forge = Forge(allow_pii=True)   # auto-approve PII fields
    forge = Forge(interactive=False)  # CI mode — reject dangerous gates silently

Domain rules (persisted across sessions):
    forge.memory.add_rule("financial", "Users under 18 get restricted account type")
    forge.memory.add_rule("user", "Israeli phone numbers use format 05x-xxx-xxxx")

Coverage analysis (ForgeDream):
    report = forge.dream(models=[User, Order], force=True)
    print(report.summary())

Feature flags:
    from fixtureforge.config import is_enabled
    is_enabled("FORGE_SWARMS")   # True
    is_enabled("FORGE_DREAM")    # False  (enable with FORGE_FLAG_DREAM=1)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Type, TypeVar

from pydantic import BaseModel

from .ai.engine import AIEngine
from .config.flags import FORGE_FLAGS, flag_summary, is_enabled
from .core.batch_engine import SmartBatchEngine
from .core.compression import CompressionPipeline, ForgeSessionState
from .core.dataset import ForgeDataset
from .core.generator import BasicGenerator
from .core.streamer import DataStreamer
from .core.swarm import DataSwarm
from .memory.dream import ForgeDream
from .memory.store import ForgeMemory
from .providers.base import LLMProvider
from .security.permissions import (
    DataSensitivity,
    FieldPermissionChecker,
    ForgeCoordinator,
)

__version__ = "2.1.0"

T = TypeVar("T", bound=BaseModel)


class Forge:
    """
    Main entry point for FixtureForge v2.0 — Agentic Test Data Harness.

    Parameters
    ----------
    provider : LLMProvider, optional
        A pre-constructed provider instance.
    provider_name : str, optional
        "gemini" | "openai" | "anthropic" | "ollama". Auto-detected from env.
    api_key : str, optional
        Falls back to the relevant env var.
    model : str, optional
        Model identifier. Provider default is used when omitted.
    use_ai : bool
        False = fully deterministic, zero-cost generation (CI safe).
    use_cache : bool
        Cache AI responses to disk (7-day TTL). Default True.
    locale : str
        Faker locale for standard fields (default "en_US").
    allow_pii : bool, optional
        Auto-approve SENSITIVE data generation (overrides FORGE_ALLOW_PII env var).
    interactive : bool
        When False, permission gates in CI mode reject silently instead of prompting.
    memory_dir : Path, optional
        Root for the .forge/ context directory (default: current working directory).
    **provider_kwargs
        Forwarded to the provider constructor.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_ai: bool = True,
        use_cache: bool = True,
        locale: str = "en_US",
        seed: Optional[int] = None,
        verbose: bool = False,
        allow_pii: Optional[bool] = None,
        interactive: bool = True,
        memory_dir: Optional[Path] = None,
        **provider_kwargs,
    ):
        # ── Resolve AI provider ──────────────────────────────────────────
        resolved_provider: Optional[LLMProvider] = None

        if use_ai:
            if provider is not None:
                resolved_provider = provider
            else:
                try:
                    from .providers.factory import create_provider
                    resolved_provider = create_provider(
                        provider_name=provider_name,
                        api_key=api_key,
                        model=model,
                        **provider_kwargs,
                    )
                except Exception as exc:
                    print(f"Warning: Could not initialise AI provider: {exc}")
                    print("   Running in deterministic-only mode.")
                    resolved_provider = None

        self._provider = resolved_provider
        self._seed = seed
        self._verbose = verbose

        # ── Core generation stack ────────────────────────────────────────
        self.ai_engine = AIEngine(provider=resolved_provider, use_cache=use_cache)
        self.generator = BasicGenerator(
            locale=locale,
            ai_engine=self.ai_engine,
            seed=seed,
            verbose=verbose,
        )
        self.batch_engine = SmartBatchEngine(
            generator=self.generator, ai_engine=self.ai_engine
        )

        # ── Security layer ───────────────────────────────────────────────
        self.coordinator = ForgeCoordinator(
            allow_pii=allow_pii,
            interactive=interactive,
        ) if is_enabled("FORGE_PERMISSIONS") else None

        # ── Memory / context layer ───────────────────────────────────────
        self.memory = ForgeMemory(base_dir=memory_dir)

        # ── Session state + compression ──────────────────────────────────
        self._session = ForgeSessionState()
        self._compression = CompressionPipeline()

        # ── ForgeDream (feature-flagged) ─────────────────────────────────
        self._dream: Optional[ForgeDream] = (
            ForgeDream(memory_dir=self.memory._root)
            if is_enabled("FORGE_DREAM")
            else None
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def use_ai(self) -> bool:
        """True when an AI provider is active."""
        return self._provider is not None

    @property
    def provider_name(self) -> Optional[str]:
        return self._provider.model_name if self._provider else None

    @property
    def flags(self) -> Dict[str, bool]:
        """Snapshot of all feature flag values."""
        return flag_summary()

    # ------------------------------------------------------------------
    # Public generation API
    # ------------------------------------------------------------------

    def create(
        self,
        model: Type[T],
        count: int = 1,
        context: str = None,
        **overrides,
    ) -> Any:
        """
        Generate *count* instances one-by-one.
        Runs a permission check first (safe → auto, sensitive/dangerous → gate).
        Returns a single instance when count=1, otherwise a list.
        """
        self._check_permission(model, count)

        results: List[T] = []
        domain_rules = self.memory.get_rules_for_prompt(model_name=model.__name__)

        for i in range(count):
            if count > 1 and not self._verbose:
                print(f"   ...generating {i + 1}/{count}...")
            if self._verbose and count > 1:
                print(f"\n  --- record {i + 1}/{count} ---")
            item = self.generator.generate(model, context=context, **overrides)
            self._register(model, item)
            results.append(item)

        self._post_generation(model, count, list(model.model_fields.keys()))
        _ = domain_rules   # rules are read; future: pass into generator
        return results[0] if count == 1 else results

    def create_batch(
        self,
        model: Type[T],
        count: int,
        context: str = None,
        **overrides,
    ) -> List[T]:
        """
        Generate *count* instances efficiently (O(m) API calls, not O(n×m)).

        When AI is active and no overrides are specified, SmartBatchEngine
        batches all semantic fields across all records into one call per field.
        Falls back to loop-based create() when overrides are specified.
        """
        self._check_permission(model, count)

        if not self.use_ai or overrides:
            return self.create(model, count=count, context=context, **overrides)

        print(f"⚡ Smart-Batching {count} × '{model.__name__}'...", flush=True)
        try:
            items = self.batch_engine.generate_many(model, count=count, context=context)
            for item in items:
                self._register(model, item)
            self._post_generation(model, count, list(model.model_fields.keys()))
            return items
        except Exception as exc:
            print(f"⚠️  Batch error: {exc}. Falling back to loop.")
            return self.create(model, count=count, context=context, **overrides)

    def create_large(
        self,
        model: Type[T],
        count: int,
        context: str = None,
        seed_ratio: float = 0.01,
    ) -> "ForgeDataset[T]":
        """
        Efficient generation for very large datasets (10k+ records).

        Uses Seed + Interpolation: generate only (count × seed_ratio) unique
        AI values, then tile deterministically.  Wraps the result in a
        ForgeDataset which auto-spills to disk when > 50 KB.
        """
        self._check_permission(model, count)

        print(
            f"🌊 Large-batch: {count} × '{model.__name__}' "
            f"(seed_ratio={seed_ratio:.0%})...",
            flush=True,
        )
        items = self.batch_engine.generate_many_with_seeds(
            model, count=count, context=context, seed_ratio=seed_ratio
        )
        for item in items:
            self._register(model, item)
        self._post_generation(model, count, list(model.model_fields.keys()))

        dataset = ForgeDataset(items)
        if dataset.is_spilled:
            print(dataset.preview())
        return dataset

    def create_stream(
        self,
        model: Type[T],
        count: int,
        filename: str,
        context: str = None,
        **overrides,
    ) -> Generator[T, None, None]:
        """
        Lazy evaluation: generate and write to disk one record at a time.
        Prevents memory exhaustion for huge datasets.
        Supports .json, .csv, .sql output formats.
        """
        self._check_permission(model, count)

        streamer = DataStreamer(filename)
        streamer.start()
        print(f"🌊 Streaming {count} items to {filename}...")

        for _ in range(count):
            item = self.generator.generate(model, context=context, **overrides)
            streamer.write(item)
            self._register(model, item)
            yield item

        streamer.close()
        self._post_generation(model, count, list(model.model_fields.keys()))
        print(f"✅ Stream complete → {filename}")

    def swarm(
        self,
        models: List[Type[BaseModel]],
        counts: Optional[List[int]] = None,
        contexts: Optional[List[Optional[str]]] = None,
        max_workers: int = 4,
    ) -> Dict[str, List[Any]]:
        """
        Generate multiple models in parallel, sharing the AI cache.

        The first model warms the cache; subsequent models inherit it
        for ~90% cost reduction per additional model.

        Parameters
        ----------
        models      : list of Pydantic model classes
        counts      : records per model (defaults to 10 each)
        contexts    : optional context string per model
        max_workers : thread-pool size for the parallel phase

        Returns
        -------
        dict mapping model_name → list of generated instances
        """
        if not is_enabled("FORGE_SWARMS"):
            raise RuntimeError(
                "DataSwarms are disabled. Set FORGE_FLAG_SWARMS=1 to enable."
            )
        swarm = DataSwarm(forge=self, max_workers=max_workers)
        return swarm.run(models=models, counts=counts, contexts=contexts)

    def dream(
        self,
        models: Optional[List[Type[BaseModel]]] = None,
        force: bool = False,
    ) -> "ForgeDream":
        """
        Run ForgeDream 4-phase coverage consolidation.

        Analyses coverage gaps, merges contradictory rules, and trims the
        memory index.  Saves a coverage_gaps.json report to the .forge/ dir.

        Requires FORGE_DREAM feature flag (FORGE_FLAG_DREAM=1) unless force=True.

        Returns the DreamReport.
        """
        if not is_enabled("FORGE_DREAM") and not force:
            raise RuntimeError(
                "ForgeDream is feature-flagged off. "
                "Set FORGE_FLAG_DREAM=1 or pass force=True."
            )
        if self._dream is None:
            self._dream = ForgeDream(memory_dir=self.memory._root)

        return self._dream.run(models=models, force=force)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return record counts per registered model, plus session state."""
        registry_stats = {k: len(v) for k, v in self.generator.registry.items()}
        return {
            "registry": registry_stats,
            "session_tokens": self._session.token_estimate,
            "memory": self.memory.stats(),
            "flags": {k: v for k, v in self.flags.items() if v},  # only enabled
        }

    def clear_registry(self) -> None:
        """Reset FK registry and ID counters (useful between independent test scenarios)."""
        self.generator.registry.clear()
        self.generator._id_counters.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_permission(self, model: Type, count: int) -> None:
        """Run permission gate when FORGE_PERMISSIONS is enabled."""
        if self.coordinator is None:
            return
        approved = self.coordinator.check_and_approve(model, count)
        if not approved:
            sensitivity = FieldPermissionChecker.classify_model(model).value
            raise PermissionError(
                f"Generation of '{model.__name__}' ({sensitivity}) was denied by ForgeCoordinator."
            )

    def _register(self, model: Type, item: Any) -> None:
        key = model.__name__.lower()
        self.generator.registry.setdefault(key, []).append(item)

    def _post_generation(
        self, model: Type, count: int, fields: List[str]
    ) -> None:
        """Update session state and trigger compression if near budget."""
        self._session.add_generation(model.__name__, count, fields)
        layer = self._compression.maybe_compact(self._session)
        if layer:
            print(f"   [compression: {layer} layer ran]")

        # ForgeDream session counter
        if self._dream is not None:
            self._dream.record_session()


# ---------------------------------------------------------------------------
# Package-level convenience instance (auto-detects provider from env vars)
# ---------------------------------------------------------------------------
forge = Forge()
