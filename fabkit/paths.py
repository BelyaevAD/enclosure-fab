from __future__ import annotations

from pathlib import Path

ZONE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ZONE_ROOT / "schema"
TEMPLATES_DIR = ZONE_ROOT / "templates"
LIBRARY_DIR = ZONE_ROOT / "library" / "boards"
PROJECTS_DIR = ZONE_ROOT / "projects"
FIXTURES_DIR = ZONE_ROOT / "fixtures"
WORK_DIR = ZONE_ROOT / ".work"
GENERATED_DIR = WORK_DIR / "generated"
LAST_GATE_PATH = WORK_DIR / "last_gate.json"

# Linear deflection for STL *and* 3MF. CadQuery export() defaults to 0.1 mm
# unless this is passed as the ``tolerance=`` argument (not ``opt=``).
STL_TOLERANCE = 0.001
STL_ANGULAR_TOLERANCE = 0.1

# projects/<family>/spec.yaml  or  projects/<family>/<version>/spec.yaml
_SPEC_DEPTH = (1, 2)


def _reserved_name(name: str) -> bool:
    return name.startswith("_") or name.startswith(".")


def iter_project_specs() -> list[Path]:
    """Live SKUs: singleton family or one version folder under a family."""
    if not PROJECTS_DIR.is_dir():
        return []
    found: list[Path] = []
    root = PROJECTS_DIR.resolve()
    for spec in root.glob("*/spec.yaml"):
        if _reserved_name(spec.parent.name):
            continue
        found.append(spec.resolve())
    for spec in root.glob("*/*/spec.yaml"):
        family, version = spec.parent.relative_to(root).parts
        if _reserved_name(family) or _reserved_name(version):
            continue
        found.append(spec.resolve())
    return sorted(set(found))


def project_dir_for_spec(spec_path: Path) -> Path | None:
    """Directory that owns spec.yaml (version folder, or the family if singleton)."""
    spec_path = spec_path.resolve()
    try:
        relative = spec_path.relative_to(PROJECTS_DIR.resolve())
    except ValueError:
        return None
    if relative.name != "spec.yaml":
        return None
    depth = len(relative.parts) - 1
    if depth not in _SPEC_DEPTH:
        return None
    if any(_reserved_name(part) for part in relative.parts[:-1]):
        return None
    return spec_path.parent


def project_ref(spec_path: Path) -> str | None:
    """CLI id: `family` or `family/version`."""
    project = project_dir_for_spec(spec_path)
    if project is None:
        return None
    return project.relative_to(PROJECTS_DIR.resolve()).as_posix()


def default_generated_dir(spec_path: Path, mode: str) -> Path:
    project = project_dir_for_spec(spec_path)
    if project is not None:
        return project / ".work" / "generated" / mode
    return GENERATED_DIR / mode
