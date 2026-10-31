---
name: fixtureforge
description: Generate deterministic, AI-enriched Pydantic test fixtures — seed-reproducible in CI, context-aware in dev — with automatic FK wiring and a one-line pytest plugin.
---

## What it is

FixtureForge generates test data for Pydantic `BaseModel` subclasses.
It behaves differently in two modes from the **same code**:

- **Dev mode** — calls an LLM for realistic, context-aware values on semantic
  fields (`bio`, `description`, `review`, `message`).
- **CI mode** (`use_ai=False, seed=42`) — pure Faker + sequential counters,
  zero network calls, 100% reproducible output.

Field routing is automatic. You do not wire generators by field name.

| Tier | Fields | Generator |
|------|--------|-----------|
| Structural | `id`, `*_id` | Counter + FK registry |
| Standard | `name`, `email`, `phone`, `address` | Faker |
| Semantic | `bio`, `description`, `review`, `message` | LLM (batched) |
| Computed | `@computed_field` | Pydantic |

100 users with 2 semantic fields = **2 API calls** (batched), not 200.

## When to use it

Use FixtureForge when:
- Models are Pydantic `BaseModel` subclasses.
- Tests must pass identically in CI and locally (seed-deterministic).
- Models have FK relationships (`order.user_id` → `user.id`).
- Semantic / free-text fields need realistic content, not Lorem Ipsum.

Do NOT use for:
- Plain dicts, dataclasses, or non-Pydantic structures.
- One-off single values that don't justify a model definition.

## Install & setup

```bash
pip install fixtureforge                    # Faker only, no AI required
pip install "fixtureforge[anthropic]"       # + Claude
pip install "fixtureforge[openai]"          # + GPT
pip install "fixtureforge[gemini]"          # + Gemini
pip install "fixtureforge[groq]"            # + Groq (free tier)
pip install "fixtureforge[all]"             # all providers
```

Requirements: Python 3.11+, pydantic ≥ 2.5, faker ≥ 22.0

AI is activated automatically when a provider key is found in the environment:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # → Claude
export OPENAI_API_KEY=sk-...          # → GPT
export GOOGLE_API_KEY=...             # → Gemini
export GROQ_API_KEY=...               # → Groq
```

## Core workflow

```python
from fixtureforge import Forge
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    email: str
    bio: str

# Dev mode — auto-detects provider from env
forge = Forge()
users = forge.create_batch(User, count=50, context="SaaS platform users")

# CI mode — deterministic, zero network
forge = Forge(use_ai=False, seed=42)
users = forge.create_batch(User, count=500)

# Single instance
user = forge.create(User, context="VIP enterprise customer")
```

## Determinism in CI

Always use `use_ai=False, seed=42` (or `FORGE_SEED=42`) for CI:

```yaml
# .github/workflows/test.yml
- name: Run tests
  env:
    FORGE_SEED: 42
  run: pytest
```

Never commit an AI provider key. Never set `use_ai=True` in CI-facing code.

## Foreign keys — automatic

Generate the parent first; child FKs resolve automatically:

```python
customers = forge.create_batch(Customer, count=10)
orders    = forge.create_batch(Order, count=100)
# every order.customer_id is a valid customer.id — no manual wiring
```

## pytest plugin — preferred integration

```python
# conftest.py
from fixtureforge.pytest_plugin import forge_fixture, forge_swarm_fixture
from myapp.models import User, Order

forge_fixture(User,  count=10, seed=42)           # → fixture "users"
forge_fixture(Order, count=50, seed=42)           # → fixture "orders"
forge_fixture(User,  count=1,  seed=42, name="admin_user")  # → "admin_user" (singular)
forge_swarm_fixture([User, Order], counts=[5, 20], seed=42) # → "swarm_data"
```

```python
# test_users.py
def test_signup(users):           # 10 User instances, injected
    assert all("@" in u.email for u in users)

def test_swarm(swarm_data):
    assert len(swarm_data["User"]) == 5
    assert len(swarm_data["Order"]) == 20
```

The `forge` fixture is auto-available in every test (zero config):

```python
def test_custom(forge):
    vip = forge.create(User, context="VIP enterprise customer")
    assert vip.name
```

`forge_fixture` parameters: `model`, `count`, `seed`, `context`, `use_ai`,
`scope` ("function"|"class"|"module"|"session"), `name`, `**overrides`.

## Multi-model swarms

```python
results = forge.swarm(
    models=[User, Order, Product],
    counts=[10, 50, 100],
    contexts=["SaaS users", "E-commerce orders", None],
)
# {"User": [...], "Order": [...], "Product": [...]}
```

First model warms the AI cache; subsequent models share it (~90% cheaper).

## Domain rules

```python
forge.memory.add_rule("financial", "Users under 18 get restricted account type")
forge.memory.add_rule("orders", "Max 3 active loans per customer at any time")
# Rules inject into AI prompts automatically on every generation call
```

## Export

```python
from fixtureforge.core.exporter import DataExporter

DataExporter.export(users, "users.json")   # format inferred from extension
DataExporter.export(users, "users.csv")
DataExporter.export(users, "users.sql")
```

## Common mistakes — never do these

- **Never** add custom generator logic for `id`, `name`, `email`, `bio`, etc.
  FixtureForge routes them automatically.
- **Never** set `use_ai=True` in CI. Use `FORGE_SEED=42` env var instead.
- **Never** wire FK relationships manually. Generate the parent model first.
- **Never** guess provider names. Only: `"anthropic"`, `"openai"`, `"gemini"`,
  `"groq"`, `"ollama"`.
- **Never** call `ForgeEnterprise` unless the repo already depends on the
  Enterprise Edition — it is a separate, access-gated product.
- **Never** invent `Forge()` kwargs not documented here or in the README.
- **Never** redefine the `forge` fixture in conftest.py — it is auto-provided.

## Links

- Repo: https://github.com/Yaniv2809/fixtureforge
- Docs: https://yaniv2809.github.io/fixtureforge/
- PyPI: https://pypi.org/project/fixtureforge/
- Issues: https://github.com/Yaniv2809/fixtureforge/issues
