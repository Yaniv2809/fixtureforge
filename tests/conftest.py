"""
FixtureForge pytest plugin — integration test conftest.
Demonstrates the exact API a real project would use.
"""
# When running from source (not installed), register plugin explicitly.
# In installed projects this is handled automatically via the pytest11 entry point.
pytest_plugins = ["fixtureforge.pytest_plugin"]

from pydantic import BaseModel

from fixtureforge.pytest_plugin import forge_fixture, forge_swarm_fixture


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(BaseModel):
    id: int
    name: str
    email: str
    age: int


class Order(BaseModel):
    id: int
    user_id: int
    amount: float


class Product(BaseModel):
    id: int
    name: str
    price: float


# ---------------------------------------------------------------------------
# Fixture declarations — one line each
# ---------------------------------------------------------------------------

forge_fixture(User,    count=10,  seed=42)           # → fixture: "users"
forge_fixture(Order,   count=25,  seed=42)           # → fixture: "orders"
forge_fixture(Product, count=1,   seed=42)           # → fixture: "product"  (singular)
forge_fixture(User,    count=5,   seed=99,
              name="admin_users",
              context="admin accounts")               # → fixture: "admin_users"

forge_swarm_fixture(
    [User, Order, Product],
    counts=[5, 10, 3],
    seed=42,
    scope="session",
)                                                     # → fixture: "swarm_data"
