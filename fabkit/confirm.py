from __future__ import annotations

from pathlib import Path

from fabkit.io_yaml import dump_yaml, load_yaml
from fabkit.validate import walk_path


def confirm_field(spec_path: Path, dotted: str, *, i_measured: bool) -> dict:
    if not i_measured:
        raise PermissionError("refusing to set confirmed without --i-measured")
    spec = load_yaml(spec_path)
    node = walk_path(spec, dotted)
    if not isinstance(node, dict) or "confirmed" not in node:
        raise KeyError(f"{dotted} is not a measured/AABB node with confirmed")
    node["confirmed"] = True
    dump_yaml(spec_path, spec)
    return {"path": dotted, "confirmed": True, "spec": str(spec_path)}
