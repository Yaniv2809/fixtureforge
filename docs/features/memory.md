# ForgeMemory

ForgeMemory persists business rules across sessions so you don't have to re-specify them in every generation call.

---

## Adding Rules

```python
forge.memory.add_rule("user", "Users under 18 get account_type='restricted'")
forge.memory.add_rule("financial", "Max 3 active loans per customer at any time")
forge.memory.add_rule("user", "Israeli phone numbers use format 05x-xxx-xxxx")
```

Rules are stored in `.forge/` in your project directory and injected into AI prompts automatically on every generation call.

---

## How Rules Inject

Rules are re-read from disk on every `create_batch()` call — not cached in memory. This means:

- Edit a rule file → next generation call picks it up immediately
- No restart needed
- Always fresh

---

## Skeptical Memory

FixtureForge validates stored rules against the live schema before using them:

```python
# If the schema changes (e.g., account_type field removed),
# the rule is flagged as potentially invalid
result = forge.memory.validate_against_schema(User)
if result.has_conflicts:
    print(result.conflicts)
```

---

## Progressive Forgetting

FixtureForge never stores what it can re-derive:

- Field names? The model schema has them.
- Field types? Same.
- Default values? Pydantic handles those.

Only business rules that exist **nowhere else in the code** are kept.

Field-name-only rules are rejected:

```python
forge.memory.add_rule("user", "name is a string")
# Rejected: re-derivable from schema. Nothing stored.
```

---

## Storage Structure

```
.forge/
  FORGE.md          # index — topic list + line counts (max 200 lines)
  user.md           # user domain rules (max 10KB)
  financial.md      # financial domain rules (max 10KB)
  .dream_state.json # ForgeDream run state
  coverage_gaps.json
```

---

## Stats

```python
forge.stats()
# {
#   "memory": {
#     "topics": 3,
#     "total_kb": 2.4
#   }
# }
```
