"""
SmartBatchEngine — generate N records with the minimum number of API calls.

The naive approach calls the AI once per semantic field per record:
  100 records × 2 semantic fields = 200 API calls  ← slow & expensive

SmartBatchEngine batches ALL records for each semantic field into ONE call:
  100 records × 2 semantic fields = 2 API calls  ← 100× faster & cheaper

Algorithm:
  1. Classify every field with IntelligentRouter.
  2. For each SEMANTIC field, call ai_engine.generate_semantic_batch(count=N).
     This returns N values in a single LLM request.
  3. Generate STRUCTURAL and STANDARD fields deterministically (zero API cost).
  4. Skip COMPUTED fields (Pydantic resolves them automatically).
  5. Assemble N instances from the pools.
"""
from typing import Any, Dict, List, Optional, Type

from ..ai.engine import AIEngine
from .generator import BasicGenerator, _SKIP
from .parser import ModelParser
from .router import FieldTier, IntelligentRouter


class SmartBatchEngine:
    def __init__(self, generator: BasicGenerator, ai_engine: AIEngine):
        self.generator = generator
        self.ai_engine = ai_engine
        self.router = IntelligentRouter()

    @property
    def verbose(self) -> bool:
        return self.generator.verbose

    def generate_many(
        self,
        model: Type,
        count: int,
        context: str = None,
    ) -> List[Any]:
        """
        Generate `count` instances of `model`.
        Semantic fields are batched into one API call per field.
        """
        fields = ModelParser.parse(model)

        # Separate fields by tier
        structural = [f for f in fields if self.router.classify(f) == FieldTier.STRUCTURAL]
        standard   = [f for f in fields if self.router.classify(f) == FieldTier.STANDARD]
        semantic   = [f for f in fields if self.router.classify(f) == FieldTier.SEMANTIC]
        # COMPUTED fields are intentionally omitted — Pydantic handles them.

        # --- Step 1: batch-generate all semantic fields upfront ---
        # Each call returns a list[str] of length `count`.
        semantic_pools: Dict[str, List[str]] = {}
        for field in semantic:
            print(f"   [ai] Generating {count} values for '{field.name}'...")
            semantic_pools[field.name] = self.ai_engine.generate_semantic_batch(
                field_name=field.name,
                context=context or "",
                count=count,
            )

        if self.verbose and structural:
            print(f"   [structural] fields: {[f.name for f in structural]}")
        if self.verbose and standard:
            print(f"   [faker]      fields: {[f.name for f in standard]}")

        # --- Step 2: assemble N instances ---
        results: List[Any] = []
        for i in range(count):
            data: Dict[str, Any] = {}

            for field in structural:
                val = self.generator._generate_structural(field)
                if val is not _SKIP:
                    data[field.name] = val

            for field in standard:
                val = self.generator._generate_standard(field)
                if val is not _SKIP:
                    data[field.name] = val

            for field in semantic:
                pool = semantic_pools.get(field.name, [])
                data[field.name] = pool[i] if i < len(pool) else f"[AI Placeholder for {field.name}]"

            results.append(model(**data))

        return results

    def generate_many_with_seeds(
        self,
        model: Type,
        count: int,
        context: str = None,
        seed_ratio: float = 0.01,
    ) -> List[Any]:
        """
        Seed + Interpolation strategy for very large datasets (>10k records).

        Instead of generating `count` AI values, generate only
        max(50, count * seed_ratio) unique seeds, then tile them
        deterministically across `count` records.

        This keeps costs near-constant regardless of `count` while
        preserving statistical diversity.
        """
        import random  # noqa: PLC0415

        seed_count = max(50, int(count * seed_ratio))

        # Generate the seed pool
        seed_instances = self.generate_many(model, count=seed_count, context=context)

        if seed_count >= count:
            return seed_instances[:count]

        # Tile and shuffle seeds to fill `count` records
        tiled: List[Any] = []
        while len(tiled) < count:
            batch = seed_instances.copy()
            random.shuffle(batch)
            tiled.extend(batch)

        return tiled[:count]
