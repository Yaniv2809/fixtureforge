# pytest Plugin

FixtureForge ships a first-class pytest plugin that auto-registers via the `pytest11` entry point — no manual imports needed.

---

## The `forge` Fixture

The `forge` fixture is available in **every test with zero configuration**:

```python
def test_generate_user(forge):
    user = forge.create(User)
    assert user.email

def test_batch(forge):
    users = forge.create_batch(User, count=10)
    assert len(users) == 10
```

The fixture reads from environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FORGE_AI` | `0` | Set to `1` to enable AI in tests |
| `FORGE_SEED` | `42` | Seed for deterministic output |
| `FORGE_VERBOSE` | `0` | Set to `1` for field provenance logs |

---

## Declaring Model Fixtures

Use `forge_fixture()` in `conftest.py` to declare fixtures for your models:

```python
# conftest.py
from fixtureforge import forge_fixture
from myapp.models import User, Order, Product

forge_fixture(User, count=50)
forge_fixture(Order, count=200)
forge_fixture(Product, count=1)   # count=1 -> singular name 'product'
```

This auto-creates fixtures named after your models:

```python
def test_user_count(users):           # 50 users
    assert len(users) == 50

def test_orders_have_users(orders):   # 200 orders
    assert all(o.user_id for o in orders)

def test_product_exists(product):     # single instance (not a list)
    assert product.name
```

**Naming convention:**

- `count > 1` → plural snake_case (`User` → `users`, `OrderItem` → `order_items`)
- `count == 1` → singular snake_case (`User` → `user`)

---

## Named Fixtures

Override the auto-generated name:

```python
forge_fixture(User, count=5, name="admin_users", context="platform administrators")
```

```python
def test_admins(admin_users):
    assert len(admin_users) == 5
```

---

## Swarm Fixtures

Generate multiple models in parallel with a shared AI cache:

```python
# conftest.py
from fixtureforge import forge_swarm_fixture
from myapp.models import User, Order, Product

forge_swarm_fixture(
    name="app_data",
    models=[User, Order, Product],
    counts=[10, 50, 20],
)
```

```python
def test_full_app(app_data):
    assert len(app_data["User"]) == 10
    assert len(app_data["Order"]) == 50
    assert len(app_data["Product"]) == 20
```

Swarm fixtures are **session-scoped** — generated once, shared across all tests.

---

## Seed Determinism in Tests

```python
def test_seed_determinism():
    from fixtureforge import Forge

    forge_a = Forge(use_ai=False, seed=42)
    forge_b = Forge(use_ai=False, seed=42)

    result_a = forge_a.create_batch(User, count=5)
    result_b = forge_b.create_batch(User, count=5)

    assert result_a == result_b  # guaranteed identical
```

---

## Source Mode (Development)

When running FixtureForge from source (not installed), add to `conftest.py`:

```python
# conftest.py
pytest_plugins = ["fixtureforge.pytest_plugin"]
```
