# Frequently Asked Questions

Real questions from developers, QA engineers, and architects evaluating FixtureForge.

---

## Why FixtureForge?

### I already use factory_boy + Faker. What does FixtureForge actually add?

factory_boy is a solid library — but it requires you to explicitly define every fake value:
`factory.Faker('name')`, `factory.Faker('email')`, and so on for every field in every model.
FixtureForge reads your Pydantic model and routes each field automatically:
`id` → sequential counter, `email` → Faker, `bio` → AI. Nothing to declare.

Beyond that, FixtureForge adds things that factory_boy doesn't have and
that you'd need to build yourself:

- **Automatic FK resolution** — child models always reference valid parent IDs
- **Seed determinism** — instance-level RNG isolation, not global state
- **DataSwarms** — parallel multi-model generation with a shared AI cache
- **Response caching** — identical requests cost nothing after the first call
- **pytest plugin** — one-line fixture declaration in `conftest.py`
- **ForgeMemory** — persistent business rules that inject into every generation call

If factory_boy already covers your needs, there's no urgent reason to switch.
FixtureForge is most valuable when you need realistic semantic content
(bios, descriptions, reviews) or when managing complex relational datasets.

---

### Why not just write 20 lines of Python that call the ChatGPT API directly?

You can — and for a one-off script, that's perfectly reasonable.
The gap appears quickly once you need production-grade behavior:

| Concern | 20-line script | FixtureForge |
|---------|---------------|--------------|
| 100 records | 100 API calls | 1 batched call |
| `id`, `email`, `phone` | still sent to AI | free via Faker/counters |
| Repeat runs | paid every time | 7-day response cache |
| Same data across runs | manual | `seed=` parameter |
| FK relationships | you build it | automatic |
| Pydantic validation | you build it | built-in, with retry |
| pytest fixture | you wire it | one-line declaration |

The 20-line script tends to become 200 lines by month two.

---

### Why not build an in-house solution tailored to our stack?

