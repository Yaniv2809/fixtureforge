<p align="center">
  <img src="fixtureforge-logo.png" alt="FixtureForge Logo" width="400"/>
</p>

# FixtureForge

**Agentic Test Data Harness for Python.**  
Generate realistic, context-aware fixtures — deterministic in CI, AI-powered in development.

[![PyPI version](https://img.shields.io/pypi/v/fixtureforge.svg)](https://pypi.org/project/fixtureforge/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

```python
# This is what most test data looks like:
user = User(name="Test User", email="test@test.com", bio="Lorem ipsum...")

# It doesn't catch real-world edge cases.
# It doesn't feel like production data.
# And writing 500 of them by hand? Not happening.
```

FixtureForge solves this in two modes:

```python
# CI mode — deterministic, zero AI, seed-controlled. Same seed = same data. Always.
forge = Forge(use_ai=False, seed=42)
users = forge.create_batch(User, count=500)

# Dev mode — AI-generated, context-aware, realistic
forge = Forge()
reviews = forge.create_batch(Review, count=50, context="angry holiday customers")
```

---

## Installation

```bash
pip install fixtureforge
```

With your preferred AI provider:

```bash
pip install "fixtureforge[anthropic]"   # Claude
pip install "fixtureforge[openai]"      # GPT
pip install "fixtureforge[gemini]"      # Google Gemini
pip install "fixtureforge[all]"         # All providers
```

---

## Quick Start

```python
from fixtureforge import Forge
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    email: str
    bio: str

forge = Forge()  # auto-detects provider from env vars
users = forge.create_batch(User, count=50, context="SaaS platform users")
```

That's it. FixtureForge:
- Assigns sequential IDs automatically
- Generates `name` and `email` with Faker (zero API cost)
- Sends only `bio` to the AI — in a single batch call for all 50 records

---

## Core Concepts

### Intelligent Field Routing

Every field is classified into a tier. Only semantic fields hit the AI:

| Tier | Fields | Generator | Cost |
|------|--------|-----------|------|
| **Structural** | `id`, `user_id`, `order_id` | Internal counters / FK registry | Free |
| **Standard** | `name`, `email`, `phone`, `address`, `date` | Faker | Free |
| **Computed** | `@computed_field` properties | Pydantic | Free |
| **Semantic** | `bio`, `description`, `review`, `message` | LLM (batched) | API tokens |

100 users with 2 semantic fields = **2 API calls**, not 200.

### CI Mode vs Dev Mode

```python
# CI — fully deterministic, no network, reproducible
forge = Forge(use_ai=False, seed=42)

# Dev — AI-powered, realistic context
forge = Forge(provider_name="anthropic", model="claude-haiku-4-5-20251001")

# Large datasets — seed+interpolation, constant cost regardless of count
forge.create_large(Order, count=100_000, seed_ratio=0.01)  # pays for ~1k, delivers 100k
```

### Verbose Mode

See exactly where each value comes from:

```python
forge = Forge(use_ai=False, seed=42, verbose=True)
user = forge.create(User)

# [structural] id    = 1
# [faker]      name  = 'Allison Hill'
# [faker]      email = 'donaldgarcia@example.net'
# [ai]         bio   = 'Passionate developer with 8 years...'
```

---

## Providers

FixtureForge auto-detects your provider from environment variables:

```bash
export ANTHROPIC_API_KEY=...   # → Claude (default: claude-haiku-4-5-20251001)
export OPENAI_API_KEY=...      # → GPT    (default: gpt-4o-mini)
export GOOGLE_API_KEY=...      # → Gemini (default: gemini-2.0-flash)
export GROQ_API_KEY=...        # → Groq   (default: llama-3.3-70b-versatile)
# No key? → Ollama (localhost:11434) → Deterministic-only
```

Or be explicit:

```python
forge = Forge(provider_name="anthropic", model="claude-sonnet-4-6")
forge = Forge(provider_name="ollama", model="llama3.2")
forge = Forge(use_ai=False)  # zero cost, zero network
```

---

## Foreign Key Relationships

Register parent records first — child FKs resolve automatically:

```python
# Step 1: generate customers
customers = forge.create_batch(Customer, count=10)

# Step 2: orders automatically reference real customer IDs
orders = forge.create_batch(Order, count=100)
# order.customer_id → always a valid customer.id
```

---

## DataSwarms — Parallel Multi-Model Generation

Generate multiple models in parallel with shared AI cache.  
The first model warms the cache; every subsequent model inherits it (~90% cheaper per model).

```python
results = forge.swarm(
    models=[User, Order, Product, Payment],
    counts=[10,   50,    100,     30],
    contexts=["SaaS users", "E-commerce orders", None, None],
)

# returns:
# {
#   "User":    [...10 users...],
#   "Order":   [...50 orders...],
#   "Product": [...100 products...],
#   "Payment": [...30 payments...],
# }
```

5 models ≈ cost of 1.5 models.

---

## Permission Gates

FixtureForge classifies models by data sensitivity and gates dangerous operations:

```python
class SafeUser(BaseModel):
    id: int
    name: str          # SAFE — auto-approved

class CustomerProfile(BaseModel):
    id: int
    ssn: str           # SENSITIVE — requires FORGE_ALLOW_PII=1
    salary: float      # SENSITIVE

class SecurityTest(BaseModel):
    id: int
    sql_injection: str # DANGEROUS — requires interactive confirmation
```

```python
# PII auto-approved
forge = Forge(allow_pii=True)

# CI/headless — dangerous ops silently rejected
forge = Forge(interactive=False)
```

Three levels: `safe` (auto) → `sensitive` (env gate) → `dangerous` (human prompt).

---

## Domain Rules — ForgeMemory

Persist business rules that survive across sessions.  
Rules are re-read on every generation call — update a rule, next call respects it immediately.

```python
forge.memory.add_rule("financial", "Users under 18 get restricted account type")
forge.memory.add_rule("user", "Israeli phone numbers use format 05x-xxx-xxxx")
forge.memory.add_rule("orders", "Max 3 active loans per customer at any time")

# Rules inject into AI prompts automatically
users = forge.create_batch(User, count=50, context="Israeli SaaS platform")
```

**Skeptical Memory** — rules are hints, not truth. FixtureForge validates stored rules against the live schema before every generation call.

**Progressive Forgetting** — field names and types are never stored (re-derivable from the model). Only business rules that exist nowhere else in the code are kept.

---

## ForgeDream — Coverage Analysis

Find gaps in your test-data coverage automatically:

```python
import os
os.environ["FORGE_FLAG_DREAM"] = "1"

report = forge.dream(models=[User, Order], force=True)
print(report.summary())

# ForgeDream Report - 2026-04-08
#   Coverage gaps found  : 3
#   Rule conflicts found : 0
#   Top gaps:
#     [User.age]   no_boundary : No boundary-value rules for numeric field 'age'
#     [User.email] no_invalid  : No invalid-data rules for well-known field 'email'
#     [Order.total] no_boundary: No boundary-value rules for numeric field 'total'
```

Four phases: **Orient** (read index) → **Gather** (find gaps) → **Consolidate** (merge rules) → **Prune** (trim to ≤200 lines).

Report saved as `.forge/coverage_gaps.json`.

---

## Streaming — Memory-Safe Large Datasets

```python
# Lazy evaluation — writes to disk one record at a time
for user in forge.create_stream(User, count=1_000_000, filename="users.json"):
    pass  # process one record, never loads all into memory
```

Supports `.json`, `.csv`, `.sql` output formats.

---

## Export

```python
from fixtureforge.core.exporter import DataExporter

users = forge.create_batch(User, count=100)
DataExporter.to_json(users, "users.json")
DataExporter.to_csv(users, "users.csv")
DataExporter.to_sql(users, "users.sql", table_name="users")
```

---

## Response Cache

AI responses are cached locally for 7 days. Identical requests cost nothing after the first call.

```python
forge = Forge(use_cache=True)   # default — saves to ~/.fixtureforge/cache/
forge = Forge(use_cache=False)  # disable caching
```

---

## Feature Flags

```python
from fixtureforge.config import is_enabled, flag_summary

flag_summary()
# {
#   'FORGE_SWARMS':      True,   # shipped
#   'FORGE_PERMISSIONS': True,   # shipped
#   'FORGE_COMPRESSION': True,   # shipped
#   'FORGE_MCP':         True,   # shipped
#   'FORGE_DREAM':       False,  # enable with FORGE_FLAG_DREAM=1
#   'FORGE_KAIROS':      False,  # coming in v2.x
#   'FORGE_ULTRAPLAN':   False,  # coming in v2.x
# }
```

Enable any staged feature with an env var:

```bash
FORGE_FLAG_DREAM=1 python run_tests.py
```

---

## Stats & Diagnostics

```python
forge.stats()
# {
#   "registry": {"user": 50, "order": 200},
#   "session_tokens": 1240,
#   "memory": {"topics": 3, "total_kb": 2.4},
#   "flags": {"FORGE_SWARMS": True, "FORGE_PERMISSIONS": True}
# }

forge.clear_registry()  # reset FK registry between independent test scenarios
```

---

## Architecture

```
FixtureForge v2.0
├── Config Layer        feature flags, env-var overrides
├── Security Layer      safe / sensitive / dangerous gates, mailbox pattern
├── Memory Layer        FORGE.md pointer index, on-demand topic files
├── Generation Layer    IntelligentRouter, SmartBatchEngine, DataSwarms
├── Compression Layer   Micro → Auto → Full (three-layer pipeline)
├── Export Layer        JSON / CSV / SQL / streaming
└── Background Layer    ForgeDream coverage analysis (feature-flagged)
```

**Provider-agnostic**: Claude, GPT, Gemini, Groq, Ollama, or no AI at all.  
**Pydantic v2 native**: full support for `@computed_field`, validators, and constrained types.  
**CI-safe**: `seed=` parameter guarantees identical output across runs.

---

## Comparison

| | FixtureForge | factory_boy | faker | hypothesis |
|---|---|---|---|---|
| AI-generated context | Yes | No | No | No |
| Deterministic (seed=) | Yes | Yes | Yes | Yes |
| FK relationships | Auto | Manual | No | No |
| Coverage analysis | Yes | No | No | Partial |
| CI-safe mode | Yes | Yes | Yes | Yes |
| Large datasets | Yes (100k+) | Manual | Manual | No |
| Permission gates | Yes | No | No | No |

FixtureForge is not a replacement for `faker` — it uses `faker` internally. It's not a replacement for `hypothesis` — it solves a different problem. It adds the layer between "I need realistic data" and "I need it to feel like production".

---

## Requirements

- Python 3.11+
- pydantic >= 2.5
- faker >= 22.0

AI providers are optional extras — the core works with zero dependencies beyond pydantic and faker.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Links

- **PyPI**: https://pypi.org/project/fixtureforge/
- **Repository**: https://github.com/Yaniv2809/fixtureforge
- **Issues**: https://github.com/Yaniv2809/fixtureforge/issues
