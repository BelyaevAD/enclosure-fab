"""Two coplanar C-rings. One snaps onto a bar, the other takes a stick.

Spec circumferences are the original pipe estimate (π × stated diameter).
The hole is that diameter plus BORE_EXTRA_MM, then trimmed after the trial
print (BAR_HOLE_TRIM_MM / HANDLE_HOLE_TRIM_MM). Both hoops lie in XY so the
20 mm band is the part height. Mouths open on opposite ends (−X and +X).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import cadquery as cq

from fabkit.enclosure_box import EnclosureBuild
from fabkit.kernel import intersect_volume
from fabkit.solid import cut_through, fuse, is_one_valid_solid
from fabkit.validate import walk_path

TEMPLATE_ID = "ring_yoke"
# How far each bore nicks the other ring so the union is not a coplanar kiss.
JOINT_BITE_MM = 0.8
# Sphere on each tip: rounds the entry (sketch nubs) without filling the mouth.
BULB_R_MM = 2.0
BULB_INTO_WALL_MM = 1.4
# Both hoops in XY (axis Z). Mouths open outward on opposite ends.
# Bar gap toward −X. Handle gap toward +X.
BAR_GAP_DEG = 180.0
HANDLE_GAP_DEG = 0.0
# Diametral growth that the first preview added over the stated pipe.
BORE_EXTRA_MM = 2.5
# Trial print 2026-09-22: holes ran large. Large: operator said 3, maybe 4.
BAR_HOLE_TRIM_MM = 4.0
HANDLE_HOLE_TRIM_MM = 3.0
# A pipe this far under the stated diameter must still be wider than the mouth.
UNDERSIZE_HOLD_MM = 2.5


def _mm(spec: dict[str, Any], path: str) -> float:
    return float(walk_path(spec, path)["value"])


def _ring_wall(spec: dict[str, Any], name: str, fallback: float) -> float:
    ring = (spec.get("rings") or {}).get(name) or {}
    raw = ring.get("wall_mm")
    if raw is None:
        return fallback
    return float(raw)


def bore_diameter(circumference_mm: float) -> float:
    return circumference_mm / math.pi


@dataclass(frozen=True)
class RingLayout:
    wall: float
    bar_wall: float
    handle_wall: float
    band: float
    bar_pipe: float
    handle_pipe: float
    bar_bore: float
    handle_bore: float
    bar_mouth: float
    handle_mouth: float
    bite: float
    x0: float
    warnings: tuple[str, ...]


def layout_from_spec(spec: dict[str, Any]) -> RingLayout:
    wall = float(spec.get("wall_mm") or 4.0)
    bar_wall = _ring_wall(spec, "bar", wall)
    handle_wall = _ring_wall(spec, "handle", wall)
    band = _mm(spec, "rings.band_mm")
    bar_pipe = bore_diameter(_mm(spec, "rings.bar.circumference_mm"))
    handle_pipe = bore_diameter(_mm(spec, "rings.handle.circumference_mm"))
    bar_mouth = _mm(spec, "rings.bar.mouth_mm")
    handle_mouth = _mm(spec, "rings.handle.mouth_mm")
    bar_bore = bar_pipe + BORE_EXTRA_MM - BAR_HOLE_TRIM_MM
    handle_bore = handle_pipe + BORE_EXTRA_MM - HANDLE_HOLE_TRIM_MM
    bite = min(JOINT_BITE_MM, min(bar_wall, handle_wall) * 0.3)
    bar_r = bar_bore / 2.0
    handle_r = handle_bore / 2.0
    x0 = (bar_r + bar_wall) + handle_r - bite
    warnings: list[str] = []
    for label, mouth, pipe, bore in (
        ("rings.bar.mouth_mm", bar_mouth, bar_pipe, bar_bore),
        ("rings.handle.mouth_mm", handle_mouth, handle_pipe, handle_bore),
    ):
        small = pipe - UNDERSIZE_HOLD_MM
        if mouth + 1e-9 >= bore:
            warnings.append(f"{label}={mouth} ≥ hole {bore:.2f}: the ring will not retain")
        elif mouth + 1e-9 >= small:
            warnings.append(
                f"{label}={mouth} is not under a pipe {UNDERSIZE_HOLD_MM} mm "
                f"smaller than Ø{pipe:.2f}: that pipe can leave without flexing"
            )
        elif mouth < 0.55 * bore:
            warnings.append(
                f"{label}={mouth} is under 55% of hole {bore:.2f}: "
                "the hoop will not flex that far by hand"
            )
    if handle_wall > 2.6:
        warnings.append(
            f"rings.handle.wall_mm={handle_wall} on a {band:.0f} mm band: "
            "PETG bending modulus ~1800 MPa, force grows with thickness cubed; "
            "a ring opened often wants about 2.0 mm"
        )
    if min(bar_wall, handle_wall) + 1e-9 < bite + 1.2:
        warnings.append(
            f"wall {min(bar_wall, handle_wall)} mm is thin for the {bite:.2f} mm joint bite"
        )
    return RingLayout(
        wall=bar_wall,
        bar_wall=bar_wall,
        handle_wall=handle_wall,
        band=band,
        bar_pipe=bar_pipe,
        handle_pipe=handle_pipe,
        bar_bore=bar_bore,
        handle_bore=handle_bore,
        bar_mouth=bar_mouth,
        handle_mouth=handle_mouth,
        bite=bite,
        x0=x0,
        warnings=tuple(warnings),
    )


def _half_gap_deg(mouth_mm: float, inner_r: float) -> float:
    ratio = (mouth_mm / 2.0) / inner_r
    if ratio >= 0.999:
        raise ValueError(
            f"mouth {mouth_mm} mm is not smaller than the bore diameter {2.0 * inner_r:.2f} mm"
        )
    if ratio <= 0.05:
        raise ValueError(f"mouth {mouth_mm} mm is too small to be a snap opening")
    return math.degrees(math.asin(ratio))


def _annulus(plane: str, inner_r: float, outer_r: float, band: float) -> cq.Workplane:
    return (
        cq.Workplane(plane)
        .circle(outer_r)
        .circle(inner_r)
        .extrude(band / 2.0, both=True)
    )


def _sector(
    plane: str,
    reach: float,
    center_deg: float,
    half_deg: float,
    half_depth: float,
) -> cq.Workplane:
    a0 = math.radians(center_deg - half_deg)
    a1 = math.radians(center_deg + half_deg)
    pts = [(0.0, 0.0)]
    steps = 12
    for i in range(steps + 1):
        angle = a0 + (a1 - a0) * i / steps
        pts.append((reach * math.cos(angle), reach * math.sin(angle)))
    return cq.Workplane(plane).polyline(pts).close().extrude(half_depth, both=True)


def _plane_point(plane: str, radius: float, deg: float) -> tuple[float, float, float]:
    angle = math.radians(deg)
    c, s = math.cos(angle), math.sin(angle)
    if plane == "XZ":
        return (radius * c, 0.0, radius * s)
    if plane == "XY":
        return (radius * c, radius * s, 0.0)
    raise ValueError(f"unsupported ring plane {plane!r}")


def _c_ring(
    plane: str,
    inner_r: float,
    wall: float,
    band: float,
    mouth_mm: float,
    center_deg: float,
) -> cq.Workplane:
    outer_r = inner_r + wall
    half = _half_gap_deg(mouth_mm, inner_r)
    ring = cut_through(
        _annulus(plane, inner_r, outer_r, band),
        _sector(plane, outer_r + 2.0, center_deg, half, band / 2.0 + 2.0),
    )
    bulb_r = min(BULB_R_MM, wall * 0.55)
    center_r = inner_r + min(BULB_INTO_WALL_MM, wall * 0.35)
    for deg in (center_deg - half, center_deg + half):
        bulb = cq.Workplane("XY").sphere(bulb_r).translate(_plane_point(plane, center_r, deg))
        ring = fuse(ring, bulb)
    if not is_one_valid_solid(ring):
        raise ValueError(f"C-ring on {plane} did not stay one solid after the mouth cut")
    return ring


def _bore(plane: str, radius: float, half_len: float, origin: tuple[float, float, float]) -> cq.Workplane:
    return cq.Workplane(plane).circle(radius).extrude(half_len, both=True).translate(origin)


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    lay = layout_from_spec(spec)
    for label, thick in (("bar", lay.bar_wall), ("handle", lay.handle_wall)):
        if thick + 1e-9 < 1.2:
            raise ValueError(f"rings.{label}.wall_mm={thick} is under 1.2 mm (3 perimeters on a 0.4 nozzle)")
    bar_r = lay.bar_bore / 2.0
    handle_r = lay.handle_bore / 2.0
    bar = _c_ring("XY", bar_r, lay.bar_wall, lay.band, lay.bar_mouth, BAR_GAP_DEG)
    handle = _c_ring(
        "XY", handle_r, lay.handle_wall, lay.band, lay.handle_mouth, HANDLE_GAP_DEG
    ).translate((lay.x0, 0.0, 0.0))
    part = fuse(bar, handle)
    if not is_one_valid_solid(part):
        raise ValueError("ring yoke joint did not fuse into one solid")

    inset = max(lay.bite + 0.25, (BULB_R_MM - BULB_INTO_WALL_MM) + 0.4)
    half = lay.band / 2.0 + 4.0
    bar_ko = _bore("XY", bar_r - inset, half, (0.0, 0.0, 0.0))
    handle_ko = _bore("XY", handle_r - inset, half, (lay.x0, 0.0, 0.0))
    keepout_volume = intersect_volume(part, bar_ko) + intersect_volume(part, handle_ko)

    bb = part.val().BoundingBox()
    outer = (float(bb.xlen), float(bb.ylen), float(bb.zlen))
    report = {
        "ring_bar_pipe_mm": round(lay.bar_pipe, 3),
        "ring_handle_pipe_mm": round(lay.handle_pipe, 3),
        "ring_bar_bore_mm": round(lay.bar_bore, 3),
        "ring_handle_bore_mm": round(lay.handle_bore, 3),
        "ring_bar_mouth_mm": round(lay.bar_mouth, 3),
        "ring_handle_mouth_mm": round(lay.handle_mouth, 3),
        "ring_mouths": "opposed-x",
        "ring_planes": "coplanar-xy",
        "ring_band_mm": round(lay.band, 3),
        "ring_wall_mm": round(lay.bar_wall, 3),
        "ring_bar_wall_mm": round(lay.bar_wall, 3),
        "ring_handle_wall_mm": round(lay.handle_wall, 3),
        "ring_joint_x_mm": round(lay.x0, 3),
        "ring_joint": "one-solid",
    }
    return EnclosureBuild(
        base=part,
        lid=part,
        assembled=part,
        printable=part,
        keepout=bar_ko,
        keepout_volume=keepout_volume,
        outer=outer,
        cavity_lw=(round(lay.bar_bore, 3), round(lay.handle_bore, 3)),
        warnings=list(lay.warnings),
        report=report,
    )