A week of work gets you basic generation. What takes months:
batching, response caching, FK graph resolution, per-instance RNG isolation
(so parallel tests don't interfere), graceful fallback when the AI is unavailable,
permission gates for sensitive fields, and pytest integration.

FixtureForge went through that exact build in its v2.0 rewrite.
The problems you'll discover in month three of an in-house solution
are precisely the ones v2.0 was designed to solve.
The MIT license means you can fork and modify it freely if the defaults don't fit.

---

## CI/CD and Cost

### Will AI calls make our CI pipeline slow and expensive?

The short answer: **use AI in development, not in CI.**

The `forge` pytest fixture defaults to `use_ai=False, seed=42` in tests.
CI runs with zero network calls, zero cost, and no latency.
AI generation is used during development to explore realistic edge cases —
the results are pinned to a seed and replayed deterministically in CI.

For the cases where you do use AI, the cost is lower than it appears:
100 records with 2 semantic fields = 2 API calls (one per field type, batched),
not 200. Standard fields like `id`, `name`, `email` never touch the AI.

---

### What happens when the AI provider is unavailable? Does CI go red?

No. FixtureForge falls back gracefully to Faker-only generation
if the AI provider doesn't respond. No exceptions are raised unless
you explicitly set `strict=True`. A CI pipeline should never fail
because of LLM latency or an external API outage.

---

### Is there caching? We run tests dozens of times per day.

Yes — a local response cache with a 7-day TTL stored at `~/.fixtureforge/cache/`.
An identical request (same model, same context, same library version)
returns the cached result with zero API calls.

```python
forge = Forge(use_cache=True)   # default
forge = Forge(use_cache=False)  # disable if you need fresh data every run
```

---

### How is determinism actually guaranteed? I fight flaky tests daily.

The `seed=` parameter controls two independent mechanisms:

1. **`faker.seed_instance(seed)`** — called at the instance level, not globally.
   Two `Forge(seed=42)` instances don't interfere with each other's Faker state.
2. **`random.Random(seed)`** — a dedicated RNG per Forge instance,
   completely isolated from Python's global `random` module.

Result: the same seed always produces the same data, on every machine,
in every run, even when multiple Forge instances run in parallel threads.

```python
forge_a = Forge(use_ai=False, seed=42)
forge_b = Forge(use_ai=False, seed=42)

assert forge_a.create_batch(User, count=5) == forge_b.create_batch(User, count=5)
# True — always
```

---

## Practical Usage

### How do I inject complex, domain-specific business context?

Two layers, used together:

```python
# Per-call context — shapes this generation only
users = forge.create_batch(
    Customer,
    count=10,
    context="VIP customer with an overdue balance, Israeli locale"
)

# Persistent rules — auto-injected into every future generation call
forge.memory.add_rule("financial", "VIP customers always have credit_limit > 10000")
forge.memory.add_rule("user", "Israeli phone numbers use the format 05x-xxx-xxxx")
forge.memory.add_rule("orders", "Maximum 3 active loans per customer at any time")
```

Memory rules are re-read from disk on every call —
update a rule and the next generation picks it up immediately, no restart needed.

---

### How do I know the AI response actually matches my Pydantic schema?

Every AI response is validated against your Pydantic model before it's returned.
An invalid response triggers a retry. If retries are exhausted,
FixtureForge falls back to Faker for that specific field.
Your test always receives a fully validated model instance — never raw JSON.

---

### Can I generate intentionally invalid data for negative testing?

Yes. Use the `context` parameter to describe the invalidity you need:

```python
invalid_users = forge.create_batch(
    User,
    count=20,
    context="invalid data: malformed emails missing the @ symbol, "
            "negative ages, empty required fields, strings exceeding max length"
)
```

[ForgeDream](features/dream.md), when enabled, also scans your models automatically
and flags fields that have no negative-testing coverage, then suggests rules to add.

---

## Security and Compliance

### Will our database schemas or internal logic leak to external AI providers?

Only the names of semantic fields and your `context` string are included in the prompt.
The following are **never sent**:

- Database connection strings or credentials
- Production data values
- Internal business logic or proprietary code
- Full table schemas beyond the Pydantic model field names

For environments where zero external data transfer is acceptable,
use `provider_name="ollama"` (local inference) or `use_ai=False`.
Both options operate entirely offline.

---

### Can FixtureForge run fully offline in an air-gapped environment?

Yes. Two options:

```python
# Option 1: Local inference via Ollama
forge = Forge(provider_name="ollama", model="llama3.2")
# Requires Ollama running locally: https://ollama.com

# Option 2: No AI at all
forge = Forge(use_ai=False, seed=42)
```

No mandatory cloud calls exist anywhere in the architecture.
Every component that touches an external provider is pluggable and replaceable.

---

### What is the license? Can we use this in a commercial product?

**MIT License.** You can use, modify, distribute, and incorporate FixtureForge
into a closed-source commercial product without any obligation to open your own code.
There is no copyleft, no patent clause, and no commercial restriction of any kind.

---

## Project Health

### What is the project roadmap? I won't adopt a young library that might be abandoned.

Fair concern. The current roadmap includes:

- **`FORGE_KAIROS`** — time-aware generation (temporal logic: `created_at < updated_at`,
  expired tokens, event sequences)
- **OpenAPI / JSON Schema input** — generate fixtures directly from a `swagger.json`
  without defining a Pydantic model
- **VS Code extension** — right-click a model, generate fixtures inline in the editor
- **ForgeDream auto-suggestions** — when a coverage gap is found,
  automatically propose the rule to add

FixtureForge is MIT licensed, which means it is forkable at any time
with no legal or licensing friction. The full architecture is documented,
and the CHANGELOG is detailed enough that a new maintainer could take over
without a handoff conversation.

The risk of depending on a young single-maintainer project is real
and worth weighing against your adoption criteria.
If long-term guaranteed maintenance is a hard requirement,
that is a legitimate reason to look at more established alternatives.

---

!!! tip "Have a question that isn't here?"
    Open a [GitHub Discussion](https://github.com/Yaniv2809/fixtureforge/discussions)
    — questions asked there often end up in this FAQ.
