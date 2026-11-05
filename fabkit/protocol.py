from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from fabkit.io_yaml import load_yaml
from fabkit.paths import (
    LIBRARY_DIR,
    PROJECTS_DIR,
    SCHEMA_DIR,
    TEMPLATES_DIR,
    ZONE_ROOT,
    iter_project_specs,
    project_ref,
)
from fabkit.validate import (
    FIT_CRITICAL_PATHS,
    RING_FIT_CRITICAL,
    SHELL_FIT_CRITICAL,
    STRIP_FIT_CRITICAL,
    TRAY_FIT_CRITICAL,
    MAGNET_BOX_FIT_CRITICAL,
)


def protocol(family: str | None = None) -> dict[str, Any]:
    raw = load_yaml(SCHEMA_DIR / "protocols.yaml")
    families: dict[str, Any] = raw.get("families") or {}
    if family:
        if family not in families:
            known = ", ".join(sorted(families))
            raise KeyError(f"unknown family {family!r}; known: {known}")
        families = {family: families[family]}
    out = {
        "coordinate_system": raw.get("coordinate_system", "").strip(),
        "ventilation": raw.get("ventilation", "").strip(),
        "printer": raw.get("printer", "").strip(),
        "fit_critical": list(FIT_CRITICAL_PATHS),
        "families": {},
    }
    for name, info in families.items():
        extra = list(info.get("extra") or [])
        critical = list(info.get("fit_critical") or FIT_CRITICAL_PATHS)
        if name == "g202" and not info.get("fit_critical"):
            critical = list(SHELL_FIT_CRITICAL)
        if name == "g202_panel" and not info.get("fit_critical"):
            critical = list(TRAY_FIT_CRITICAL)
        if name == "magnet_box" and not info.get("fit_critical"):
            critical = list(MAGNET_BOX_FIT_CRITICAL)
        if name == "ring_yoke" and not info.get("fit_critical"):
            critical = list(RING_FIT_CRITICAL)
        if name == "strip_clip" and not info.get("fit_critical"):
            critical = list(STRIP_FIT_CRITICAL)
        row = {
            "required_fields": critical + extra,
            "notes": info.get("notes", ""),
        }
        cs = info.get("coordinate_system")
        if cs:
            row["coordinate_system"] = str(cs).strip()
        out["families"][name] = row
    if family and len(out["families"]) == 1:
        only = next(iter(out["families"].values()))
        out["fit_critical"] = list(only["required_fields"])
    return out


def list_templates() -> list[str]:
    names: list[str] = []
    if TEMPLATES_DIR.is_dir():
        names = sorted(
            path.name for path in TEMPLATES_DIR.iterdir() if path.is_dir() and not path.name.startswith(".")
        )
    if "enclosure_box" not in names:
        names.append("enclosure_box")
    return names


def iter_spec_files() -> Iterator[tuple[Path, str]]:
    if LIBRARY_DIR.is_dir():
        for path in sorted(LIBRARY_DIR.glob("*.yaml")):
            yield path, "stub"
    for path in iter_project_specs():
        yield path, "project"


def resolve_spec_path(spec_path: str | Path) -> Path:
    path = Path(spec_path)
    if path.is_file():
        return path.resolve()
    if path.is_dir() and (path / "spec.yaml").is_file():
        return (path / "spec.yaml").resolve()
    zone_rel = ZONE_ROOT / path
    if zone_rel.is_file():
        return zone_rel.resolve()
    if zone_rel.is_dir() and (zone_rel / "spec.yaml").is_file():
        return (zone_rel / "spec.yaml").resolve()
    raw = str(spec_path).replace("\\", "/").removesuffix(".yaml")
    slug = path.name.removesuffix(".yaml")
    if slug == "spec":
        slug = path.parent.name
    for alt in (
        PROJECTS_DIR / raw / "spec.yaml",
        PROJECTS_DIR / slug / "spec.yaml",
    ):
        if alt.is_file():
            return alt.resolve()
    family_dir = PROJECTS_DIR / slug
    if family_dir.is_dir() and not (family_dir / "spec.yaml").is_file():
        versions = sorted(
            path
            for path in family_dir.glob("*/spec.yaml")
            if path.is_file() and not path.parent.name.startswith("_")
        )
        if len(versions) == 1:
            return versions[0].resolve()
    for alt in (
        LIBRARY_DIR / str(spec_path),
        LIBRARY_DIR / f"{spec_path}.yaml",
        LIBRARY_DIR / f"{slug}.yaml",
    ):
        if alt.is_file():
            return alt.resolve()
    for found, kind in iter_spec_files():
        if kind != "project":
            continue
        ref = project_ref(found)
        if ref == raw or ref == slug:
            return found.resolve()
        try:
            if load_yaml(found).get("board_id") in {raw, slug}:
                return found.resolve()
        except (OSError, ValueError):
            continue
    for found, kind in iter_spec_files():
        if kind != "stub":
            continue
        try:
            if load_yaml(found).get("board_id") == slug:
                return found.resolve()
        except (OSError, ValueError):
            continue
    known = [project_ref(p) for p in iter_project_specs()]
    raise FileNotFoundError(f"{spec_path}; known projects: {', '.join(x for x in known if x)}")


def list_boards() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    from fabkit.validate import unconfirmed_fit_critical

    for path, kind in iter_spec_files():
        data = load_yaml(path)
        try:
            unconfirmed = unconfirmed_fit_critical(data)
        except Exception:
            unconfirmed = ["<invalid>"]
        rows.append(
            {
                "board_id": data.get("board_id", path.parent.name if kind == "project" else path.stem),
                "project": project_ref(path) if kind == "project" else None,
                "family": data.get("family"),
                "kind": kind,
                "revision": data.get("revision", "unknown"),
                "path": str(path),
                "unconfirmed_fit_critical": unconfirmed,
            }
        )
    return rows
