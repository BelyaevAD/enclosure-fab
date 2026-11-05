"""Prove this generate wrote meshes, and flag live SKUs older than fabkit."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fabkit.paths import ZONE_ROOT, default_generated_dir, iter_project_specs, project_ref
from fabkit.validate import load_spec

THIS_RUN_SLACK_S = 2.0
SOURCE_SLACK_S = 1.0
FABKIT = ZONE_ROOT / "fabkit"

_SNAP = (
    "build.py",
    "enclosure_snap.py",
    "snap_geom.py",
    "fit.py",
    "solid.py",
    "kernel.py",
)
_BOX = ("build.py", "enclosure_box.py", "fit.py", "solid.py", "kernel.py")
_SHELL = ("build.py", "enclosure_shell.py", "fit.py", "solid.py", "kernel.py")
_TRAY = ("build.py", "enclosure_tray.py", "enclosure_shell.py", "fit.py", "solid.py", "kernel.py")
_MAGNET_BOX = (
    "build.py",
    "enclosure_magnet_box.py",
    "enclosure_tray.py",
    "enclosure_shell.py",
    "fit.py",
    "solid.py",
    "kernel.py",
)
_RING = ("build.py", "ring_yoke.py", "solid.py", "kernel.py")
_STRIP = ("build.py", "strip_clip.py", "solid.py", "kernel.py")


def utc_stamp(ts: float | None = None) -> str:
    if ts is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_teardown_exit(code: int) -> bool:
    """Windows VTK/OCP heap crash after a successful write."""
    return (code & 0xFFFFFFFF) in {0xC0000005, 0xC0000374}


def missing_or_stale(files: dict[str, Any], t0: float) -> list[str]:
    """Keys whose path is missing, empty, or older than this generate() call."""
    bad: list[str] = []
    floor = t0 - THIS_RUN_SLACK_S
    for key, raw in files.items():
        path = Path(str(raw))
        if not path.is_file() or path.stat().st_size <= 0:
            bad.append(key)
            continue
        if path.stat().st_mtime < floor:
            bad.append(key)
    return bad


def mesh_sources(spec: dict[str, Any]) -> list[Path]:
    template = spec.get("template_id")
    names: tuple[str, ...]
    if template == "enclosure_snap":
        names = _SNAP
        extra: list[str] = []
        if (spec.get("case") or {}).get("vents"):
            extra.append("vents.py")
        if spec.get("headers"):
            extra.append("headers.py")
        names = names + tuple(extra)
    elif template == "enclosure_box":
        names = _BOX
    elif template == "enclosure_shell":
        names = _SHELL
    elif template == "enclosure_tray":
        names = _TRAY
    elif template == "enclosure_magnet_box":
        names = _MAGNET_BOX
    elif template == "ring_yoke":
        names = _RING
    elif template == "strip_clip":
        names = _STRIP
    else:
        return []
    return [FABKIT / name for name in names if (FABKIT / name).is_file()]


def newest_source(spec: dict[str, Any]) -> tuple[Path, float] | None:
    paths = mesh_sources(spec)
    if not paths:
        return None
    newest = max(paths, key=lambda p: p.stat().st_mtime)
    return newest, newest.stat().st_mtime


def _preview_mesh(spec_path: Path, spec: dict[str, Any]) -> Path:
    dest = default_generated_dir(spec_path, "preview")
    board = spec.get("board_id", "board")
    template = spec.get("template_id", "enclosure_box")
    return dest / f"PREVIEW-{board}-{template}.3mf"


def stale_live_previews(exclude: Path | None = None) -> list[dict[str, str]]:
    """Live SKUs whose committed-side 3MF is older than the cutter that feeds them."""
    skip = exclude.resolve() if exclude is not None else None
    out: list[dict[str, str]] = []
    for spec_path in iter_project_specs():
        if skip is not None and spec_path == skip:
            continue
        try:
            spec = load_spec(spec_path)
        except (OSError, ValueError, KeyError):
            continue
        source = newest_source(spec)
        if source is None:
            continue
        src_path, src_mtime = source
        mesh = _preview_mesh(spec_path, spec)
        if not mesh.is_file():
            continue
        if mesh.stat().st_mtime + SOURCE_SLACK_S >= src_mtime:
            continue
        ref = project_ref(spec_path) or spec_path.parent.name
        out.append(
            {
                "id": ref,
                "mesh_at": utc_stamp(mesh.stat().st_mtime),
                "source": src_path.name,
                "source_at": utc_stamp(src_mtime),
            }
        )
    return out


def file_facts(files: dict[str, Any]) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    for key, raw in files.items():
        path = Path(str(raw))
        if not path.is_file():
            facts[key] = {"path": str(path), "missing": True}
            continue
        stat = path.stat()
        facts[key] = {
            "path": str(path),
            "bytes": stat.st_size,
            "mtime": utc_stamp(stat.st_mtime),
        }
    return facts


def freshness_report(result: dict[str, Any]) -> str:
    lines = [f"generated_at: {result.get('generated_at') or '(missing)'}"]
    files = result.get("files") or {}
    mesh = files.get("3mf")
    if mesh:
        path = Path(str(mesh))
        if path.is_file():
            stat = path.stat()
            lines.append(
                f"3mf: {path.name}  {stat.st_size} bytes  {utc_stamp(stat.st_mtime)}"
            )
        else:
            lines.append(f"3mf: missing ({path})")
    else:
        lines.append("3mf: missing")
    for key, label in (
        ("preview_png", "preview.png"),
        ("preview_print_png", "preview-print.png"),
        ("preview_button_png", "preview-button.png"),
    ):
        raw = result.get(key)
        if not raw:
            continue
        path = Path(str(raw))
        if path.is_file():
            stat = path.stat()
            lines.append(
                f"{label}: {stat.st_size} bytes  {utc_stamp(stat.st_mtime)}"
            )
        else:
            lines.append(f"{label}: missing ({path})")
    siblings = result.get("stale_siblings") or []
    if siblings:
        lines.append("stale_siblings: " + ", ".join(siblings))
    else:
        lines.append("stale_siblings: (none)")
    return "\n".join(lines)
