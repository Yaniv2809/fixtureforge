"""
FixtureForge pytest plugin.

Provides two integration points:

1. ``forge`` fixture — auto-available in every test, zero config.
   CI-safe by default (use_ai=False). Activated by FORGE_AI=1.

2. ``forge_fixture()`` — declare model fixtures in conftest.py with one line.
   Injects a named pytest fixture into the caller's namespace automatically.

-------------------------------------------------------------------------------
QUICK START
-------------------------------------------------------------------------------

# conftest.py
from fixtureforge.pytest_plugin import forge_fixture
from myapp.models import User, Order, Product

# Declare fixtures — one line per model
forge_fixture(User,    count=10,  seed=42)
forge_fixture(Order,   count=50,  seed=42, context="e-commerce orders")
forge_fixture(Product, count=1)            # singular — returns one instance

# test_users.py
def test_all_users_have_email(users):      # ← 10 User instances
    assert all("@" in u.email for u in users)

def test_order_links_customer(orders, users):  # ← FK resolved automatically
    assert all(o.user_id in {u.id for u in users} for o in orders)

def test_product_name(product):            # ← single Product instance
    assert len(product.name) > 0

-------------------------------------------------------------------------------
ADVANCED USAGE
-------------------------------------------------------------------------------

# Explicit forge fixture for one-off generation
def test_custom(forge):
    vip = forge.create(User, context="VIP enterprise customer")
    assert vip.name

# Full AI mode in dev (override with env var)
# FORGE_AI=1 pytest → uses real LLM
# FORGE_SEED=42 pytest → reproducible seed

# Scoped fixtures (shared across all tests in a module)
forge_fixture(User, count=100, seed=42, scope="module")

# Named override (when you want a different name than the model)
forge_fixture(User, count=5, seed=0, name="admin_users", context="admin accounts")

def test_admins(admin_users):
    assert len(admin_users) == 5
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Type

import pytest
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_forge_config() -> Dict[str, Any]:
    """Read Forge config from environment variables."""
    use_ai = os.environ.get("FORGE_AI", "0").strip().lower() in ("1", "true", "yes")
    seed_env = os.environ.get("FORGE_SEED", "").strip()
    seed = int(seed_env) if seed_env.isdigit() else None
    verbose = os.environ.get("FORGE_VERBOSE", "0").strip().lower() in ("1", "true", "yes")
    return {"use_ai": use_ai, "seed": seed, "verbose": verbose}


def _fixture_name_for(model: Type[BaseModel], count: int, name: Optional[str]) -> str:
    """Derive fixture name: explicit name > plural/singular from model name."""
    if name:
        return name
    base = model.__name__.lower()
    return base + "s" if count > 1 else base


# ---------------------------------------------------------------------------
# Auto-provided ``forge`` fixture (available in every test, zero config)
# ---------------------------------------------------------------------------

@pytest.fixture
def forge():
    """
    Auto-provided Forge instance.

    CI-safe by default (use_ai=False, seed from FORGE_SEED env var).
    Set FORGE_AI=1 to enable real AI generation in dev/staging.

    Example::

        def test_something(forge):
            users = forge.create_batch(User, count=10)
            assert len(users) == 10
    """
    from fixtureforge import Forge  # lazy import — keeps pytest startup fast

    cfg = _resolve_forge_config()
    return Forge(
        use_ai=cfg["use_ai"],
        seed=cfg["seed"],
        verbose=cfg["verbose"],
    )


# ---------------------------------------------------------------------------
# forge_fixture() — one-line fixture declaration
# ---------------------------------------------------------------------------

def forge_fixture(
    model: Type[BaseModel],
    count: int = 1,
    *,
    context: Optional[str] = None,
    seed: Optional[int] = None,
    use_ai: Optional[bool] = None,
    scope: str = "function",
    name: Optional[str] = None,
    **overrides: Any,
) -> Any:
    """
    Declare a pytest fixture that generates model instances.

    Call this at module level in ``conftest.py``.  The fixture is injected
    directly into the caller's namespace under the derived or given name.

    Parameters
    ----------
    model   : Pydantic BaseModel subclass to generate
    count   : number of records (>1 → list, ==1 → single instance)
    context : AI prompt context, e.g. "angry customers"
    seed    : random seed for deterministic output (overrides FORGE_SEED)
    use_ai  : override env-based detection (default: False / FORGE_AI env var)
    scope   : pytest fixture scope — "function" | "class" | "module" | "session"
    name    : explicit fixture name (default: model name in lower-case, pluralised)
    **overrides : field overrides forwarded to forge.create / create_batch

    Returns
    -------
    The pytest fixture callable (also injected into caller's namespace).

    Example::

        # conftest.py
        forge_fixture(User,  count=50, seed=42)
        forge_fixture(Order, count=200, seed=42, context="high-value orders")

        # test_orders.py
        def test_order_count(orders):
            assert len(orders) == 200
    """
    fixture_name = _fixture_name_for(model, count, name)

    # Resolve use_ai: explicit arg > env var
    _use_ai: bool
    if use_ai is not None:
        _use_ai = use_ai
    else:
        _use_ai = os.environ.get("FORGE_AI", "0").strip().lower() in ("1", "true", "yes")

    # Resolve seed: explicit arg > env var
    _seed: Optional[int]
    if seed is not None:
        _seed = seed
    else:
        seed_env = os.environ.get("FORGE_SEED", "").strip()
        _seed = int(seed_env) if seed_env.isdigit() else None

    # Capture all params in closure (avoids late-binding issues in loops)
    _model    = model
    _count    = count
    _context  = context
    _overrides = overrides

    def _fixture_fn():
        from fixtureforge import Forge  # lazy import

        f = Forge(use_ai=_use_ai, seed=_seed)

        if _count == 1:
            return f.create(_model, context=_context, **_overrides)
        return f.create_batch(_model, count=_count, context=_context, **_overrides)

    # Give the function the correct name so pytest identifies the fixture by it
    _fixture_fn.__name__ = fixture_name
    _fixture_fn.__qualname__ = fixture_name

    # Apply the pytest.fixture decorator with the requested scope
    marked = pytest.fixture(scope=scope, name=fixture_name)(_fixture_fn)

    # Inject into caller's conftest.py namespace so pytest can discover it
    frame = sys._getframe(1)
    frame.f_locals[fixture_name] = marked

    return marked


# ---------------------------------------------------------------------------
# forge_swarm_fixture() — parallel multi-model fixture in one call
# ---------------------------------------------------------------------------

def forge_swarm_fixture(
    models: List[Type[BaseModel]],
    counts: Optional[List[int]] = None,
    contexts: Optional[List[Optional[str]]] = None,
    *,
    seed: Optional[int] = None,
    use_ai: Optional[bool] = None,
    scope: str = "session",
) -> Any:
    """
    Declare a single fixture that generates multiple models in parallel
    using DataSwarms.  Returns a dict mapping model_name → list.

    Best used with ``scope="session"`` so the swarm runs once per test run.

    Example::

        # conftest.py
        forge_swarm_fixture(
            [User, Order, Product],
            counts=[10, 50, 100],
            seed=42,
        )

        # test_something.py
        def test_data_volume(swarm_data):
            assert len(swarm_data["User"]) == 10
            assert len(swarm_data["Order"]) == 50
    """
    _use_ai = (
        use_ai
        if use_ai is not None
        else os.environ.get("FORGE_AI", "0").strip().lower() in ("1", "true", "yes")
    )
    _seed = seed or (
        int(s) if (s := os.environ.get("FORGE_SEED", "").strip()).isdigit() else None
    )

    def _swarm_fn():
        from fixtureforge import Forge

        f = Forge(use_ai=_use_ai, seed=_seed)
        return f.swarm(models=models, counts=counts, contexts=contexts)

    _swarm_fn.__name__ = "swarm_data"
    _swarm_fn.__qualname__ = "swarm_data"

    marked = pytest.fixture(scope=scope, name="swarm_data")(_swarm_fn)

    frame = sys._getframe(1)
    frame.f_locals["swarm_data"] = marked

    return marked
