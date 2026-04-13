<div class="hero" markdown>
  <img src="assets/logo.png" alt="FixtureForge" />

  # FixtureForge

  **Agentic Test Data Harness for Python.**<br>
  Deterministic in CI. AI-powered in development.

  <div class="hero-badges" markdown>
  [![PyPI version](https://img.shields.io/pypi/v/fixtureforge.svg)](https://pypi.org/project/fixtureforge/)
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  </div>
</div>

---

## The Problem

```python
# This is what most test data looks like:
user = User(name="Test User", email="test@test.com", bio="Lorem ipsum...")

# It doesn't catch real-world edge cases.
# It doesn't feel like production data.
# Writing 500 of them by hand? Not happening.
```

FixtureForge solves this by generating realistic, context-aware test fixtures —
using AI when you need quality, Faker when you need speed, and a deterministic
seed when you need reproducibility in CI.

---

## Two-Line Setup

```python
from fixtureforge import Forge
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    email: str
    bio: str

forge = Forge()
users = forge.create_batch(User, count=50, context="SaaS platform users")
```

FixtureForge handles the rest:

- **`id`** — sequential counter (free)
- **`name`, `email`** — Faker (free)
- **`bio`** — batched AI call (1 API call for all 50 records)

---

## Why FixtureForge?

<div class="feature-grid" markdown>

<div class="feature-card" markdown>
### Intelligent Field Routing
Only semantic fields hit the AI. `id`, `email`, `phone` are handled by
Faker or counters. 100 users with 2 AI fields = **2 API calls**.
</div>

<div class="feature-card" markdown>
### Deterministic CI Mode
`seed=42` guarantees identical output across every run.
No network. No flakiness. No surprises.
</div>

<div class="feature-card" markdown>
### pytest Plugin
Declare fixtures in one line from `conftest.py`.
The `forge` fixture is auto-available in every test with zero config.
</div>

<div class="feature-card" markdown>
### DataSwarms
Generate 5 model types in parallel for the cost of 1.5.
Shared AI cache across the swarm.
</div>

<div class="feature-card" markdown>
### ForgeMemory
Persist business rules that survive sessions.
Rules inject into prompts automatically.
</div>

<div class="feature-card" markdown>
### Provider-Agnostic
Claude, GPT, Gemini, Groq, Ollama — or no AI at all.
Auto-detects from environment variables.
</div>

</div>

---

## Installation

```bash
pip install fixtureforge
```

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[API Reference](api-reference.md){ .md-button }

---

## Comparison

|                        | FixtureForge | factory_boy | faker  | hypothesis |
|------------------------|:------------:|:-----------:|:------:|:----------:|
| AI-generated context   | Yes          | No          | No     | No         |
| Deterministic (seed=)  | Yes          | Yes         | Yes    | Yes        |
| FK relationships       | Auto         | Manual      | No     | No         |
| Coverage analysis      | Yes          | No          | No     | Partial    |
| CI-safe mode           | Yes          | Yes         | Yes    | Yes        |
| Large datasets (100k+) | Yes          | Manual      | Manual | No         |
| Permission gates       | Yes          | No          | No     | No         |

FixtureForge is not a replacement for `faker` — it uses `faker` internally.
It adds the layer between *"I need realistic data"* and *"I need it to feel like production."*
