# Quick Start

## Your First Fixture

Define a Pydantic model and generate data in two lines:

```python
from fixtureforge import Forge
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str
    email: str
    bio: str

forge = Forge()
users = forge.create_batch(User, count=10, context="SaaS platform users")
```

FixtureForge automatically routes each field:

| Field | Router | Cost |
|-------|--------|------|
| `id` | Sequential counter | Free |
| `name` | Faker | Free |
| `email` | Faker | Free |
| `bio` | AI (batched) | 1 API call for all 10 |

---

## Offline / CI Mode

No API key required:

```python
forge = Forge(use_ai=False, seed=42)
users = forge.create_batch(User, count=100)
# Identical output every run — perfect for CI
```

---

## Single Record

```python
user = forge.create(User)
```

---

## With Context

Context shapes the AI-generated fields:

```python
angry_users = forge.create_batch(
    Review,
    count=20,
    context="1-star reviews from angry holiday shoppers"
)
```

---

## Verbose Mode

See where every value comes from:

```python
forge = Forge(use_ai=False, seed=42, verbose=True)
user = forge.create(User)

# [structural] id    = 1
# [faker]      name  = 'Allison Hill'
# [faker]      email = 'donaldgarcia@example.net'
# [ai]         bio   = 'Passionate developer with 8 years...'
```

---

## Foreign Keys

Register parents first — child FKs resolve automatically:

```python
customers = forge.create_batch(Customer, count=10)
orders = forge.create_batch(Order, count=100)
# order.customer_id always points to a real customer.id
```

---

## pytest Integration

In `conftest.py`:

```python
from fixtureforge import forge_fixture
from myapp.models import User, Order

forge_fixture(User, count=50)
forge_fixture(Order, count=200)
```

In your tests:

```python
def test_users_have_emails(users):
    assert all(u.email for u in users)

def test_order_count(orders):
    assert len(orders) == 200
```

See [pytest Plugin](../features/pytest-plugin.md) for full details.
