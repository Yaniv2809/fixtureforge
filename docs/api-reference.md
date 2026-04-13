# API Reference

## Forge

The main entry point for FixtureForge.

```python
from fixtureforge import Forge

forge = Forge(
    use_ai=True,              # False = offline/CI mode
    seed=None,                # int — deterministic output
    verbose=False,            # show field provenance
    allow_pii=False,          # allow SENSITIVE fields
    interactive=True,         # prompt user for DANGEROUS fields
    provider_name=None,       # "anthropic"|"openai"|"groq"|"gemini"|"ollama"
    model=None,               # model name string
    use_cache=True,           # cache AI responses for 7 days
    memory_dir=None,          # path to .forge/ dir (default: cwd)
)
```

---

### forge.create()

Generate a single record.

```python
user = forge.create(User, context="senior engineer")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `type[BaseModel]` | Pydantic model class |
| `context` | `str \| None` | Free-text context hint for AI |

---

### forge.create_batch()

Generate multiple records.

```python
users = forge.create_batch(User, count=50, context="SaaS users")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `type[BaseModel]` | Pydantic model class |
| `count` | `int` | Number of records |
| `context` | `str \| None` | Context hint for AI |

---

### forge.swarm()

Generate multiple model types in parallel.

```python
results = forge.swarm(
    models=[User, Order, Product],
    counts=[10, 50, 100],
    contexts=["SaaS users", None, None],
    seed=42,
)
# Returns: {"User": [...], "Order": [...], "Product": [...]}
```

---

### forge.create_large()

Generate large datasets with cost-controlled AI sampling.

```python
forge.create_large(Order, count=100_000, seed_ratio=0.01)
```

---

### forge.create_stream()

Lazy generator for memory-safe large datasets.

```python
for record in forge.create_stream(User, count=1_000_000, filename="users.json"):
    pass
```

---

### forge.dream()

Run ForgeDream coverage analysis.

```python
report = forge.dream(models=[User, Order], force=True)
print(report.summary())
```

Requires `FORGE_FLAG_DREAM=1`.

---

### forge.stats()

Return diagnostics dict.

```python
forge.stats()
# {"registry": {...}, "session_tokens": 1240, "memory": {...}, "flags": {...}}
```

---

### forge.clear_registry()

Reset the FK registry between independent test scenarios.

```python
forge.clear_registry()
```

---

## forge_fixture()

Declare a pytest fixture from a Pydantic model.

```python
from fixtureforge import forge_fixture

forge_fixture(
    model,            # Pydantic model class
    count=1,          # number of records
    name=None,        # fixture name (default: auto from model name)
    context=None,     # AI context hint
    seed=None,        # override seed
    use_ai=False,     # default False in tests
)
```

---

## forge_swarm_fixture()

Declare a parallel multi-model pytest fixture (session-scoped).

```python
from fixtureforge import forge_swarm_fixture

forge_swarm_fixture(
    name,             # fixture name
    models,           # list of Pydantic model classes
    counts,           # list of counts (same length as models)
    contexts=None,    # list of context strings or None
)
```

---

## ForgeMemory

```python
forge.memory.add_rule(topic: str, rule: str) -> None
forge.memory.get_rules_for_prompt() -> str
forge.memory.validate_against_schema(model: type) -> ValidationResult
```

---

## Feature Flags

```python
from fixtureforge.config import is_enabled, flag_summary

is_enabled("FORGE_DREAM")   # bool
flag_summary()               # dict of all flags and their current state
```

Available flags:

| Flag | Default | Description |
|------|---------|-------------|
| `FORGE_SWARMS` | `True` | DataSwarms parallel generation |
| `FORGE_PERMISSIONS` | `True` | Permission gates |
| `FORGE_COMPRESSION` | `True` | Session compression pipeline |
| `FORGE_MCP` | `True` | MCP integration |
| `FORGE_DREAM` | `False` | Coverage analysis |
| `FORGE_KAIROS` | `False` | Coming in v2.x |
| `FORGE_ULTRAPLAN` | `False` | Coming in v2.x |
