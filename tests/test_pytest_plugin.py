"""
Integration tests for the FixtureForge pytest plugin.
All tests use use_ai=False (seed-controlled) — zero network, fully deterministic.
"""
from fixtureforge import Forge
from fixtureforge.pytest_plugin import forge_fixture


# ---------------------------------------------------------------------------
# Basic fixture tests
# ---------------------------------------------------------------------------

def test_users_count(users):
    """forge_fixture with count=10 delivers exactly 10 records."""
    assert len(users) == 10


def test_users_have_valid_emails(users):
    """All generated emails contain '@'."""
    assert all("@" in u.email for u in users)


def test_users_have_sequential_ids(users):
    """IDs are assigned sequentially starting from 1."""
    ids = [u.id for u in users]
    assert ids == sorted(ids)
    assert ids[0] >= 1


def test_users_have_positive_age(users):
    """Age is a positive integer."""
    assert all(u.age > 0 for u in users)


def test_orders_count(orders):
    """forge_fixture with count=25 delivers exactly 25 records."""
    assert len(orders) == 25


def test_product_is_single_instance(product):
    """count=1 returns a single instance, not a list."""
    from pydantic import BaseModel
    assert isinstance(product, BaseModel)
    assert not isinstance(product, list)
    assert hasattr(product, "id") and hasattr(product, "name") and hasattr(product, "price")


def test_named_fixture(admin_users):
    """Explicit name= parameter creates fixture under that name."""
    assert len(admin_users) == 5


# ---------------------------------------------------------------------------
# Determinism tests — same seed = same data across runs
# ---------------------------------------------------------------------------

def test_seed_determinism():
    """Same seed produces identical output every time."""
    forge_a = Forge(use_ai=False, seed=42)
    forge_b = Forge(use_ai=False, seed=42)

    from tests.conftest import User
    a = forge_a.create_batch(User, count=5)
    b = forge_b.create_batch(User, count=5)

    assert [u.model_dump() for u in a] == [u.model_dump() for u in b]


def test_different_seeds_give_different_data():
    """Different seeds produce different results."""
    from tests.conftest import User

    forge_a = Forge(use_ai=False, seed=42)
    forge_b = Forge(use_ai=False, seed=99)

    a = forge_a.create_batch(User, count=5)
    b = forge_b.create_batch(User, count=5)

    assert any(ua.name != ub.name for ua, ub in zip(a, b))


# ---------------------------------------------------------------------------
# forge fixture (auto-provided)
# ---------------------------------------------------------------------------

def test_forge_fixture_creates_instances(forge):
    """The auto-provided ``forge`` fixture works out of the box."""
    from tests.conftest import User
    users = forge.create_batch(User, count=3)
    assert len(users) == 3
    assert all(u.id > 0 for u in users)


def test_forge_fixture_single_record(forge):
    """forge.create returns a single instance when count=1."""
    from tests.conftest import User
    user = forge.create(User)
    assert user.id >= 1
    assert "@" in user.email


# ---------------------------------------------------------------------------
# FK relationship test
# ---------------------------------------------------------------------------

def test_fk_resolution(forge):
    """Orders automatically reference valid user IDs."""
    from tests.conftest import User, Order

    users = forge.create_batch(User, count=5)
    orders = forge.create_batch(Order, count=20)

    user_ids = {u.id for u in users}
    for order in orders:
        assert order.user_id in user_ids, (
            f"order.user_id={order.user_id} not in user IDs {user_ids}"
        )


# ---------------------------------------------------------------------------
# Swarm fixture
# ---------------------------------------------------------------------------

def test_swarm_data_keys(swarm_data):
    """forge_swarm_fixture returns all requested models."""
    assert "User" in swarm_data
    assert "Order" in swarm_data
    assert "Product" in swarm_data


def test_swarm_data_counts(swarm_data):
    """Each model in the swarm has the correct record count."""
    assert len(swarm_data["User"])    == 5
    assert len(swarm_data["Order"])   == 10
    assert len(swarm_data["Product"]) == 3
