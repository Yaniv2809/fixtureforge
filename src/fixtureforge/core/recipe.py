"""
RecipeRunner — execute YAML-based data generation scenarios.

Recipe format:
  steps:
    - model: Product
      count: 100
      context: "E-commerce electronics store"
      fields:
        id:          int
        name:        str
        description: str   # → SEMANTIC → AI
        price:       float
        in_stock:    bool

    - model: Review
      count: 500
      context: "Verified buyer reviews for electronics"
      fields:
        id:         int
        product_id: int    # → STRUCTURAL → FK lookup
        rating:     float
        comment:    str    # → SEMANTIC → AI
"""
from typing import Any, Dict, List, Optional, Type

import yaml
from pydantic import Field, create_model


class RecipeRunner:
    """Parse a YAML recipe file and execute generation steps."""

    _TYPE_MAP: Dict[str, type] = {
        "int":   int,
        "str":   str,
        "float": float,
        "bool":  bool,
        "list":  list,
        "dict":  dict,
    }

    def __init__(self, recipe_path: str, forge=None):
        """
        Parameters
        ----------
        recipe_path : str
            Path to the YAML recipe file.
        forge : Forge, optional
            A pre-configured Forge instance. When omitted, the package-level
            ``forge`` singleton is used (auto-detected provider).
        """
        self.recipe_path = recipe_path
        # Lazy import avoids circular dependency
        if forge is None:
            from fixtureforge import forge as _forge  # noqa: PLC0415
            self._forge = _forge
        else:
            self._forge = forge

    def run(self) -> Dict[str, List[Any]]:
        """Execute all steps in the recipe and return the generated data."""
        with open(self.recipe_path, "r", encoding="utf-8") as fh:
            recipe = yaml.safe_load(fh)

        print(f"📜 Running recipe: {self.recipe_path}")

        results: Dict[str, List[Any]] = {}
        for step in recipe.get("steps", []):
            model_name: str = step["model"]
            count: int = step.get("count", 1)
            context: Optional[str] = step.get("context")
            fields_cfg: Dict[str, str] = step.get("fields", {})

            dynamic_model = self._build_model(model_name, fields_cfg)

            print(f"\n🏗️  Step: {count} × {model_name}")
            if context:
                print(f"   🎬 Context: {context}")

            generated = self._forge.create_batch(
                dynamic_model, count=count, context=context
            )

            results[model_name] = generated
            self._print_sample(generated)

        return results

    # ------------------------------------------------------------------

    def _build_model(self, name: str, fields_cfg: Dict[str, str]) -> Type:
        """Dynamically construct a Pydantic model from YAML field definitions."""
        pydantic_fields = {
            field_name: (
                self._TYPE_MAP.get(type_str, str),
                Field(description=f"{field_name} ({type_str})"),
            )
            for field_name, type_str in fields_cfg.items()
        }
        return create_model(name, **pydantic_fields)

    @staticmethod
    def _print_sample(data: List[Any], limit: int = 3) -> None:
        for item in data[:limit]:
            print(f"   ✅ {item.model_dump()}")
