"""
Model introspection and field extraction.

Supports:
  - Pydantic v2 BaseModel (regular fields + @computed_field)
  - SQLAlchemy ORM models (optional dependency)
"""
from typing import Any, Dict, List, Type, get_args, get_origin

from pydantic import BaseModel

# --- SQLAlchemy optional support ---
try:
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy.orm import DeclarativeMeta
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    DeclarativeMeta = type("DeclarativeMeta", (), {})
    sa_inspect = None


class FieldInfo:
    """Normalised representation of a single model field."""

    def __init__(
        self,
        name: str,
        field_type: Type,
        required: bool = True,
        default: Any = None,
        constraints: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ):
        self.name = name
        self.field_type = field_type
        self.required = required
        self.default = default
        self.constraints = constraints or {}
        self.metadata = metadata or {}

    @property
    def type_name(self) -> str:
        """Human-readable type name, e.g. 'str', 'Optional[int]'."""
        try:
            origin = get_origin(self.field_type)
            if origin:
                args = get_args(self.field_type)
                if args:
                    args_str = ", ".join(
                        a.__name__ if hasattr(a, "__name__") else str(a)
                        for a in args
                    )
                    return f"{origin.__name__}[{args_str}]"
                return origin.__name__
            return self.field_type.__name__
        except Exception:
            return str(self.field_type)


class ModelParser:
    """Parse Pydantic v2 models into a list of FieldInfo objects."""

    @classmethod
    def parse(cls, model: Type[BaseModel]) -> List[FieldInfo]:
        fields: List[FieldInfo] = []

        # --- Regular fields ---
        for field_name, field_info in model.model_fields.items():
            field_type = field_info.annotation
            required = field_info.is_required()
            default = field_info.default if not required else None

            # Extract numeric / string constraints from Pydantic metadata annotations
            constraints: Dict[str, Any] = {}
            for meta in (field_info.metadata or []):
                for attr in ("ge", "le", "gt", "lt", "min_length", "max_length", "pattern"):
                    val = getattr(meta, attr, None)
                    if val is not None:
                        constraints[attr] = val

            field_meta: Dict[str, Any] = {
                "description": field_info.description,
                "examples": getattr(field_info, "examples", None),
                "computed": False,
            }

            fields.append(
                FieldInfo(
                    name=field_name,
                    field_type=field_type,
                    required=required,
                    default=default,
                    constraints=constraints,
                    metadata=field_meta,
                )
            )

        # --- Pydantic v2 @computed_field properties ---
        # These derive their value from other fields; we register them so the
        # router can classify them as COMPUTED and the generator can skip them.
        computed_fields = getattr(model, "model_computed_fields", {})
        for field_name, computed_info in computed_fields.items():
            return_type = getattr(computed_info, "return_type", None) or str
            fields.append(
                FieldInfo(
                    name=field_name,
                    field_type=return_type,
                    required=False,
                    default=None,
                    constraints={},
                    metadata={
                        "description": getattr(computed_info, "description", None),
                        "computed": True,
                    },
                )
            )

        return fields
