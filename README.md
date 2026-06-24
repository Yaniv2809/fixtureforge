<p align="center">
  <img src="fixtureforge-logo.png" alt="FixtureForge" width="360"/>
</p>

<h1 align="center">FixtureForge</h1>
<p align="center"><b>Agentic test data harness for Python — deterministic in CI, AI-powered in dev.</b></p>

<p align="center">
  <a href="https://pypi.org/project/fixtureforge/"><img src="https://img.shields.io/pypi/v/fixtureforge.svg" alt="PyPI version"/></a>
  <a href="https://pypi.org/project/fixtureforge/"><img src="https://img.shields.io/pypi/dm/fixtureforge.svg" alt="Downloads"/></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"/></a>
  <a href="https://pypi.org/project/fixtureforge/"><img src="https://img.shields.io/badge/pytest-plugin-orange.svg" alt="pytest plugin"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"/></a>
</p>

---

## The problem with test data today

```python
# ❌ Everyone does this. It's brittle and misses real-world edge cases.
user = User(name="Test User", email="test@test.com", bio="Lorem ipsum...")

# ❌ factory_boy is great — but it's static. No surprises, no edge cases.
UserFactory.create(role="admin")

# ❌ Writing 500 of them by hand? Not happening.
```

Hardcoded fixtures rot. AI-generated fixtures are unpredictable in CI.  
**FixtureForge solves both** — same codebase, two behaviors:

```
Dev mode  →  AI generates rich, realistic, edge-case-aware fixtures
CI mode   →  same fixtures, frozen with seed=42, 100% reproducible
```

---

## Quickstart

```bash
pip install fixtureforge
```

```python
from fixtureforge import Forge
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    email: str
    bio: str

forge = Forge()                    # auto-detects AI provider from env vars
users = forge.create_batch(User, count=50, context="SaaS platform users")
```

FixtureForge routes each field to the cheapest generator automatically:

- **`id`** → sequential counter *(free)*
- **`name`, `email`** → Faker *(free)*
- **`bio`** → single batched AI call for all 50 records *(1 API call, not 50)*

**No AI key? No problem.** Pure Faker mode works out of the box:

```python
forge = Forge(use_ai=False, seed=42)   # deterministic, zero network, CI-safe
users = forge.create_batch(User, count=500)
```

---

## Intelligent Field Routing

Every field is classified into a tier. Only semantic fields hit the AI:

| Tier | Fields | Generator | Cost |
|------|--------|-----------|------|
| **Structural** | `id`, `user_id`, `order_id` | Counters + FK registry | Free |
| **Standard** | `name`, `email`, `phone`, `address` | Faker | Free |
| **Computed** | `@computed_field` | Pydantic | Free |
| **Semantic** | `bio`, `description`, `review`, `message` | LLM (batched) | API tokens |

100 users with 2 semantic fields = **2 API calls**, not 200.

---

## CI/CD — zero config changes between environments

```yaml
# .github/workflows/test.yml
- name: Run tests
  env:
    FORGE_SEED: 42        # identical output every run
    # No AI key needed — FixtureForge auto-detects and falls back to Faker
  run: pytest
```

In dev, export any provider key and AI kicks in automatically:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # → Claude
export OPENAI_API_KEY=sk-...          # → GPT
export GOOGLE_API_KEY=...             # → Gemini
export GROQ_API_KEY=...               # → Groq (fast + cheap)
```

---

## Foreign Key Relationships — automatic

```python
# Step 1: generate customers
customers = forge.create_batch(Customer, count=10)

# Step 2: Order.customer_id auto-resolves to a real customer.id
orders = forge.create_batch(Order, count=100)
# → every order.customer_id is valid. No manual wiring.
```

---

## DataSwarms — bulk generation, shared cache

Generate multiple models in parallel. The first model warms the AI cache;  
every subsequent model inherits it — **~90% cheaper per additional model**.

```python
results = forge.swarm(
    models=[User, Order, Product, Payment],
    counts=[10,   50,    100,     30],
    contexts=["SaaS users", "E-commerce orders", None, None],
)
# {
#   "User":    [...10 users...],
#   "Order":   [...50 orders...],
#   "Product": [...100 products...],
#   "Payment": [...30 payments...],
# }
```

5 models ≈ cost of 1.5 models.

---

## ForgeMemory — fixtures that remember your domain

```python
forge.memory.add_rule("financial", "Users under 18 get restricted account type")
forge.memory.add_rule("user", "Israeli phone numbers use format 05x-xxx-xxxx")
forge.memory.add_rule("orders", "Max 3 active loans per customer at any time")

# Rules inject into AI prompts automatically on every generation call
users = forge.create_batch(User, count=50, context="Israeli SaaS platform")
```

Rules survive across sessions. Update a rule — next call respects it immediately.  
**Skeptical Memory** validates stored rules against the live schema before every call.

---

## pytest plugin — one line per fixture

```python
# conftest.py
from fixtureforge.pytest_plugin import forge_fixture, forge_swarm_fixture
from pydantic import BaseModel

class User(BaseModel):
    id: int; name: str; email: str

forge_fixture(User, count=10, seed=42)           # → fixture: "users"
forge_swarm_fixture([User, Order], counts=[5, 20], seed=42)  # → "swarm_data"
```

```python
# test_users.py
def test_signup(users):
    for user in users:
        assert "@" in user.email

def test_full_flow(swarm_data):
    users  = swarm_data["User"]
    orders = swarm_data["Order"]
