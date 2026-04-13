# Installation

## Requirements

- Python **3.11+**
- pydantic **>= 2.5**
- faker **>= 22.0**

AI providers are **optional extras** — the core works offline with zero extra dependencies.

---

## Basic Install

```bash
pip install fixtureforge
```

This gives you the full offline mode: Faker-based generation, seed determinism, FK resolution, pytest plugin, and all architecture layers.

---

## With AI Providers

Install with your preferred provider:

```bash
pip install "fixtureforge[groq]"       # Groq — free tier, recommended
pip install "fixtureforge[anthropic]"  # Claude
pip install "fixtureforge[openai]"     # GPT
pip install "fixtureforge[gemini]"     # Google Gemini
pip install "fixtureforge[all]"        # All providers
```

Then set your API key as an environment variable:

```bash
export GROQ_API_KEY=gsk_...
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...
```

---

## Verify Installation

```python
import fixtureforge
print(fixtureforge.__version__)  # 2.1.0
```

Quick smoke test (offline, no API key needed):

```python
from fixtureforge import Forge
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    email: str

forge = Forge(use_ai=False, seed=42)
users = forge.create_batch(User, count=3)
for u in users:
    print(u)
```

---

## Next Steps

- [Quick Start](quickstart.md) — generate your first fixture in 2 minutes
- [Providers](../concepts/providers.md) — configure AI providers
- [pytest Plugin](../features/pytest-plugin.md) — integrate with your test suite
