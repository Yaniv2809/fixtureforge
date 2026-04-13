"""
FixtureForge - Demo
===================
Run from the project root:

  Without AI (deterministic only):
    python examples/demo.py

  With an AI provider (set ONE of these env vars first):
    set GROQ_API_KEY=gsk_...         && python examples/demo.py
    set GOOGLE_API_KEY=...           && python examples/demo.py
    set OPENAI_API_KEY=...           && python examples/demo.py
    set ANTHROPIC_API_KEY=...        && python examples/demo.py

Demos covered:
  1. Provider auto-detection
  2. Field tier classification  (STRUCTURAL / STANDARD / COMPUTED / SEMANTIC)
  3. Single record generation
  4. Relationships between models (FK registry)
  5. @computed_field support
  6. Smart batch generation
  7. Export to JSON / CSV / SQL
  8. Streaming (memory-safe)
  9. Registry stats
"""
import os
import sys
import tempfile
from pathlib import Path

# Allow running from project root without pip-installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load .env from project root (if python-dotenv is installed)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — use env vars set manually

# Force UTF-8 so emoji/special chars work on all terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pydantic import BaseModel, Field, computed_field

from fixtureforge import Forge
from fixtureforge.core.exporter import DataExporter
from fixtureforge.core.parser import ModelParser
from fixtureforge.core.router import FieldTier, IntelligentRouter

SEP = "-" * 60


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class Category(BaseModel):
    id: int
    name: str


class Product(BaseModel):
    id: int
    category_id: int          # FK  -> resolved from registry
    name: str
    email: str                # vendor contact email
    price: float
    rating: float
    description: str          # SEMANTIC -> AI generated
    review: str               # SEMANTIC -> AI generated

    @computed_field
    @property
    def discounted_price(self) -> float:
        """10% loyalty discount, calculated automatically."""
        return round(self.price * 0.9, 2)


class SupportTicket(BaseModel):
    id: int
    customer_name: str
    email: str
    subject: str = Field(max_length=100)   # short -> STANDARD (Faker)
    message: str                           # SEMANTIC -> AI generated
    status: str = Field(default="open")
    priority: int = Field(ge=1, le=5)


# ------------------------------------------------------------------ #
#  1. Provider detection                                               #
# ------------------------------------------------------------------ #

section("1 - Provider detection")

forge = Forge()  # auto-detects from env vars

if forge.use_ai:
    print(f"  [OK] AI provider active  ->  model: {forge.provider_name}")
else:
    print("  [--] No API key found. Running in deterministic-only mode.")
    print("       Set GROQ_API_KEY / GOOGLE_API_KEY / OPENAI_API_KEY /")
    print("       ANTHROPIC_API_KEY, or start Ollama locally.")

# ------------------------------------------------------------------ #
#  2. Field tier classification                                        #
# ------------------------------------------------------------------ #

section("2 - Field tier classification  (Product model)")

router = IntelligentRouter()
fields = ModelParser.parse(Product)

tier_labels = {
    FieldTier.STRUCTURAL: "[STRUCT]",
    FieldTier.STANDARD:   "[STND  ]",
    FieldTier.COMPUTED:   "[COMP  ]",
    FieldTier.SEMANTIC:   "[AI    ]",
}

for f in fields:
    tier = router.classify(f)
    print(f"  {tier_labels[tier]}  {f.name}")

# ------------------------------------------------------------------ #
#  3. Single record                                                    #
# ------------------------------------------------------------------ #

section("3 - Single record")

cat = forge.create(Category)
print(f"  Category  id={cat.id}  name={cat.name!r}")

product = forge.create(Product, context="organic health food e-commerce")
print(f"  Product   id={product.id}  name={product.name!r}")
print(f"            price={product.price}  ->  discounted={product.discounted_price}")
print(f"            category_id={product.category_id}")
if forge.use_ai:
    print(f"            description: {product.description[:80]}...")
    print(f"            review:      {product.review[:80]}...")

# ------------------------------------------------------------------ #
#  4. Relationships (FK registry)                                      #
# ------------------------------------------------------------------ #

section("4 - Relationships (FK registry)")

forge.clear_registry()

categories = forge.create(Category, count=3)
print(f"  Created {len(categories)} categories  "
      f"(ids: {[c.id for c in categories]})")

products = forge.create_batch(
    Product, count=6, context="electronics and gadgets store"
)
print(f"  Created {len(products)} products")

cat_ids = {c.id for c in categories}
for p in products:
    ok = "OK" if p.category_id in cat_ids else "FAIL"
    print(f"    [{ok}] product.category_id={p.category_id}  name={p.name!r}")

# ------------------------------------------------------------------ #
#  5. @computed_field                                                  #
# ------------------------------------------------------------------ #

section("5 - @computed_field  (price -> discounted_price)")

for p in products[:3]:
    expected = round(p.price * 0.9, 2)
    ok = "OK" if p.discounted_price == expected else "FAIL"
    print(f"  [{ok}] price={p.price:9.2f}  x0.9  =  {p.discounted_price}")

# ------------------------------------------------------------------ #
#  6. Smart batch generation                                           #
# ------------------------------------------------------------------ #

section("6 - Smart batch generation")

if forge.use_ai:
    print("  (With AI: semantic fields batched into one API call per field)")
else:
    print("  (Without AI: all fields generated by Faker)")

tickets = forge.create_batch(
    SupportTicket,
    count=5,
    context="angry customers complaining about delayed deliveries",
)
print(f"  Generated {len(tickets)} support tickets")
for t in tickets:
    print(f"    #{t.id}  priority={t.priority}  customer={t.customer_name!r}")
    if forge.use_ai:
        print(f"         {t.message[:90]}...")

# ------------------------------------------------------------------ #
#  7. Export                                                           #
# ------------------------------------------------------------------ #

section("7 - Export  (JSON / CSV / SQL)")

with tempfile.TemporaryDirectory() as tmp:
    json_path = os.path.join(tmp, "tickets.json")
    csv_path  = os.path.join(tmp, "tickets.csv")
    sql_path  = os.path.join(tmp, "tickets.sql")

    DataExporter.export(tickets, json_path)
    DataExporter.export(tickets, csv_path)
    DataExporter.export(tickets, sql_path)

    print(f"  JSON  {os.path.getsize(json_path):>7} bytes")
    print(f"  CSV   {os.path.getsize(csv_path):>7} bytes")
    print(f"  SQL   {os.path.getsize(sql_path):>7} bytes")

    lines = Path(sql_path).read_text(encoding="utf-8").splitlines()
    print("\n  SQL preview:")
    for line in lines[:4]:
        print(f"    {line}")

# ------------------------------------------------------------------ #
#  8. Streaming                                                        #
# ------------------------------------------------------------------ #

section("8 - Streaming  (lazy, memory-safe)")

stream_path = os.path.join(tempfile.gettempdir(), "ff_stream_demo.json")
streamed = sum(1 for _ in forge.create_stream(Category, count=10, filename=stream_path))

print(f"  Streamed {streamed} records -> {stream_path}")
print(f"  File size: {os.path.getsize(stream_path)} bytes")

# ------------------------------------------------------------------ #
#  9. Registry stats                                                   #
# ------------------------------------------------------------------ #

section("9 - Registry stats")

for model_name, n in forge.stats().items():
    print(f"  {model_name:20}  {n} records")

# ------------------------------------------------------------------ #
#  Done                                                                #
# ------------------------------------------------------------------ #

print(f"\n{SEP}")
print("  Demo complete!")
if not forge.use_ai:
    print("  Tip: set an AI provider key to see semantic field generation.")
print(SEP)
