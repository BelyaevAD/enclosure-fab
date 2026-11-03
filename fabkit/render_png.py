"""Off-screen isometric PNG via cadquery.vis (VTK). Call only from export_child."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cadquery import Assembly, Color, Workplane
from cadquery.vis import show

from fabkit.enclosure_box import EnclosureBuild

_SIZE = dict(width=960, height=720)
_PETG = Color(0.70, 0.78, 0.76, 1.0)


def render_previews(
    parts: EnclosureBuild,
    dest_dir: Path,
    stem: str,
    *,
    button_face: str | None = None,
) -> dict[str, str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    assembled_png = dest_dir / f"{stem}-assembled.png"
    print_png = dest_dir / f"{stem}-print.png"
    _shot(parts.assembled, assembled_png, camera=_camera_from_plus_x(parts.assembled))
    _shot(
        parts.printable,
        print_png,
        camera=dict(roll=-25.0, elevation=-35.0, azimuth=15.0, zoom=1.28),
    )
    files = {"png_assembled": str(assembled_png), "png_print": str(print_png)}
    if button_face:
        button_png = dest_dir / f"{stem}-button.png"
        _shot(
            parts.assembled,
            button_png,
            camera=_camera_from_face(parts.assembled, button_face),
        )
        files["png_button"] = str(button_png)
    return files


def _look_at(
    wp: Workplane,
    dx: float,
    dy: float,
    dz: float,
    *,
    zoom: float = 1.12,
    fx: float = 0.5,
    fy: float = 0.5,
    fz: float = 0.5,
) -> dict[str, Any]:
    bb = wp.val().BoundingBox()
    cx = bb.xmin + fx * (bb.xmax - bb.xmin)
    cy = bb.ymin + fy * (bb.ymax - bb.ymin)
    cz = bb.zmin + fz * (bb.zmax - bb.zmin)
    span = max(bb.xlen, bb.ylen, bb.zlen, 1.0)
    dist = span * 2.35
    return {
        "position": (cx + dist * dx, cy + dist * dy, cz + dist * dz),
        "focus": (cx, cy, cz),
        "viewup": (0.0, 0.0, 1.0),
        "roll": 0.0,
        "elevation": 0.0,
        "azimuth": 0.0,
        "zoom": zoom,
    }


def _camera_from_plus_x(wp: Workplane) -> dict[str, Any]:
    """Look from +X/+Y/+Z so the USB wall (+X) and lid (+Z) are both readable."""
    return _look_at(wp, 0.98, 0.70, 0.55, zoom=1.08)


def _camera_from_face(wp: Workplane, face: str) -> dict[str, Any]:
    """Hero the flex-tab wall. USB ISO hides −Y."""
    if face == "minus_y":
        return _look_at(wp, 0.16, -1.0, 0.10, zoom=2.12, fx=0.80, fy=0.02, fz=0.46)
    if face == "plus_y":
        return _look_at(wp, 0.16, 1.0, 0.10, zoom=2.12, fx=0.80, fy=0.98, fz=0.46)
    if face == "minus_x":
        return _look_at(wp, -1.0, 0.16, 0.10, zoom=2.12, fx=0.02, fy=0.45, fz=0.46)
    return _look_at(wp, 0.98, 0.70, 0.55, zoom=1.08)


def _shot(wp: Workplane, dest: Path, *, camera: dict[str, Any]) -> None:
    show(
        Assembly(wp, color=_PETG),
        screenshot=str(dest),
        interact=False,
        edges=True,
        trihedron=True,
        specular=True,
        bgcolor=(0.94, 0.95, 0.96),
        gradient=True,
        tolerance=1e-4,
        **camera,
        **_SIZE,
    )
    if not dest.is_file() or dest.stat().st_size < 100:
        raise RuntimeError(f"PNG render produced no file: {dest}")