```

The `forge` fixture is auto-available in every test with zero config.

---

## Multi-provider support

```python
# Be explicit
forge = Forge(provider_name="anthropic", model="claude-haiku-4-5-20251001")
forge = Forge(provider_name="openai",    model="gpt-4o-mini")
forge = Forge(provider_name="gemini",    model="gemini-2.0-flash")
forge = Forge(provider_name="groq",      model="llama-3.3-70b-versatile")
forge = Forge(provider_name="ollama",    model="llama3.2")   # local, zero cost
forge = Forge(use_ai=False)                                   # pure Faker
```

---

## Large datasets — constant AI cost regardless of count

```python
# Seed + Interpolation: generates ~1 000 unique AI values, tiles to 100 000
dataset = forge.create_large(Order, count=100_000, seed_ratio=0.01)

# Streaming — one record at a time, never loads all into memory
for user in forge.create_stream(User, count=1_000_000, filename="users.json"):
    process(user)
```

---

## Export

```python
from fixtureforge.core.exporter import DataExporter

users = forge.create_batch(User, count=100)
DataExporter.to_json(users, "users.json")
DataExporter.to_csv(users,  "users.csv")
DataExporter.to_sql(users,  "users.sql", table_name="users")
```

---

## FixtureForge vs alternatives

|  | FixtureForge | factory\_boy | Faker | hypothesis |
|--|:--:|:--:|:--:|:--:|
| AI-powered context | ✅ | ❌ | ❌ | ❌ |
| Deterministic (seed=) | ✅ | ✅ | ✅ | ✅ |
| FK relationships | **Auto** | Manual | ❌ | ❌ |
| Batched AI calls | ✅ | ❌ | ❌ | ❌ |
| Coverage gap analysis | ✅ | ❌ | ❌ | Partial |
| Large datasets (100k+) | ✅ | Manual | Manual | ❌ |
| pytest plugin | ✅ | ❌ | ❌ | ❌ |
| Multi-LLM support | ✅ | ❌ | ❌ | ❌ |
| Permission gates | ✅ | ❌ | ❌ | ❌ |
| CI-safe (zero network) | ✅ | ✅ | ✅ | ✅ |

FixtureForge is not a replacement for Faker — it uses Faker internally for standard fields.  
It adds the layer between *"I need realistic data"* and *"I need it to feel like production."*

---

## Installation

```bash
# Core (deterministic mode, no AI)
pip install fixtureforge

# With your preferred provider
pip install "fixtureforge[anthropic]"   # Claude
pip install "fixtureforge[openai]"      # GPT
pip install "fixtureforge[gemini]"      # Gemini
pip install "fixtureforge[all]"         # All providers
```

**Requirements:** Python 3.11+ · pydantic ≥ 2.5 · faker ≥ 22.0

---

## Enterprise Edition

For teams with compliance requirements — GDPR, SOC2, HIPAA, multi-tenant SaaS:

| | Community | Enterprise |
|--|:--:|:--:|
| AI generation + Faker | ✅ | ✅ |
| pytest plugin | ✅ | ✅ |
| Deterministic seeding | ✅ | ✅ |
| **Cryptographic Provenance Envelope** | ❌ | ✅ |
| **PII Airgap — fail-closed scanner** | ❌ | ✅ |
| **Contextual Tenant Enclaves** | ❌ | ✅ |
| **Cross-tenant FK violation detection** | ❌ | ✅ |
| **Presidio / custom scanner support** | ❌ | ✅ |

```python
from fixtureforge.enterprise import ForgeEnterprise

forge = ForgeEnterprise(use_ai=False)
users = forge.create_batch(User, count=10)

users[0].model_dump()
# { "id": 1, "name": "...", "bio": "...",
#   "forge_metadata": {
#     "forge_id": "abc-123",
#     "provenance_hash": "sha256:029773ed...",  ← immutable audit stamp
#     "tenant_id": "tenant-acme",
#     "source": "faker",
#     ...
#   }
# }

with forge.isolate_tenant("tenant-acme"):
    acme_users = forge.create_batch(User, count=5)
    # FK references from tenant-acme can NEVER resolve to tenant-xyz records
```

**Access:** [yaniv2809@gmail.com](mailto:yaniv2809@gmail.com)

---

## Project status

| Component | Status |
|-----------|--------|
| Core (`Forge`, `create_batch`) | ✅ Stable |
| DataSwarms | ✅ Stable |
| ForgeMemory | ✅ Stable |
| pytest plugin | ✅ v2.2.0 |
| Anthropic / OpenAI / Gemini / Groq / Ollama | ✅ |
| `assert_semantic_match` | ✅ v2.2.0 |
| `SmartFailureAnalyzer` | ✅ v2.2.0 |
| Enterprise Edition | ✅ (access by request) |
| ForgeDream (coverage analysis) | 🔜 Feature-flagged |
| Async support | 🔜 Planned |

---

## Links

- **Docs**: https://yaniv2809.github.io/fixtureforge/
- **PyPI**: https://pypi.org/project/fixtureforge/
- **Repository**: https://github.com/Yaniv2809/fixtureforge
- **Issues**: https://github.com/Yaniv2809/fixtureforge/issues
- **Discussion**: https://github.com/Yaniv2809/fixtureforge/discussions/1

---

## Contributing

Issues and PRs welcome.

```bash
git clone https://github.com/Yaniv2809/fixtureforge
cd fixtureforge
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest tests/
```

---

## License

MIT © [Yaniv2809](https://github.com/Yaniv2809)

---

<p align="center">
  <b>If FixtureForge saved you time, give it a ⭐ — it helps others find it.</b>
</p>
