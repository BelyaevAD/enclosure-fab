"""Passive chimney vents for enclosure_snap. Call from the committed template only.

Reuse recipe: docs/patterns.md. Do not fork a second
cutter — set case.vents and call apply_snap_vents. Roof-on-bed exhaust is a
well inside the outline; cutting through both short ends splits the lid into
bars. Wall intake is a closed window in the face (rim stays a loop). A U-notch
through the rim breaks the snap groove and Studio hangs those perimeters in
the gap. A two-sided 45° gable peak in a 1.5 mm wall is still a lintel.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, sqrt
from typing import Any

import cadquery as cq

from fabkit.kernel import box_aabb
from fabkit.solid import PENETRATE_MM, cut_all, fuse, intersect
from fabkit.vent_catalog import KIND_GRID_45, resolve_kind

# Forgetting slot_w_mm must not ship a 1.8 mm roof-on-bed hole (Studio closes it).
SLOT_W_MM = 2.4
LIGAMENT_MM = 2.52
LID_MIN_SLOT_W_MM = 2.4
# Leave plastic under the snap groove (groove starts ~ base_h − 1.35).
SNAP_CLEAR_MM = 1.2
# First solid layers + elephant foot close holes that start on the bed face.
BED_CLEAR_MM = 3.2
EDGE_MARGIN_MM = 3.5
SKIRT_W_MM = 1.0
LID_SLOT_COUNT = 3
# Roof-on-bed exhaust is a well (header-snap), not a roof-only plate hole.
# End rails stay: cutting through both ±X splits the lid into separate bars.
WELL_OVERSHOOT_MM = 0.4
LID_X_MARGIN_MM = 6.0
# Extra Y on the outer face (assembled +Z = print-bed after the flip).
LID_BED_FLARE_MM = 0.6
LID_BED_FLARE_DEPTH_MM = 0.4
# Closed hole with a flat 90° lintel hangs inner walls (Studio). A 1.2 mm
# two-sided gable in a 1.5 mm wall is still a peak the slicer fills.
# Live intake is `shed-slot`: window in the face, rim and snap groove stay a
# loop, lintel is one 45° slope (no vanishing peak, no crenel).
GABLE_MIN_RECT_MM = 1.6
SHED_MIN_RECT_MM = 1.6
RIM_OVERSHOOT_MM = 0.4
# Through-wall overshoot so the cutter is not flush with inner/outer faces.
WALL_THRU_MM = 0.6
# In-plane 45° kerf: perpendicular width / √2 = Δ(along − z).
GRID_SQRT2 = sqrt(2.0)

AABB = tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class SnapVentCtx:
    wall: float
    outer_l: float
    outer_w: float
    base_h: float
    roof_h: float
    groove_z0: float
    inlet_y0: float
    inlet_d: float
    fit: float = 0.25
    skirt_h: float = 2.0
    skirt_w: float = SKIRT_W_MM


def wall_slot_band(ctx: SnapVentCtx) -> tuple[float, float]:
    """Closed-window band: above the bed, below the snap groove. Rim stays solid."""
    z0 = max(ctx.wall + 0.3, BED_CLEAR_MM)
    z1 = ctx.groove_z0 - SNAP_CLEAR_MM
    if z1 < z0 + 2.4:
        z1 = min(ctx.groove_z0 - 0.8, z0 + 2.4)
    return z0, z1


def wall_intake_z(ctx: SnapVentCtx) -> tuple[float, float]:
    """Live ±Y/−X intake: same closed band as wall_slot_band."""
    return wall_slot_band(ctx)


def wall_crenel_prism(
    *,
    along: str,
    a0: float,
    a1: float,
    z0: float,
    z1: float,
    thru0: float,
    thru1: float,
) -> cq.Workplane:
    """Through-wall U-notch (open at the rim)."""
    if along == "x":
        return box_aabb(a0, thru0, z0, a1, thru1, z1)
    if along == "y":
        return box_aabb(thru0, a0, z0, thru1, a1, z1)
    raise ValueError(f"along must be 'x' or 'y', got {along!r}")


def slot_gable_h(width: float, band_h: float) -> float:
    """Height of a 45° peak on a wall slot (0.5×width), clamped to the band."""
    if width <= 0 or band_h <= 0:
        return 0.0
    want = 0.5 * width
    room = band_h - GABLE_MIN_RECT_MM
    if room < 0.4:
        return max(0.0, min(want, 0.35 * band_h))
    return min(want, room)


def _through_wall_plane(along: str, thru0: float, thru1: float) -> cq.Workplane:
    """Sketch (along-wall, +Z), extrude through the wall.

    Named ``XZ`` has normal −Y (CadQuery ``yDir = normal × xDir``). Extrude
    from the far face so the prism actually occupies ``thru0…thru1``. Named
    ``YZ`` has normal +X — start at ``thru0``.
    """
    if along == "x":
        return cq.Workplane("XZ", origin=(0.0, thru1, 0.0))
    return cq.Workplane("YZ", origin=(thru0, 0.0, 0.0))


def _wall_profile_prism(
    along: str,
    pts: list[tuple[float, float]],
    thru0: float,
    thru1: float,
) -> cq.Workplane:
    thick = thru1 - thru0
    return (
        _through_wall_plane(along, thru0, thru1)
        .polyline(pts)
        .close()
        .extrude(thick)
    )


def gable_slot_prism(
    *,
    along: str,
    a0: float,
    a1: float,
    z0: float,
    z1: float,
    thru0: float,
    thru1: float,
    gable_h: float | None = None,
) -> cq.Workplane:
    """Through-wall cutter: rectangle with a 45° gable instead of a flat lintel.

    `along` is the long axis of the slot in the wall plane: ``x`` for ±Y walls
    (profile in XZ, extrude Y), ``y`` for ±X walls (profile in YZ, extrude X).
    """
    if along not in {"x", "y"}:
        raise ValueError(f"along must be 'x' or 'y', got {along!r}")
    thick = thru1 - thru0
    if a1 <= a0 or z1 <= z0 or thick <= 0:
        raise ValueError("degenerate gable slot")
    gh = slot_gable_h(a1 - a0, z1 - z0) if gable_h is None else float(gable_h)
    z_eave = z1 - gh
    if gh < 0.35 or z_eave <= z0 + 1e-9:
        if along == "x":
            return box_aabb(a0, thru0, z0, a1, thru1, z1)
        return box_aabb(thru0, a0, z0, thru1, a1, z1)
    mid = 0.5 * (a0 + a1)
    pts = [(a0, z0), (a1, z0), (a1, z_eave), (mid, z1), (a0, z_eave)]
    return _wall_profile_prism(along, pts, thru0, thru1)


def shed_slot_h(width: float, band_h: float) -> float:
    """Z rise of a 45° shed lintel (equals width), leaving a rectangle below."""
    if width <= 0 or band_h <= 0:
        return 0.0
    want = width
    room = band_h - SHED_MIN_RECT_MM
    if room < 0.4:
        return max(0.0, min(want, 0.5 * band_h))
    return min(want, room)


def shed_slot_prism(
    *,
    along: str,
    a0: float,
    a1: float,
    z0: float,
    z1: float,
    thru0: float,
    thru1: float,
    shed_h: float | None = None,
) -> cq.Workplane:
    """Through-wall window: rectangle fused with a 45° wedge (shed, not gable).

    A single 4-point polyline prism left leftover faces in the hole; Studio
    Repair deleted them. Two convex solids with a real overlap fuse cleanly.
    The rim of the part is not cut. Top edge runs from (a0, z1) down to
    (a1, z1 − shed_h).
    """
    if along not in {"x", "y"}:
        raise ValueError(f"along must be 'x' or 'y', got {along!r}")
    thick = thru1 - thru0
    if a1 <= a0 or z1 <= z0 or thick <= 0:
        raise ValueError("degenerate shed slot")
    sh = shed_slot_h(a1 - a0, z1 - z0) if shed_h is None else float(shed_h)
    z_low = z1 - sh
    if sh < 0.35 or z_low <= z0 + 1e-9:
        if along == "x":
            return box_aabb(a0, thru0, z0, a1, thru1, z1)
        return box_aabb(thru0, a0, z0, thru1, a1, z1)
    if along == "x":
        rect = box_aabb(a0, thru0, z0, a1, thru1, z_low + PENETRATE_MM)
    else:
        rect = box_aabb(thru0, a0, z0, thru1, a1, z_low + PENETRATE_MM)
    wedge = _wall_profile_prism(
        along,
        [(a0, z_low), (a1, z_low), (a0, z1)],
        thru0,
        thru1,
    )
    return fuse(rect, wedge)


def face_strip_prism(
    *,
    along: str,
    p0: tuple[float, float],
    p1: tuple[float, float],
    width: float,
    thru0: float,
    thru1: float,
    clip_a0: float,
    clip_a1: float,
    clip_z0: float,
    clip_z1: float,
) -> cq.Workplane | None:
    """Through-wall kerf along a segment in the face plane, clipped to a field.

    `p0`/`p1` are (along, z). Width is the clear opening in the face. 45°
    segments self-support on a standing wall (no 90° lintel).
    """
    if along not in {"x", "y"}:
        raise ValueError(f"along must be 'x' or 'y', got {along!r}")
    dx = p1[0] - p0[0]
    dz = p1[1] - p0[1]
    length = hypot(dx, dz)
    if length < 0.45 or width < 0.35:
        return None
    nx = -dz / length * (width / 2.0)
    nz = dx / length * (width / 2.0)
    pts = [
        (p0[0] + nx, p0[1] + nz),
        (p1[0] + nx, p1[1] + nz),
        (p1[0] - nx, p1[1] - nz),
        (p0[0] - nx, p0[1] - nz),
    ]
    strip = _wall_profile_prism(along, pts, thru0, thru1)
    if along == "x":
        field = box_aabb(clip_a0, thru0, clip_z0, clip_a1, thru1, clip_z1)
    else:
        field = box_aabb(thru0, clip_a0, clip_z0, thru1, clip_a1, clip_z1)
    return intersect(strip, field)


def grid_45_c_values(
    a0: float,
    a1: float,
    z0: float,
    z1: float,
    slot_w: float,
    ligament: float,
) -> list[float]:
    """c = along − z for parallel +45° slits (perp pitch = slot + ligament)."""
    dw = slot_w * GRID_SQRT2
    pitch = (slot_w + ligament) * GRID_SQRT2
    if pitch < 0.8 or a1 - a0 < slot_w or z1 - z0 < slot_w:
        return []
    c_lo = a0 - z1
    c_hi = a1 - z0 - dw
    if c_hi < c_lo:
        return []
    c = c_lo + 0.25 * ligament * GRID_SQRT2
    out: list[float] = []
    while c <= c_hi + 1e-9:
        out.append(round(c, 4))
        c += pitch
    return out


def grid_45_slot_prism(
    *,
    along: str,
    a0: float,
    a1: float,
    z0: float,
    z1: float,
    thru0: float,
    thru1: float,
    c0: float,
    slot_w: float,
) -> cq.Workplane | None:
    """One +45° parallelogram slit: along − z ∈ [c0, c0 + slot_w√2]."""
    dw = slot_w * GRID_SQRT2
    pts = [
        (c0 + z0, z0),
        (c0 + dw + z0, z0),
        (c0 + dw + z1, z1),
        (c0 + z1, z1),
    ]
    xs = [p[0] for p in pts]
    if max(xs) < a0 + 0.15 or min(xs) > a1 - 0.15:
        return None
    strip = _wall_profile_prism(along, pts, thru0, thru1)
    if along == "x":
        field = box_aabb(a0, thru0, z0, a1, thru1, z1)
    else:
        field = box_aabb(thru0, a0, z0, thru1, a1, z1)
    return intersect(strip, field)


def roof_well_z(ctx: SnapVentCtx) -> tuple[float, float]:
    """Roof + lid skirt. Same z as header-snap pin wells."""
    return (
        ctx.base_h - ctx.skirt_h - WELL_OVERSHOOT_MM,
        ctx.base_h + ctx.roof_h + WELL_OVERSHOOT_MM,
    )


def lid_roof_slots(ctx: SnapVentCtx, slot_w: float, ligament: float) -> list[AABB]:
    """Three chimney wells in the roof, inset from the short ends.

    Assembled AABB (x0, y0, z0, x1, y1, z1). z is a well (roof + skirt
    height), like header-snap. x keeps end rails so the lid stays one
    solid — do not overshoot ±X. ±Y skirts (snap) stay solid.
    """
    z0, z1 = roof_well_z(ctx)
    x0 = LID_X_MARGIN_MM
    x1 = ctx.outer_l - LID_X_MARGIN_MM
    if x1 - x0 < slot_w * 2:
        return []
    pitch = slot_w + ligament
    total = LID_SLOT_COUNT * slot_w + (LID_SLOT_COUNT - 1) * ligament
    y0 = 0.5 * ctx.outer_w - 0.5 * total
    if y0 < ctx.wall + 0.6 or y0 + total > ctx.outer_w - ctx.wall - 0.6:
        return []
    boxes: list[AABB] = []
    for i in range(LID_SLOT_COUNT):
        ys = y0 + i * pitch
        boxes.append((x0, ys, z0, x1, ys + slot_w, z1))
    return boxes


def vent_block(spec: dict[str, Any]) -> dict[str, Any] | None:
    block = (spec.get("case") or {}).get("vents")
    if not block:
        return None
    faces = [str(f) for f in (block.get("faces") or [])]
    if not faces:
        return None
    slot_w = float(block.get("slot_w_mm") or SLOT_W_MM)
    ligament = float(block.get("ligament_mm") or LIGAMENT_MM)
    return {
        "faces": faces,
        "kind": resolve_kind(block),
        "pattern": str(block.get("pattern") or "slots"),
        "slot_w": slot_w,
        "ligament": ligament,
        "pitch": slot_w + ligament,
    }


def slot_origins(start: float, end: float, width: float, pitch: float) -> list[float]:
    if end - start < width or pitch <= 0:
        return []
    out: list[float] = []
    x = start
    while x + width <= end + 1e-9:
        out.append(round(x, 4))
        x += pitch
    return out


def apply_snap_vents(
    base: cq.Workplane,
    lid_assembled: cq.Workplane,
    spec: dict[str, Any],
    ctx: SnapVentCtx,
    wall_exclude: dict[str, list[tuple[float, float]]] | None = None,
) -> tuple[cq.Workplane, cq.Workplane, list[str]]:
    warnings: list[str] = []
    cfg = vent_block(spec)
    if cfg is None:
        return base, lid_assembled, warnings
    faces = set(cfg["faces"])
    slot_w = cfg["slot_w"]
    pitch = cfg["pitch"]
    ligament = cfg["ligament"]
    kind = str(cfg.get("kind") or resolve_kind((spec.get("case") or {}).get("vents") or {}))
    z0, z1 = wall_intake_z(ctx)
    known = {"lid", "minus_x", "plus_x", "plus_y", "minus_y", "floor"}
    skipped = sorted(faces - known)
    if skipped:
        warnings.append("case.vents: faces not cut: " + ",".join(skipped))
    if kind == KIND_GRID_45:
        warnings.append(
            "case.vents grid-45: parallel 45° slits in the wall face; "
            "rim stays a loop (not louver-45, not a 90° lintel)"
        )
    tools: list[cq.Workplane] = []
    if "minus_x" in faces:
        if kind == KIND_GRID_45:
            minus = _minus_x_grid_tools(ctx, slot_w, ligament, z0, z1)
        else:
            minus = _minus_x_tools(ctx, slot_w, z0, z1)
        if not minus:
            warnings.append("case.vents minus_x: no intake windows fitted")
        tools.extend(minus)
    exclude = wall_exclude or {}
    if "plus_y" in faces:
        plus = _long_wall_tools(
            ctx,
            slot_w,
            pitch,
            z0,
            z1,
            plus=True,
            exclude=exclude.get("plus_y"),
            kind=kind,
            ligament=ligament,
        )
        if not plus:
            warnings.append("case.vents plus_y: no intake windows fitted")
        tools.extend(plus)
    if "minus_y" in faces:
        minus_y = _long_wall_tools(
            ctx,
            slot_w,
            pitch,
            z0,
            z1,
            plus=False,
            exclude=exclude.get("minus_y"),
            kind=kind,
            ligament=ligament,
        )
        if not minus_y:
            warnings.append("case.vents minus_y: no intake windows fitted")
        tools.extend(minus_y)
    if "floor" in faces:
        floor = _floor_tools(ctx, slot_w, pitch)
        if not floor:
            warnings.append("case.vents floor: no windows fitted")
        tools.extend(floor)
    if tools:
        base = cut_all(base, tools)
    if "lid" in faces:
        through, flares = lid_roof_cutters(ctx, slot_w, cfg["ligament"])
        if not through:
            warnings.append("case.vents lid: roof slots do not fit; no lid holes cut")
        else:
            lid_assembled = cut_all(lid_assembled, through)
            if flares:
                lid_assembled = cut_all(lid_assembled, flares)
    return base, lid_assembled, warnings


def _minus_x_tools(ctx: SnapVentCtx, slot_w: float, z0: float, z1: float) -> list[cq.Workplane]:
    bands = (
        (EDGE_MARGIN_MM, ctx.inlet_y0 - 2.0),
        (ctx.inlet_y0 + ctx.inlet_d + 2.0, ctx.outer_w - EDGE_MARGIN_MM),
    )
    tools: list[cq.Workplane] = []
    # Flanks beside the IN U-slot are often narrower than a 2.4 lid slot.
    # Shrink to the band instead of dropping intake (vertical 1.8 still prints).
    min_w = min(slot_w, 1.8)
    for y0, y1 in bands:
        usable = y1 - y0
        if usable < min_w:
            continue
        w = min(slot_w, usable)
        mid = 0.5 * (y0 + y1)
        ys = mid - w / 2.0
        tools.append(
            shed_slot_prism(
                along="y",
                a0=ys,
                a1=ys + w,
                z0=z0,
                z1=z1,
                thru0=-WALL_THRU_MM,
                thru1=ctx.wall + WALL_THRU_MM,
            )
        )
    return tools


def _minus_x_grid_tools(
    ctx: SnapVentCtx, slot_w: float, ligament: float, z0: float, z1: float
) -> list[cq.Workplane]:
    """+45° slits on the short −X face.

    Window intake splits Y around the IN U-slot; those flanks are too
    narrow for a 45° parallelogram on an 18.5 mm buck. Grid stays one
    field across Y and, when the U-slot exists, stops below it so the
    rim notch is unchanged.
    """
    y0, y1 = EDGE_MARGIN_MM, ctx.outer_w - EDGE_MARGIN_MM
    z1_use = z1
    if ctx.inlet_d > 0.2:
        z1_use = min(z1, ctx.base_h - ctx.inlet_d - 0.4)
    if y1 - y0 < slot_w + ligament or z1_use - z0 < slot_w:
        return []
    thru0, thru1 = -WALL_THRU_MM, ctx.wall + WALL_THRU_MM
    tools: list[cq.Workplane] = []
    for c0 in grid_45_c_values(y0, y1, z0, z1_use, slot_w, ligament):
        prism = grid_45_slot_prism(
            along="y",
            a0=y0,
            a1=y1,
            z0=z0,
            z1=z1_use,
            thru0=thru0,
            thru1=thru1,
            c0=c0,
            slot_w=slot_w,
        )
        if prism is not None:
            tools.append(prism)
    return tools


def _overlaps_range(x0: float, x1: float, spans: list[tuple[float, float]] | None) -> bool:
    if not spans:
        return False
    return any(x0 < e1 and x1 > e0 for e0, e1 in spans)


def _long_wall_tools(
    ctx: SnapVentCtx,
    slot_w: float,
    pitch: float,
    z0: float,
    z1: float,
    *,
    plus: bool,
    exclude: list[tuple[float, float]] | None = None,
    kind: str = "window",
    ligament: float = LIGAMENT_MM,
) -> list[cq.Workplane]:
    if plus:
        thru0, thru1 = ctx.outer_w - ctx.wall - WALL_THRU_MM, ctx.outer_w + WALL_THRU_MM
    else:
        thru0, thru1 = -WALL_THRU_MM, ctx.wall + WALL_THRU_MM
    a0, a1 = 6.0, ctx.outer_l - 6.0
    if kind == KIND_GRID_45:
        tools: list[cq.Workplane] = []
        dw = slot_w * GRID_SQRT2
        for c0 in grid_45_c_values(a0, a1, z0, z1, slot_w, ligament):
            along0, along1 = c0 + z0, c0 + dw + z1
            if _overlaps_range(along0, along1, exclude):
                continue
            prism = grid_45_slot_prism(
                along="x",
                a0=a0,
                a1=a1,
                z0=z0,
                z1=z1,
                thru0=thru0,
                thru1=thru1,
                c0=c0,
                slot_w=slot_w,
            )
            if prism is not None:
                tools.append(prism)
        return tools
    xs = slot_origins(a0, a1, slot_w, pitch)
    return [
        shed_slot_prism(
            along="x",
            a0=x,
            a1=x + slot_w,
            z0=z0,
            z1=z1,
            thru0=thru0,
            thru1=thru1,
        )
        for x in xs
        if not _overlaps_range(x, x + slot_w, exclude)
    ]


def _floor_tools(ctx: SnapVentCtx, slot_w: float, pitch: float) -> list[cq.Workplane]:
    xs = slot_origins(7.0, ctx.outer_l - 7.0, slot_w, pitch)
    y0, y1 = EDGE_MARGIN_MM, ctx.outer_w - EDGE_MARGIN_MM
    return [box_aabb(x, y0, -0.3, x + slot_w, y1, ctx.wall + 0.4) for x in xs]


def bed_face_flare_boxes_from_slots(
    slots: list[AABB],
    *,
    wall: float,
    outer_w: float,
    roof_outer: float,
    flare: float = LID_BED_FLARE_MM,
    depth: float = LID_BED_FLARE_DEPTH_MM,
) -> list[AABB]:
    """Widen Y on the outer roof face (print-bed lead-in). Chimney and pin wells."""
    y_min = wall + 0.3
    y_max = outer_w - wall - 0.3
    flare_z0 = roof_outer - depth
    boxes: list[AABB] = []
    for x0, y0, _z0, x1, y1, z1 in slots:
        fy0 = max(y0 - flare, y_min)
        fy1 = min(y1 + flare, y_max)
        if fy1 - fy0 <= y1 - y0 + 1e-9:
            continue
        boxes.append((x0, fy0, flare_z0, x1, fy1, z1))
    return boxes


def lid_bed_flare_boxes(ctx: SnapVentCtx, slot_w: float, ligament: float) -> list[AABB]:
    """Wider AABBs on the outer roof face only (print-bed lead-in).

    Does not change the through-slot millimetres. Adjacent flares stay
    disjoint when ligament >= 2.0 and flare is 0.6.
    """
    return bed_face_flare_boxes_from_slots(
        lid_roof_slots(ctx, slot_w, ligament),
        wall=ctx.wall,
        outer_w=ctx.outer_w,
        roof_outer=ctx.base_h + ctx.roof_h,
    )


def lid_roof_cutters(
    ctx: SnapVentCtx, slot_w: float, ligament: float
) -> tuple[list[cq.Workplane], list[cq.Workplane]]:
    """Through slots, then separate bed-face flares (they overlap in Z)."""
    through = [
        box_aabb(x0, y0, z0, x1, y1, z1)
        for x0, y0, z0, x1, y1, z1 in lid_roof_slots(ctx, slot_w, ligament)
    ]
    flares = [box_aabb(*box) for box in lid_bed_flare_boxes(ctx, slot_w, ligament)]
    return through, flares
