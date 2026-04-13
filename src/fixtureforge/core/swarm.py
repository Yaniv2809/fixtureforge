"""
DataSwarms — parallel multi-model generation with shared cache inheritance.

Inspired by multi-agent cache sharing: the first model in a swarm pays the
full cache-warm cost; every subsequent model inherits the warm cache for
~90% cost reduction (cached tokens are nearly free).

The first agent always runs synchronously to build the shared cache.
Remaining agents run in a ThreadPoolExecutor, all sharing the same
AIEngine (and thus the same ResponseCache) as the parent Forge.

Usage:
    from fixtureforge import Forge

    forge = Forge()
    results = forge.swarm(
        [User, Order, Product, Payment],
        counts=[10, 50, 100, 30],
        contexts=["SaaS users", "E-commerce orders", None, None],
    )
    # returns {"User": [...], "Order": [...], "Product": [...], "Payment": [...]}
"""
from __future__ import annotations

import concurrent.futures
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel

if TYPE_CHECKING:
    from ..__init__ import Forge  # avoid circular at runtime


class DataSwarm:
    """
    Parallel generation coordinator.

    All agents in a swarm share *the same* ``Forge`` instance, meaning they
    share the same ``AIEngine`` and ``ResponseCache``.  The first model warms
    the cache; subsequent models benefit from it automatically.

    Parameters
    ----------
    forge : Forge
        The parent Forge instance whose engine and cache are shared.
    max_workers : int
        Thread-pool size for the parallel phase (default 4).
    """

    def __init__(self, forge: "Forge", max_workers: int = 4) -> None:
        self._forge = forge
        self._max_workers = max_workers

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(
        self,
        models: List[Type[BaseModel]],
        counts: Optional[List[int]] = None,
        contexts: Optional[List[Optional[str]]] = None,
    ) -> Dict[str, List[Any]]:
        """
        Generate *models* in parallel, cache-sharing across all agents.

        Parameters
        ----------
        models   : list of Pydantic model classes
        counts   : records per model (defaults to 10 each)
        contexts : optional context strings per model

        Returns
        -------
        dict mapping model_name → list of generated instances
        """
        if not models:
            return {}

        counts   = counts   or [10]   * len(models)
        contexts = contexts or [None] * len(models)

        if len(counts) != len(models):
            raise ValueError(f"counts length {len(counts)} ≠ models length {len(models)}")
        if len(contexts) != len(models):
            raise ValueError(f"contexts length {len(contexts)} ≠ models length {len(models)}")

        tasks: List[Tuple[Type[BaseModel], int, Optional[str]]] = list(
            zip(models, counts, contexts)
        )
        results: Dict[str, List[Any]] = {}

        # ── Phase 1: warm the cache with the first model ────────────────
        first_model, first_count, first_ctx = tasks[0]
        print(
            f"\n🐝 Swarm start — {len(models)} models, "
            f"{sum(counts)} total records"
        )
        print(f"   [0/{len(models)}] Warming cache: {first_count} × {first_model.__name__}...")
        results[first_model.__name__] = self._forge.create_batch(
            first_model, count=first_count, context=first_ctx
        )

        if len(tasks) == 1:
            print(f"✅ Swarm complete — {len(results[first_model.__name__])} records")
            return results

        # ── Phase 2: remaining models in parallel (cache is now warm) ───
        remaining = tasks[1:]
        print(
            f"   Launching {len(remaining)} parallel agents "
            f"(cache warm — ~90% cheaper per agent)..."
        )

        def _worker(
            idx: int,
            task: Tuple[Type[BaseModel], int, Optional[str]],
        ) -> Tuple[str, List[Any]]:
            model, count, ctx = task
            print(f"   [{idx}/{len(models)}] {model.__name__}: {count} records")
            items = self._forge.create_batch(model, count=count, context=ctx)
            return model.__name__, items

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self._max_workers, len(remaining))
        ) as pool:
            futures = {
                pool.submit(_worker, i + 1, task): task
                for i, task in enumerate(remaining)
            }
            for future in concurrent.futures.as_completed(futures):
                name, items = future.result()
                results[name] = items

        total = sum(len(v) for v in results.values())
        print(
            f"✅ Swarm complete — {total} records across {len(models)} models\n"
        )
        return results
