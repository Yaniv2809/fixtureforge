"""
FixtureForge MCP Server — exposes Forge as AI-callable tools via MCP stdio transport.

Usage (add to Claude Desktop config):
    {
      "mcpServers": {
        "fixtureforge": {
          "command": "fixtureforge-mcp"
        }
      }
    }

Or run directly:
    python -m fixtureforge.mcp_server
"""
from __future__ import annotations

import ast
import json
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.stdio import stdio_server

server = MCPServer(
    name="fixtureforge",
    description=(
        "Generate deterministic Pydantic test fixtures. "
        "Fields are auto-routed: id/fk → counters, name/email → Faker, bio/description → AI."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_fields(fields: Dict[str, str]):
    """
    Convert a {field_name: type_str} dict into a pydantic create_model()-compatible
    dict of (type, default) tuples.

    Supported type strings: int, str, float, bool, list, dict,
    Optional[X], Literal['a','b'], and any bare Python type name.
    """
    import enum
    import typing
    from datetime import date, datetime
    from decimal import Decimal
    from typing import Any, Optional
    from uuid import UUID

    from pydantic import create_model

    _BUILTINS = {
        "int": int, "str": str, "float": float, "bool": bool,
        "list": list, "dict": dict, "any": Any,
        "date": date, "datetime": datetime,
        "decimal": Decimal, "uuid": UUID,
    }

    field_defs: Dict[str, Any] = {}
    for name, type_str in fields.items():
        t = _resolve_type(type_str.strip(), _BUILTINS)
        field_defs[name] = (t, ...)

    return field_defs


def _resolve_type(type_str: str, builtins: Dict[str, Any]) -> Any:
    """Parse a type string into a Python type."""
    import typing
    from typing import Literal, Optional, Union

    lower = type_str.lower()

    # Simple builtin
    if lower in builtins:
        return builtins[lower]

    # Optional[X]
    if lower.startswith("optional[") and lower.endswith("]"):
        inner = type_str[9:-1]
        return Optional[_resolve_type(inner, builtins)]  # type: ignore[misc]

    # Literal['a', 'b', ...]
    if lower.startswith("literal[") and lower.endswith("]"):
        inner = type_str[8:-1]
        try:
            values = [v.strip().strip("'\"") for v in inner.split(",")]
            return Literal[tuple(values)]  # type: ignore[misc]
        except Exception:
            return str

    # List[X]
    if lower.startswith("list[") and lower.endswith("]"):
        return list

    # Dict[X, Y]
    if lower.startswith("dict[") and lower.endswith("]"):
        return dict

    return str  # fallback


def _build_model(fields: Dict[str, str]):
    """Dynamically build a Pydantic BaseModel class from a field dict."""
    from pydantic import create_model

    field_defs = _parse_fields(fields)
    return create_model("DynamicModel", **field_defs)


def _records_to_json(records: list) -> str:
    """Serialize a list of Pydantic model instances to a JSON string."""
    result = []
    for r in records:
        try:
            result.append(r.model_dump())
        except Exception:
            result.append(vars(r))
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def generate(
    fields: Dict[str, str],
    count: int = 10,
    seed: int = 42,
    use_ai: bool = False,
    context: Optional[str] = None,
) -> str:
    """
    Generate N records for a model described by a field dict.

    Args:
        fields:  mapping of field_name → type_str, e.g. {"id": "int", "name": "str", "bio": "str"}
        count:   number of records to generate (default 10)
        seed:    random seed for reproducibility (default 42)
        use_ai:  set True to use an LLM for semantic fields (requires an AI provider env var)
        context: optional context hint for AI generation (e.g. "SaaS platform users")

    Returns:
        JSON array of generated records.
    """
    from fixtureforge import Forge

    model = _build_model(fields)
    forge = Forge(use_ai=use_ai, seed=seed)
    records = forge.create_batch(model, count=count, context=context)
    return _records_to_json(records)


def swarm(
    models: List[Dict[str, str]],
    names: List[str],
    counts: Optional[List[int]] = None,
    seed: int = 42,
    use_ai: bool = False,
    contexts: Optional[List[Optional[str]]] = None,
) -> str:
    """
    Generate multiple models in parallel with shared AI cache.

    Args:
        models:   list of field dicts, one per model
        names:    list of human-readable names for each model
        counts:   records per model (default 10 each)
        seed:     random seed
        use_ai:   enable AI for semantic fields
        contexts: optional context strings per model

    Returns:
        JSON object mapping model name → array of records.
    """
    from fixtureforge import Forge

    if len(models) != len(names):
        return json.dumps({"error": "models and names must have the same length"})

    counts = counts or [10] * len(models)
    contexts = contexts or [None] * len(models)

    pydantic_models = []
    for i, (field_dict, name) in enumerate(zip(models, names)):
        from pydantic import create_model
        field_defs = _parse_fields(field_dict)
        # Use name as the class name so the swarm result keys match
        m = create_model(name, **field_defs)
        pydantic_models.append(m)

    forge = Forge(use_ai=use_ai, seed=seed)
    results = forge.swarm(pydantic_models, counts=counts, contexts=contexts)

    output = {}
    for model_name, records in results.items():
        output[model_name] = json.loads(_records_to_json(records))

    return json.dumps(output, indent=2, default=str)


def add_rule(category: str, rule: str) -> str:
    """
    Persist a domain rule that FixtureForge will inject into every AI prompt.

    Args:
        category: short label for the rule domain (e.g. "financial", "user", "orders")
        rule:     plain-English rule, e.g. "Users under 18 get restricted account type"

    Returns:
        Confirmation message.
    """
    from fixtureforge import Forge

    forge = Forge()
    forge.memory.add_rule(category, rule)
    return f"Rule added to '{category}': {rule}"


def export_records(
    fields: Dict[str, str],
    count: int = 10,
    seed: int = 42,
    filename: str = "fixtures.json",
) -> str:
    """
    Generate records and export them to a file (JSON, CSV, or SQL).

    Args:
        fields:   field dict (same as generate)
        count:    number of records
        seed:     random seed
        filename: output path; format inferred from extension (.json/.csv/.sql)

    Returns:
        Confirmation message with file path.
    """
    from fixtureforge import Forge
    from fixtureforge.core.exporter import DataExporter

    model = _build_model(fields)
    forge = Forge(use_ai=False, seed=seed)
    records = forge.create_batch(model, count=count)
    DataExporter.export(records, filename)
    return f"Exported {count} records to {filename}"


# ---------------------------------------------------------------------------
# Register tools
# ---------------------------------------------------------------------------

server.add_tool(
    generate,
    name="generate",
    description=(
        "Generate N test records for a Pydantic model described by a field dict. "
        "Fields are auto-routed: id/fk→counters, name/email→Faker, bio/description→AI. "
        "Example: fields={\"id\":\"int\",\"name\":\"str\",\"bio\":\"str\"}, count=5"
    ),
)

server.add_tool(
    swarm,
    name="swarm",
    description=(
        "Generate multiple models in parallel with shared AI cache (~90% cheaper per extra model). "
        "Example: models=[{\"id\":\"int\",\"name\":\"str\"},{\"id\":\"int\",\"product\":\"str\"}], "
        "names=[\"User\",\"Order\"], counts=[10,50]"
    ),
)

server.add_tool(
    add_rule,
    name="add_rule",
    description=(
        "Add a persistent domain rule that FixtureForge injects into every AI prompt. "
        "Example: category='financial', rule='Users under 18 get restricted account type'"
    ),
)

server.add_tool(
    export_records,
    name="export",
    description=(
        "Generate records and save them to a file. "
        "Format is inferred from the filename extension (.json, .csv, or .sql). "
        "Example: fields={\"id\":\"int\",\"name\":\"str\"}, count=100, filename=\"users.json\""
    ),
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    import asyncio
    asyncio.run(_run())


if __name__ == "__main__":
    main()
