"""Channel clip. Two teeth, one top hole. Sizes come from the spec.

The pocket is the clear opening: across the legs, and from the underside
of the top bar down to the tops of the teeth. The band is the print height
when the part lies on its side. The hole is a teardrop toward the face that
is up on the bed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import cadquery as cq

from fabkit.enclosure_box import EnclosureBuild
from fabkit.kernel import box_aabb, intersect_volume
from fabkit.solid import PENETRATE_MM, cut_through, fuse, is_one_valid_solid
from fabkit.validate import walk_path

TEMPLATE_ID = "strip_clip"
TOOTH_SIDE = "both"


def _mm(spec: dict[str, Any], path: str) -> float:
    return float(walk_path(spec, path)["value"])


@dataclass(frozen=True)
class ClipLayout:
    wall: float
    inner_x: float
    inner_z: float
    band: float
    tooth: float
    hole_d: float
    warnings: tuple[str, ...]

    @property
    def outer_x(self) -> float:
        return self.inner_x + 2.0 * self.wall

    @property
    def outer_z(self) -> float:
        return self.inner_z + 2.0 * self.wall

    @property
    def pocket_z0(self) -> float:
        return self.wall

    @property
    def pocket_z1(self) -> float:
        return self.wall + self.inner_z

    @property
    def entrance(self) -> float:
        return self.inner_x - 2.0 * self.tooth


def layout_from_spec(spec: dict[str, Any]) -> ClipLayout:
    wall = float(spec.get("wall_mm") or 4.0)
    inner_x = _mm(spec, "clip.inner_x_mm")
    inner_z = _mm(spec, "clip.inner_z_mm")
    band = _mm(spec, "clip.band_mm")
    tooth = _mm(spec, "clip.tooth_mm")
    hole_d = _mm(spec, "clip.hole_d_mm")
    side = str((spec.get("clip") or {}).get("tooth_side") or TOOTH_SIDE)
    warnings: list[str] = []
    if side != TOOTH_SIDE:
        raise ValueError(f"clip.tooth_side={side!r} is not {TOOTH_SIDE}")
    gap = inner_x - 2.0 * tooth
    if gap <= 1.2:
        warnings.append(
            f"two teeth of {tooth} mm close a {inner_x} mm opening (entrance {gap:.1f} mm)"
        )
    elif tooth > 0 and gap + 1e-9 < inner_x:
        warnings.append(
            f"entrance {gap:.1f} mm is under the {inner_x:.0f} mm pocket: "
            "tilt the body in under the two teeth; it does not drop straight down"
        )
    if hole_d + 2.4 >= band:
        warnings.append(
            f"clip.hole_d_mm={hole_d} leaves under 1.2 mm of the {band} mm band each side"
        )
    return ClipLayout(
        wall=wall,
        inner_x=inner_x,
        inner_z=inner_z,
        band=band,
        tooth=tooth,
        hole_d=hole_d,
        warnings=tuple(warnings),
    )


def _teardrop(lay: ClipLayout) -> cq.Workplane:
    """Ø hole through the top bar, point toward +Y (up once the part lies on its side)."""
    radius = lay.hole_d / 2.0
    cx = lay.outer_x / 2.0
    cy = lay.band / 2.0
    shoulder = radius / math.sqrt(2.0)
    apex_y = cy + radius * math.sqrt(2.0)
    z0 = lay.pocket_z1 - 1.0
    height = lay.wall + 3.0
    bore = (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .center(cx, cy)
        .circle(radius)
        .extrude(height)
    )
    tip = (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .polyline(
            [
                (cx - shoulder, cy + shoulder),
                (cx, apex_y),
                (cx + shoulder, cy + shoulder),
            ]
        )
        .close()
        .extrude(height)
    )
    return fuse(bore, tip)


def _channel(lay: ClipLayout) -> cq.Workplane:
    """One box. Pocket cut. Floor opened between the two teeth. Teardrop hole."""
    part = cq.Workplane("XY").box(lay.outer_x, lay.band, lay.outer_z, centered=False)
    pocket = box_aabb(
        lay.wall,
        -1.0,
        lay.pocket_z0,
        lay.wall + lay.inner_x,
        lay.band + 1.0,
        lay.pocket_z1,
    )
    opened = box_aabb(
        lay.wall + lay.tooth,
        -1.0,
        -1.0,
        lay.wall + lay.inner_x - lay.tooth,
        lay.band + 1.0,
        lay.pocket_z0 + PENETRATE_MM,
    )
    part = cut_through(part, pocket)
    part = cut_through(part, opened)
    part = cut_through(part, _teardrop(lay))
    if not is_one_valid_solid(part):
        raise ValueError("strip clip did not stay one solid after the pocket and hole")
    return part


def _lie_on_side(part: cq.Workplane, outer_z: float) -> cq.Workplane:
    """Side face on the bed. Print Z is the 15 mm band. +Y (teardrop) becomes up."""
    laid = part.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, outer_z, 0))
    if not is_one_valid_solid(laid):
        raise ValueError("strip clip did not stay one solid when laid on its side")
    return laid


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    lay = layout_from_spec(spec)
    if lay.wall + 1e-9 < 1.2:
        raise ValueError(f"wall_mm={lay.wall} is under 1.2 mm (3 perimeters on a 0.4 nozzle)")
    if lay.entrance <= 1.2:
        raise ValueError(
            f"two clip.tooth_mm={lay.tooth} close the {lay.inner_x} mm opening"
        )
    if lay.hole_d + 1e-9 < 1.2:
        raise ValueError(f"clip.hole_d_mm={lay.hole_d} is under 1.2 mm")
    if lay.hole_d + 2.4 > lay.band + 1e-9:
        raise ValueError(
            f"clip.hole_d_mm={lay.hole_d} does not leave 1.2 mm of the {lay.band} mm band"
        )
    tip = lay.band / 2.0 + (lay.hole_d / 2.0) * math.sqrt(2.0)
    if tip > lay.band - 0.8:
        raise ValueError(
            f"teardrop of Ø{lay.hole_d} reaches the {lay.band} mm side face"
        )
    part = _channel(lay)
    printable = _lie_on_side(part, lay.outer_z)
    keepout = box_aabb(
        lay.wall,
        0.0,
        lay.pocket_z0,
        lay.wall + lay.inner_x,
        lay.band,
        lay.pocket_z1,
    )
    keepout_volume = intersect_volume(part, keepout)
    bb = part.val().BoundingBox()
    outer = (float(bb.xlen), float(bb.ylen), float(bb.zlen))
    report = {
        "template_id": TEMPLATE_ID,
        "clip_inner_x_mm": round(lay.inner_x, 3),
        "clip_inner_z_mm": round(lay.inner_z, 3),
        "clip_band_mm": round(lay.band, 3),
        "clip_wall_mm": round(lay.wall, 3),
        "clip_tooth_mm": round(lay.tooth, 3),
        "clip_tooth_side": TOOTH_SIDE,
        "clip_hole_d_mm": round(lay.hole_d, 3),
        "clip_hole": "teardrop-45",
        "clip_outer_x_mm": round(lay.outer_x, 3),
        "clip_outer_z_mm": round(lay.outer_z, 3),
        "clip_entrance_mm": round(lay.entrance, 3),
        "clip_print_pose": "side-down",
        "clip_print_z_mm": round(lay.band, 3),
    }
    return EnclosureBuild(
        base=part,
        lid=part,
        assembled=part,
        printable=printable,
        keepout=keepout,
        keepout_volume=keepout_volume,
        outer=outer,
        cavity_lw=(round(lay.inner_x, 3), round(lay.inner_z, 3)),
        warnings=list(lay.warnings),
        report=report,
    )
