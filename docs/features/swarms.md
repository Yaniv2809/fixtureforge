# DataSwarms

DataSwarms generate multiple model types **in parallel** with a shared AI response cache.

---

## The Problem It Solves

Generating 5 models sequentially means 5 separate AI warm-up cycles. DataSwarms run them concurrently and share the cache — so each additional model costs ~10% of the first.

**5 models ≈ cost of 1.5 models.**

---

## Basic Usage

```python
results = forge.swarm(
    models=[User, Order, Product, Payment, Review],
    counts=[10,   50,    100,     30,      20],
    contexts=["SaaS users", "E-commerce orders", None, None, "Post-purchase reviews"],
)

# Returns a dict keyed by model name:
print(results["User"])     # list of 10 User instances
print(results["Order"])    # list of 50 Order instances
print(results["Product"])  # list of 100 Product instances
```

---

## How It Works

1. **First model runs synchronously** — warms the AI response cache
2. **Remaining models run in `ThreadPoolExecutor`** — parallel, all hit the warm cache
3. **Shared `Forge` instance** — one AIEngine, one ResponseCache, shared across all threads

```
Model 1 (User)     ----[AI call]-----> cache warm
Model 2 (Order)              ---[cache hit]-->
Model 3 (Product)            ---[cache hit]-->
Model 4 (Payment)            ---[cache hit]-->
                  |<-- total time -->|
```

---

## pytest Integration

```python
# conftest.py
from fixtureforge import forge_swarm_fixture
from myapp.models import User, Order

forge_swarm_fixture(
    name="full_dataset",
    models=[User, Order],
    counts=[10, 50],
)
```

```python
def test_data_integrity(full_dataset):
    users = full_dataset["User"]
    orders = full_dataset["Order"]
    assert all(o.user_id in {u.id for u in users} for o in orders)
```

---

## Seed Support

```python
results = forge.swarm(
    models=[User, Order],
    counts=[10, 50],
    seed=42,   # deterministic across all models
)
```
