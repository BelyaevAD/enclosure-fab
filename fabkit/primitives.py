"""Named enclosure primitives and upstream recipe pins.

Live geometry stays in fabkit. This catalog is what MCP `list_primitives`
returns so the agent copies a named part instead of inventing a button or
grid, and instead of vendoring OpenSCAD (ADR 047).
"""

from __future__ import annotations

from typing import Any

from fabkit.io_yaml import load_yaml
from fabkit.paths import ZONE_ROOT

PRIMITIVES_DIR = ZONE_ROOT / "library" / "primitives"
UPSTREAM_DIR = ZONE_ROOT / "library" / "upstream"
CATALOG_PATH = PRIMITIVES_DIR / "catalog.yaml"
UPSTREAM_PATH = UPSTREAM_DIR / "pins.yaml"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if hasattr(value, "isoformat") and not isinstance(value, (str, bytes)):
        return value.isoformat()
    return value


def list_primitives() -> dict[str, Any]:
    catalog = load_yaml(CATALOG_PATH)
    pins = load_yaml(UPSTREAM_PATH) if UPSTREAM_PATH.is_file() else {}
    return _jsonable(
        {
            "policy": str(catalog.get("policy") or "").strip(),
            "primitives": list(catalog.get("primitives") or []),
            "upstream": list(pins.get("pins") or []),
            "index": "library/primitives/INDEX.md",
            "upstream_index": "library/upstream/INDEX.md",
        }
    )
