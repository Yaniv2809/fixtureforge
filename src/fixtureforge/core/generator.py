"""
BasicGenerator — generate a single model instance using Faker + AI routing.

For bulk generation (N records) use SmartBatchEngine which makes far fewer
API calls by batching all semantic fields across all records.
"""
import random
import uuid
from typing import Any, Dict, List, Optional, Type

from faker import Faker

from ..ai.engine import AIEngine
from .parser import FieldInfo, ModelParser
from .router import FieldTier, IntelligentRouter


class BasicGenerator:
    """
    Generate one model instance at a time.
    Uses the IntelligentRouter to pick the cheapest generation strategy
    for each field.
    """

    def __init__(
        self,
        locale: str = "en_US",
        ai_engine: Optional[AIEngine] = None,
        seed: Optional[int] = None,
        verbose: bool = False,
        # Legacy: accept api_key for backwards compatibility
        api_key: Optional[str] = None,
    ):
        self.faker = Faker(locale)
        self.router = IntelligentRouter()
        self._id_counters: Dict[str, int] = {}
        self.registry: Dict[str, List[Any]] = {}
        self.verbose = verbose

        if seed is not None:
            # seed_instance() seeds THIS faker object's private RNG only —
            # two Forge(seed=42) instances are fully independent.
            self.faker.seed_instance(seed)
            # Use a dedicated Random instance (not global random module)
            # so two Forge objects with the same seed don't interfere.
            self._rng = random.Random(seed)
        else:
            self._rng = random

        if ai_engine is not None:
            self.ai_engine = ai_engine
        elif api_key:
            # Legacy path — auto-detect provider from key
            from ..providers.factory import create_provider  # noqa: PLC0415
            provider = create_provider(api_key=api_key)
            self.ai_engine = AIEngine(provider=provider)
        else:
            self.ai_engine = AIEngine(provider=None)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def generate(self, model: Type, context: str = None, **overrides) -> Any:
        """Generate one model instance with optional context and field overrides."""
        fields = ModelParser.parse(model)

        data: Dict[str, Any] = {}
        for field in fields:
            if field.name in overrides:
                data[field.name] = overrides[field.name]
            else:
                value = self._generate_smart_value(field, context)
                # COMPUTED fields return _SKIP sentinel; exclude from data dict
                if value is not _SKIP:
                    data[field.name] = value

        return model(**data)

    # ------------------------------------------------------------------
    # Internal routing
    # ------------------------------------------------------------------

    def _generate_smart_value(self, field: FieldInfo, context: str = None) -> Any:
        tier = self.router.classify(field)

        if tier == FieldTier.STRUCTURAL:
            val = self._generate_structural(field)
            if self.verbose:
                print(f"  [structural] {field.name} = {val!r}")
            return val

        if tier == FieldTier.COMPUTED:
            if self.verbose:
                print(f"  [computed]   {field.name} = <pydantic>")
            return _SKIP

        if tier == FieldTier.SEMANTIC:
            val = self._generate_semantic_content(field, context)
            if self.verbose:
                print(f"  [ai]         {field.name} = {str(val)[:80]!r}")
            return val

        val = self._generate_standard(field)
        if self.verbose:
            print(f"  [faker]      {field.name} = {val!r}")
        return val

    # ------------------------------------------------------------------
    # Structural (IDs / FKs)
    # ------------------------------------------------------------------

    def _generate_structural(self, field: FieldInfo) -> Any:
        name = field.name.lower()

        # Foreign key: resolve from registry
        if name.endswith("_id") and name != "id":
            target_model = name[: -len("_id")]
            records = self.registry.get(target_model, [])
            if records:
                return getattr(self._rng.choice(records), "id", None)

        # Integer PK / sequential ID
        if "int" in field.type_name.lower():
            if field.name not in self._id_counters:
                self._id_counters[field.name] = 1
            val = self._id_counters[field.name]
            self._id_counters[field.name] += 1
            return val

        # UUID fallback
        return str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Semantic (AI-generated, single field)
    # ------------------------------------------------------------------

    def _generate_semantic_content(self, field: FieldInfo, context: str = None) -> str:
        if not self.ai_engine or not self.ai_engine.is_available:
            return f"[AI Placeholder for {field.name}]"

        prompt = f"Generate a realistic value for a database field named '{field.name}'."
        if context:
            prompt += f" IMPORTANT CONTEXT: {context}."
        prompt += " Output ONLY the value, no quotes, no explanation."

        # Use field name + context as cache key so identical requests are free
        cache_key = f"single|{field.name}|{context or ''}"
        return self.ai_engine.generate_text(prompt, cache_key=cache_key)

    # ------------------------------------------------------------------
    # Standard (Faker)
    # ------------------------------------------------------------------

    def _generate_standard(self, field: FieldInfo) -> Any:
        name = field.name.lower()
        name_parts = set(name.split("_"))
        type_name = field.type_name.lower()

        # String heuristics — order matters (more specific first).
        # Use word-boundary checks (name_parts) for short common keywords
        # that could be substrings of unrelated words (age/message, date/update…).
        if "email" in name:
            return self.faker.email()
        if "phone" in name:
            return self.faker.phone_number()
        if "username" in name or "username" in name_parts:
            return self.faker.user_name()
        if "avatar" in name or "photo" in name or "image" in name:
            return self.faker.image_url()
        if "url" in name or "link" in name or "website" in name:
            return self.faker.url()
        if "address" in name:
            return self.faker.address()
        if "city" in name:
            return self.faker.city()
        if "state" in name_parts:
            return self.faker.state()
        if "country" in name:
            return self.faker.country()
        if "zip" in name_parts or "postal" in name:
            return self.faker.postcode()
        if "name" in name_parts or name.endswith("name"):
            return self.faker.name()
        if "date" in name_parts:
            return self.faker.date_this_decade()
        if "time" in name_parts:
            return self.faker.time()
        if "gender" in name_parts:
            return self._rng.choice(["male", "female", "non-binary"])
        if "age" in name_parts:
            return self._rng.randint(18, 80)
        if "salary" in name or "amount" in name or "price" in name:
            return round(self._rng.uniform(10, 10_000), 2)
        if "score" in name or "rating" in name:
            return round(self._rng.uniform(1, 5), 1)
        if "quantity" in name or "qty" in name:
            return self._rng.randint(1, 100)
        if "weight" in name_parts:
            return round(self._rng.uniform(0.1, 500), 2)
        if "height" in name_parts:
            return round(self._rng.uniform(1.0, 2.5), 2)

        # Type fallbacks
        if "int" in type_name:
            return self._generate_int(field)
        if "bool" in type_name:
            return self.faker.boolean()
        if "float" in type_name:
            return round(self._rng.uniform(0, 1000), 2)
        if "list" in type_name:
            return []
        if "dict" in type_name:
            return {}

        return self.faker.word()

    def _generate_int(self, field: FieldInfo) -> int:
        c = field.constraints
        min_val = c.get("ge", c.get("gt", 0) + 1 if "gt" in c else 0)
        max_val = c.get("le", c.get("lt", 10001) - 1 if "lt" in c else 10000)
        if min_val > max_val:
            max_val = min_val + 100
        return self._rng.randint(min_val, max_val)


# Sentinel object returned for COMPUTED fields so the generator knows to
# exclude them from the data dict (Pydantic will compute them automatically).
class _SkipSentinel:
    pass


_SKIP = _SkipSentinel()
