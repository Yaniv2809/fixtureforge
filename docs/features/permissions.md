# Permission Gates

FixtureForge classifies every model by data sensitivity and gates operations accordingly.

---

## Three Levels

| Level | Examples | Behavior |
|-------|----------|----------|
| **SAFE** | `name`, `email`, `id` | Auto-approved |
| **SENSITIVE** | `ssn`, `salary`, `passport_number` | Requires `allow_pii=True` or `FORGE_ALLOW_PII=1` |
| **DANGEROUS** | SQL injection strings, XSS payloads | Requires interactive confirmation |

---

## Usage

```python
class SafeUser(BaseModel):
    id: int
    name: str            # SAFE

class CustomerProfile(BaseModel):
    id: int
    ssn: str             # SENSITIVE
    salary: float        # SENSITIVE

class SecurityTest(BaseModel):
    id: int
    sql_injection: str   # DANGEROUS
    xss_payload: str     # DANGEROUS
```

```python
# Enable PII generation
forge = Forge(allow_pii=True)
profiles = forge.create_batch(CustomerProfile, count=10)

# CI/headless — dangerous ops silently rejected
forge = Forge(interactive=False)

# Interactive — user prompted to confirm dangerous ops
forge = Forge(interactive=True)
```

---

## Environment Variables

```bash
FORGE_ALLOW_PII=1        # allow sensitive fields without code change
```

---

## Mailbox Pattern

The permission system uses a thread-safe Mailbox Pattern with `threading.Lock`:

1. Generation request submitted to mailbox
2. `ForgeCoordinator` atomically claims the request
3. `FieldPermissionChecker` classifies all fields
4. Gate decision: auto-approve / env-check / prompt user
5. Result returned or request rejected

This means permission checks are **safe to use from multiple threads** (e.g., inside DataSwarms).
