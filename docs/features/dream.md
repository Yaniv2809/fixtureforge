# ForgeDream

ForgeDream is a background coverage analysis engine that finds gaps in your test-data rules.

---

## Enabling

ForgeDream is off by default. Enable it with an environment variable:

```bash
FORGE_FLAG_DREAM=1 python run_tests.py
```

Or in code:

```python
import os
os.environ["FORGE_FLAG_DREAM"] = "1"
```

---

## Running Manually

```python
report = forge.dream(models=[User, Order], force=True)
print(report.summary())
```

Example output:

```
ForgeDream Report - 2026-04-14
  Coverage gaps found  : 3
  Rule conflicts found : 0
  Top gaps:
    [User.age]    no_boundary : No boundary-value rules for numeric field 'age'
    [User.email]  no_invalid  : No invalid-data rules for well-known field 'email'
    [Order.total] no_boundary : No boundary-value rules for numeric field 'total'
```

---

## Four Phases

| Phase | What it does |
|-------|-------------|
| **Orient** | Reads the FORGE.md index to understand existing rules |
| **Gather** | Scans models for coverage gaps (boundary values, invalid data, edge cases) |
| **Consolidate** | Merges redundant or conflicting rules |
| **Prune** | Trims the rule index to max 200 lines, evicting least-used rules |

---

## Gap Detection

ForgeDream looks for two types of gaps:

**Boundary coverage** — numeric fields with no boundary-value rules:

```
[User.age]   no_boundary : No rules for min/max/zero/negative values
[Order.qty]  no_boundary : No rules for zero quantity or overflow
```

**Invalid coverage** — well-known fields with no invalid-data rules:

```
[User.email]  no_invalid : No rules for malformed email formats
[User.phone]  no_invalid : No rules for invalid phone numbers
[User.dob]    no_invalid : No rules for future dates or 1900-01-01
```

---

## Auto-Trigger

When enabled, ForgeDream triggers automatically when:

- 24 hours have passed since last run
- 5 new sessions since last run
- At least 10 minutes since the last scan

It runs in a background thread and never blocks generation.

---

## Output Files

```
.forge/
  coverage_gaps.json    # structured gap report
  .dream_state.json     # last run timestamp, session count
```
