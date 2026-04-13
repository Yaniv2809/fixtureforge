# CI vs Dev Mode

FixtureForge has two modes of operation designed for different stages of the development lifecycle.

---

## Dev Mode (default)

```python
forge = Forge()
# Auto-detects provider from environment variables
```

- Uses AI for semantic fields
- Realistic, context-aware output
- Slightly slower (AI latency ~1-2s per batch)
- Ideal for: writing new tests, exploring edge cases, seeding dev databases

---

## CI Mode

```python
forge = Forge(use_ai=False, seed=42)
```

- Zero network calls
- Faker + structural generators only
- Same seed = identical output on every machine, every run
- Ideal for: test pipelines, snapshot tests, reproducible bugs

!!! tip "Use seed= in CI"
    Set `seed=` from an environment variable so you can override it locally
    without changing code:
    ```python
    import os
    forge = Forge(use_ai=False, seed=int(os.getenv("FORGE_SEED", "42")))
    ```

---

## Seed Determinism

The `seed=` parameter controls:

1. **Faker** — `faker.seed_instance(seed)` (instance-level, no global state pollution)
2. **Random** — `random.Random(seed)` per Forge instance (fully isolated)

Two `Forge(seed=42)` instances produce identical data without interfering with each other.

```python
forge_a = Forge(use_ai=False, seed=42)
forge_b = Forge(use_ai=False, seed=42)

users_a = forge_a.create_batch(User, count=5)
users_b = forge_b.create_batch(User, count=5)

assert users_a == users_b  # always True
```

---

## Large Datasets

For very large datasets where AI cost would be prohibitive:

```python
# seed_ratio=0.01 means AI generates 1% of records,
# the rest are interpolated deterministically
forge.create_large(Order, count=100_000, seed_ratio=0.01)
# Cost: ~1,000 AI records. Delivered: 100,000 records.
```

---

## Streaming Mode

For datasets too large to hold in memory:

```python
for record in forge.create_stream(User, count=1_000_000, filename="users.json"):
    pass  # process one record at a time — never loads all into RAM
```

Supports `.json`, `.csv`, `.sql` output formats.
