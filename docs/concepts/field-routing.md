# Intelligent Field Routing

The core of FixtureForge is the **IntelligentRouter** — it classifies every field in your model and directs it to the cheapest generator that can handle it.

## The Four Tiers

| Tier | Examples | Generator | API Cost |
|------|----------|-----------|----------|
| **Structural** | `id`, `user_id`, `order_id`, `created_at` | Internal counters / FK registry | Free |
| **Standard** | `name`, `email`, `phone`, `address`, `zip_code` | Faker | Free |
| **Computed** | `@computed_field` properties | Pydantic | Free |
| **Semantic** | `bio`, `description`, `review`, `message`, `notes` | LLM (batched) | API tokens |

---

## Batching

Semantic fields are never sent one at a time. FixtureForge batches all semantic field values for all records into a single prompt.

```
100 records x 2 semantic fields = 2 API calls (not 200)
```

The batch prompt asks the model to return a JSON array with all values at once. This reduces latency by ~95% compared to per-record generation.

---

## Classification Logic

Field classification uses a combination of:

1. **Type annotation** — `int` with name `id` or ending in `_id` → Structural
2. **Field name patterns** — `email`, `phone`, `address` → Standard (Faker)
3. **Semantic heuristics** — long `str` fields with no recognized name pattern → AI

You can influence routing with Pydantic field descriptions:

```python
from pydantic import BaseModel, Field

class Product(BaseModel):
    id: int
    name: str
    sku: str = Field(description="Stock keeping unit, format: ABC-12345")
    tagline: str  # -> AI (semantic)
```

---

## Cost Estimation

```python
forge = Forge()
report = forge.estimate_cost(User, count=1000)
print(report)

# Field routing estimate for User (count=1000):
#   id          -> structural  (free)
#   name        -> faker       (free)
#   email       -> faker       (free)
#   bio         -> ai          (~2 API calls)
#   Estimated total: ~2 batched API calls
```
