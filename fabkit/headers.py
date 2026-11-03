"""Pin-row lid slots and a side button for enclosure_snap.

Pattern: header-snap. Spec millimetres are the part.
Pin slots add FDM opening clearance like USB. A flex_tab is the wall itself:
the slot *is* the clearance — do not grow the tongue by +0.3/side.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cadquery as cq

from fabkit.fit import OPENING_CLEARANCE_MM, opening_cut_size
from fabkit.kernel import box_aabb
from fabkit.snap_geom import BED_CLEAR_MM, SNAP_CLEAR_MM, SnapLayout
from fabkit.solid import PENETRATE_MM, cut_all, cut_through, fuse
from fabkit.vents import bed_face_flare_boxes_from_slots

AABB = tuple[float, float, float, float, float, float]

# Printables flexure isolation with a 0.4 mm nozzle; p1s-0.4 floor is ≥0.8.
FLEX_SLOT_MM = 0.8
# ~2 perimeters. PETG L/t 5–8 (Sovol); a 10 mm tongue at 0.9 is ~11:1.
FLEX_TAB_T_MM = 0.9
FLEX_NUB_MM = 0.8
FLEX_NUB_WH_MM = 2.6
# Unthinned root instead of a 0.8–1.0 fillet (RoboDIB / Sovol).
FLEX_HINGE_ROOT_MM = 1.2
FLEX_FREE_PAD_MM = 1.4
CORNER_LIGAMENT_MM = 0.4
# Breakaway ties across the U-slot (print support, snip after). One 0.4 line;
# pitch ~8 lines. Not the inner actuator nub.
FLEX_TIE_W_MM = 0.42
FLEX_TIE_PITCH_MM = 3.2


def header_block(spec: dict[str, Any]) -> dict[str, Any] | None:
    block = spec.get("headers")
    if not isinstance(block, dict):
        return None
    rows = block.get("rows") or []
    if not rows:
        return None
    return block


def button_block(spec: dict[str, Any]) -> dict[str, Any] | None:
    block = spec.get("button")
    if not isinstance(block, dict):
        return None
    if not block.get("face"):
        return None
    return block


def button_style(spec: dict[str, Any]) -> str:
    block = button_block(spec)
    if block is None:
        return "none"
    return str(block.get("style") or "window")


# Leave plastic between a pin well and a snap clip (FDM blob / elephant foot).
BEAD_SLOT_CLEAR_MM = 1.2
MIN_BEAD_SEG_MM = 3.2


def header_slot_aabbs(spec: dict[str, Any], lay: SnapLayout) -> list[AABB]:
    """Pin well: roof + lid skirt, assembled CS. One slot per pin row.

    A roof-only cut leaves the inner skirt (and the ±Y bead on it) in the
    pin path — Formlabs: pins limit snap length; do not run a full-length
    lock through the header envelope.
    """
    block = header_block(spec)
    if block is None:
        return []
    slot_w = float(block["slot_w_mm"])
    z0 = lay.base_h - lay.skirt_h - 0.4
    z1 = lay.outer_z + 0.4
    boxes: list[AABB] = []
    for row in block["rows"]:
        y = float(row["y_mm"]["value"])
        x0 = float(row["x0_mm"]["value"])
        x1 = float(row["x1_mm"]["value"])
        if x1 <= x0 or slot_w <= 0:
            continue
        cut_w, _ = opening_cut_size(slot_w, slot_w, OPENING_CLEARANCE_MM)
        cy = lay.board_oy + y
        xs = lay.board_ox + x0 - OPENING_CLEARANCE_MM
        xe = lay.board_ox + x1 + OPENING_CLEARANCE_MM
        boxes.append((xs, cy - cut_w / 2.0, z0, xe, cy + cut_w / 2.0, z1))
    return boxes


def header_slot_xy(spec: dict[str, Any], lay: SnapLayout) -> list[tuple[float, float, float, float]]:
    return [(x0, y0, x1, y1) for x0, y0, _z0, x1, y1, _z1 in header_slot_aabbs(spec, lay)]


def header_slot_x_union(spec: dict[str, Any], lay: SnapLayout) -> tuple[float, float] | None:
    slots = header_slot_xy(spec, lay)
    if not slots:
        return None
    return min(x0 for x0, _y0, _x1, _y1 in slots), max(x1 for _x0, _y0, x1, _y1 in slots)


def bead_x_segments(spec: dict[str, Any], lay: SnapLayout) -> list[tuple[float, float]]:
    """±Y bead spans. Full length without headers; two end clips around pin wells.

    `lid_open_usb` clips +X so the bead stops before the USB can (U-bay lid).
    """
    full = (lay.bead_x0, lay.bead_x1)
    if lay.lid_open_usb:
        full = (full[0], min(full[1], lay.usb_skirt_stop_x - 0.4))
    span = header_slot_x_union(spec, lay)
    if span is None:
        return [full]
    keepout0 = span[0] - BEAD_SLOT_CLEAR_MM
    keepout1 = span[1] + BEAD_SLOT_CLEAR_MM
    segs: list[tuple[float, float]] = []
    lo0, lo1 = full[0], min(full[1], keepout0)
    if lo1 - lo0 >= MIN_BEAD_SEG_MM:
        segs.append((lo0, lo1))
    hi0, hi1 = max(full[0], keepout1), full[1]
    if hi1 - hi0 >= MIN_BEAD_SEG_MM:
        segs.append((hi0, hi1))
    return segs or [full]


def button_cut_aabb(spec: dict[str, Any], lay: SnapLayout) -> AABB | None:
    """Through-wall window. y/z are on the board: y along width, z from PCB bottom."""
    if button_style(spec) != "window":
        return None
    btn = button_block(spec)
    if btn is None:
        return None
    face = str(btn.get("face") or "plus_x")
    y = float(btn["offset_mm"]["y"]["value"])
    z = float(btn["offset_mm"]["z"]["value"])
    part_w = float(btn["opening_wh_mm"]["w"]["value"])
    part_h = float(btn["opening_wh_mm"]["h"]["value"])
    cut_w, cut_h = opening_cut_size(part_w, part_h, OPENING_CLEARANCE_MM)
    cy = lay.board_oy + y
    cz = lay.board_oz + z
    y0, y1 = cy - cut_w / 2.0, cy + cut_w / 2.0
    z0, z1 = cz - cut_h / 2.0, cz + cut_h / 2.0
    if face == "plus_x":
        return (lay.outer_l - lay.wall - 1.4, y0, z0, lay.outer_l + 0.3, y1, z1)
    if face == "minus_x":
        return (-0.3, y0, z0, lay.wall + 1.4, y1, z1)
    if face == "plus_y":
        x = float(btn.get("offset_mm", {}).get("x", {}).get("value") or (lay.length / 2.0))
        cx = lay.board_ox + x
        return (
            cx - cut_w / 2.0,
            lay.outer_w - lay.wall - 1.4,
            z0,
            cx + cut_w / 2.0,
            lay.outer_w + 0.3,
            z1,
        )
    if face == "minus_y":
        x = float(btn.get("offset_mm", {}).get("x", {}).get("value") or (lay.length / 2.0))
        cx = lay.board_ox + x
        return (cx - cut_w / 2.0, -0.3, z0, cx + cut_w / 2.0, lay.wall + 1.4, z1)
    return None


@dataclass(frozen=True)
class FlexTabPlan:
    face: str
    hinge: str
    hinge_low: bool
    along0: float
    along1: float
    z0: float
    z1: float
    slot: float
    tab_t: float
    nub: float
    nub_along0: float
    nub_along1: float
    nub_z0: float
    nub_z1: float
    tie_w: float
    tie_pitch: float
    switch_along: float
    switch_z: float
    thickness_axis: str
    outer: float
    inner: float
    inward: float


def _face_frame(face: str, lay: SnapLayout) -> tuple[str, float, float, float] | None:
    """thickness_axis, outer, inner, inward (+1 if inward is +axis)."""
    if face == "minus_y":
        return "y", 0.0, lay.wall, 1.0
    if face == "plus_y":
        return "y", lay.outer_w, lay.outer_w - lay.wall, -1.0
    if face == "minus_x":
        return "x", 0.0, lay.wall, 1.0
    if face == "plus_x":
        return "x", lay.outer_l, lay.outer_l - lay.wall, -1.0
    return None


def _default_hinge(face: str) -> str:
    if face in {"minus_y", "plus_y"}:
        return "minus_x"
    if face == "plus_x":
        return "minus_y"
    return "plus_y"


def _hinge_is_low(face: str, hinge: str) -> bool:
    if face in {"minus_y", "plus_y"}:
        return hinge != "plus_x"
    return hinge != "plus_y"


def _along_limits(face: str, lay: SnapLayout, slot: float) -> tuple[float, float]:
    ligament = lay.wall + slot + CORNER_LIGAMENT_MM
    if face in {"minus_y", "plus_y"}:
        return ligament, lay.outer_l - ligament
    return ligament, lay.outer_w - ligament


def _mm_or(block: dict[str, Any], path: tuple[str, ...], default: float | None) -> float | None:
    cur: Any = block
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    if isinstance(cur, dict) and "value" in cur:
        return float(cur["value"])
    if isinstance(cur, (int, float)):
        return float(cur)
    return default


def flex_tab_plan(spec: dict[str, Any], lay: SnapLayout) -> FlexTabPlan | None:
    if button_style(spec) != "flex_tab":
        return None
    btn = button_block(spec)
    if btn is None:
        return None
    face = str(btn.get("face") or "minus_y")
    frame = _face_frame(face, lay)
    if frame is None:
        return None
    thickness_axis, outer, inner, inward = frame
    slot = float(btn.get("slot_mm") or FLEX_SLOT_MM)
    tab_t = float(btn.get("tab_t_mm") or FLEX_TAB_T_MM)
    nub = float(btn.get("nub_mm") or FLEX_NUB_MM)
    raw_tie = btn.get("tie_mm")
    tie_w = FLEX_TIE_W_MM if raw_tie is None else float(raw_tie)
    tie_pitch = float(btn.get("tie_pitch_mm") or FLEX_TIE_PITCH_MM)
    nub_w = _mm_or(btn, ("nub_wh_mm", "w"), FLEX_NUB_WH_MM) or FLEX_NUB_WH_MM
    nub_h = _mm_or(btn, ("nub_wh_mm", "h"), FLEX_NUB_WH_MM) or FLEX_NUB_WH_MM
    tab_w = float(btn["opening_wh_mm"]["w"]["value"])
    tab_h = float(btn["opening_wh_mm"]["h"]["value"])
    z_sw = float(btn["offset_mm"]["z"]["value"])
    hinge = str(btn.get("hinge") or _default_hinge(face))
    hinge_low = _hinge_is_low(face, hinge)
    along_lo, along_hi = _along_limits(face, lay, slot)
    if face in {"minus_y", "plus_y"}:
        switch_along = lay.board_ox + float(btn["offset_mm"]["x"]["value"])
    else:
        switch_along = lay.board_oy + float(btn["offset_mm"]["y"]["value"])
    switch_z = lay.board_oz + z_sw
    z_lo = BED_CLEAR_MM
    z_hi = lay.groove_z0 - SNAP_CLEAR_MM
    if hinge_low:
        along1 = min(switch_along + FLEX_FREE_PAD_MM, along_hi)
        along0 = along1 - tab_w
        if along0 < along_lo:
            along0 = along_lo
            along1 = min(along0 + tab_w, along_hi)
    else:
        along0 = max(switch_along - FLEX_FREE_PAD_MM, along_lo)
        along1 = along0 + tab_w
        if along1 > along_hi:
            along1 = along_hi
            along0 = max(along1 - tab_w, along_lo)
    z0 = max(z_lo, switch_z - tab_h / 2.0)
    z1 = min(z_hi, switch_z + tab_h / 2.0)
    if z1 - z0 < 3.2:
        z0 = z_lo
        z1 = min(z_hi, z0 + max(tab_h, 4.0))
    nub_a0 = max(along0 + 0.3, switch_along - nub_w / 2.0)
    nub_a1 = min(along1 - 0.3, switch_along + nub_w / 2.0)
    if nub_a1 <= nub_a0:
        if hinge_low:
            nub_a1 = along1 - 0.3
            nub_a0 = nub_a1 - nub_w
        else:
            nub_a0 = along0 + 0.3
            nub_a1 = nub_a0 + nub_w
    nub_z0 = max(z0 + 0.2, switch_z - nub_h / 2.0)
    nub_z1 = min(z1 - 0.2, switch_z + nub_h / 2.0)
    if nub_z1 <= nub_z0:
        mid = 0.5 * (z0 + z1)
        nub_z0, nub_z1 = mid - nub_h / 2.0, mid + nub_h / 2.0
    return FlexTabPlan(
        face=face,
        hinge=hinge,
        hinge_low=hinge_low,
        along0=along0,
        along1=along1,
        z0=z0,
        z1=z1,
        slot=slot,
        tab_t=min(tab_t, lay.wall - 0.35),
        nub=nub,
        nub_along0=nub_a0,
        nub_along1=nub_a1,
        nub_z0=nub_z0,
        nub_z1=nub_z1,
        tie_w=max(0.0, tie_w),
        tie_pitch=max(tie_pitch, tie_w + 0.8) if tie_w > 1e-9 else 0.0,
        switch_along=switch_along,
        switch_z=switch_z,
        thickness_axis=thickness_axis,
        outer=outer,
        inner=inner,
        inward=inward,
    )


def button_vent_exclude(spec: dict[str, Any], lay: SnapLayout) -> dict[str, list[tuple[float, float]]]:
    """X (or Y) spans on a wall that intake slots must not punch."""
    plan = flex_tab_plan(spec, lay)
    if plan is None:
        return {}
    pad = plan.slot + 1.5
    cap = plan.slot
    if plan.hinge_low:
        a0, a1 = plan.along0 - pad, plan.along1 + cap + pad
    else:
        a0, a1 = plan.along0 - cap - pad, plan.along1 + pad
    return {plan.face: [(a0, a1)]}


def flex_free_along(plan: FlexTabPlan) -> tuple[float, float]:
    """Along span of the vertical cap (0.8 mm). Not a rounded bulge."""
    if plan.hinge_low:
        return plan.along1, plan.along1 + plan.slot
    return plan.along0 - plan.slot, plan.along0


def flex_slot_span(plan: FlexTabPlan) -> tuple[float, float]:
    """Along span of the two long slits, including the cap over the vertical."""
    cap0, cap1 = flex_free_along(plan)
    return min(plan.along0, cap0), max(plan.along1, cap1)


def flex_tie_along(plan: FlexTabPlan) -> list[float]:
    """Along-axis centres of breakaway whiskers in the long slits (snip after)."""
    if plan.tie_w <= 1e-9 or plan.tie_pitch <= 1e-9:
        return []
    out: list[float] = []
    if plan.hinge_low:
        x = plan.along1
        stop = plan.along0 + FLEX_HINGE_ROOT_MM + plan.tie_w
        while x >= stop - 1e-9:
            out.append(round(x, 4))
            x -= plan.tie_pitch
    else:
        x = plan.along0
        stop = plan.along1 - FLEX_HINGE_ROOT_MM - plan.tie_w
        while x <= stop + 1e-9:
            out.append(round(x, 4))
            x += plan.tie_pitch
    return out


def _along_cuts_with_ties(
    a0: float, a1: float, ties: list[float], tie_w: float
) -> list[tuple[float, float]]:
    lo, hi = (a0, a1) if a1 >= a0 else (a1, a0)
    if hi - lo < 0.2:
        return []
    if tie_w <= 1e-9 or not ties:
        return [(lo, hi)]
    cuts: list[tuple[float, float]] = []
    cursor = lo
    for centre in sorted(ties):
        g0 = max(lo, centre - tie_w / 2.0)
        g1 = min(hi, centre + tie_w / 2.0)
        if g1 <= cursor or g0 >= hi:
            continue
        if g0 - cursor >= 0.35:
            cuts.append((cursor, g0))
        cursor = max(cursor, g1)
    if hi - cursor >= 0.35:
        cuts.append((cursor, hi))
    return cuts


def _ties_keeping_cuts(
    a0: float, a1: float, ties: list[float], tie_w: float
) -> tuple[list[float], list[tuple[float, float]], int]:
    """Drop hinge-side ticks until the long slits still cut. Count how many dropped."""
    kept = list(ties)
    dropped = 0
    while kept:
        cuts = _along_cuts_with_ties(a0, a1, kept, tie_w)
        if cuts:
            return kept, cuts, dropped
        kept.pop()
        dropped += 1
    lo, hi = (a0, a1) if a1 >= a0 else (a1, a0)
    return [], [(lo, hi)], dropped


def flex_ties_applied(
    plan: FlexTabPlan,
) -> tuple[list[float], list[tuple[float, float]], str]:
    """Ties the cutter actually leaves. Report this, not the raw pitch list.

    If pitch ate every slit segment, drop hinge-side ticks first so the free-end
    corner still prints as a support. Only open a full U when even one tick
    leaves no cut — otherwise the report would list ties that are not there.
    """
    a0, a1 = flex_slot_span(plan)
    lo, hi = (a0, a1) if a1 >= a0 else (a1, a0)
    full = [(lo, hi)]
    if plan.tie_w <= 1e-9:
        return [], full, ""
    intended = flex_tie_along(plan)
    kept, cuts, dropped = _ties_keeping_cuts(a0, a1, intended, plan.tie_w)
    if not kept:
        return [], full, "full-u"
    return kept, cuts, ("dropped" if dropped else "")


def _world_box(
    plan: FlexTabPlan,
    *,
    t0: float,
    t1: float,
    along0: float,
    along1: float,
    z0: float,
    z1: float,
) -> AABB:
    a0, a1 = (along0, along1) if along1 >= along0 else (along1, along0)
    u0, u1 = (t0, t1) if t1 >= t0 else (t1, t0)
    v0, v1 = (z0, z1) if z1 >= z0 else (z1, z0)
    if plan.thickness_axis == "y":
        return (a0, u0, v0, a1, u1, v1)
    return (u0, a0, v0, u1, a1, v1)


def _flex_long_slit_boxes(plan: FlexTabPlan, lay: SnapLayout) -> list[AABB]:
    """Top and bottom kerfs of the U, with mousebite gaps where ties sit."""
    t0 = min(plan.outer, plan.inner) - 0.35
    t1 = max(plan.outer, plan.inner) + 0.35
    slot_z0 = max(0.25, plan.z0 - plan.slot)
    slot_z1 = min(lay.base_h - 0.15, plan.z1 + plan.slot)
    _ties, cuts, _note = flex_ties_applied(plan)
    boxes: list[AABB] = []
    for s0, s1 in cuts:
        boxes.append(
            _world_box(plan, t0=t0, t1=t1, along0=s0, along1=s1, z0=plan.z1, z1=slot_z1)
        )
        boxes.append(
            _world_box(plan, t0=t0, t1=t1, along0=s0, along1=s1, z0=slot_z0, z1=plan.z0)
        )
    return boxes


def _flex_free_end_box(plan: FlexTabPlan) -> AABB:
    """Vertical cap of a square U. Height is the tongue only (dec-004)."""
    t0 = min(plan.outer, plan.inner) - 0.35
    t1 = max(plan.outer, plan.inner) + 0.35
    a0, a1 = flex_free_along(plan)
    return _world_box(plan, t0=t0, t1=t1, along0=a0, along1=a1, z0=plan.z0, z1=plan.z1)


def _flex_u_tools(plan: FlexTabPlan, lay: SnapLayout) -> list[cq.Workplane]:
    tools = [box_aabb(*box) for box in _flex_long_slit_boxes(plan, lay)]
    tools.append(box_aabb(*_flex_free_end_box(plan)))
    return tools


def _flex_thin_box(plan: FlexTabPlan) -> AABB:
    tab_inner = plan.outer + plan.inward * plan.tab_t
    p0 = min(tab_inner, plan.inner + plan.inward * 0.08)
    p1 = max(tab_inner, plan.inner + plan.inward * 0.08)
    if plan.hinge_low:
        a0, a1 = plan.along0 + FLEX_HINGE_ROOT_MM, plan.along1
    else:
        a0, a1 = plan.along0, plan.along1 - FLEX_HINGE_ROOT_MM
    return _world_box(plan, t0=p0, t1=p1, along0=a0, along1=a1, z0=plan.z0, z1=plan.z1)


def _flex_nub_box(plan: FlexTabPlan) -> AABB:
    tab_inner = plan.outer + plan.inward * plan.tab_t
    t0 = tab_inner - plan.inward * PENETRATE_MM
    t1 = tab_inner + plan.inward * plan.nub
    return _world_box(
        plan,
        t0=t0,
        t1=t1,
        along0=plan.nub_along0,
        along1=plan.nub_along1,
        z0=plan.nub_z0,
        z1=plan.nub_z1,
    )


def apply_flex_tab(
    base: cq.Workplane,
    plan: FlexTabPlan,
    lay: SnapLayout,
) -> tuple[cq.Workplane, list[str]]:
    warnings: list[str] = []
    if plan.along1 - plan.along0 < 6.0 or plan.z1 - plan.z0 < 3.2:
        warnings.append(
            "flex_tab is shorter than 6×3.2 mm after snap/bed clamps; "
            "measure RESET before print"
        )
    if plan.tab_t + 0.2 > lay.wall:
        warnings.append("flex_tab tab_t_mm leaves almost no inner relief")
    kept, _cuts, note = flex_ties_applied(plan)
    tools = _flex_u_tools(plan, lay)
    if not tools:
        warnings.append(
            "flex_tab U-slot isolation did not fit; measure RESET before print"
        )
    elif plan.tie_w <= 1e-9 or note == "full-u" or not kept:
        warnings.append(
            "flex_tab U-slot has no CAD whiskers; the tongue hangs on a standing "
            "wall. Set tie_mm ~0.42. Do not enable slicer supports."
        )
    else:
        warnings.append(
            "flex_tab U-slot has CAD breakaway whiskers (one 0.4-nozzle line, "
            "snip after print); do not enable slicer supports on the tongue"
        )
    base = cut_all(base, tools)
    base = cut_through(base, box_aabb(*_flex_thin_box(plan)))
    base = fuse(base, box_aabb(*_flex_nub_box(plan)))
    return base, warnings


def apply_headers(
    base: cq.Workplane,
    lid_assembled: cq.Workplane,
    spec: dict[str, Any],
    lay: SnapLayout,
) -> tuple[cq.Workplane, cq.Workplane, list[str], dict[str, Any]]:
    warnings: list[str] = []
    report: dict[str, Any] = {
        "header_slot_count": 0,
        "button_face": None,
        "button_style": button_style(spec) if button_block(spec) else None,
        "inlet_cut": lay.inlet_d > 0.2,
    }
    slots = header_slot_aabbs(spec, lay)
    if slots:
        lid_assembled = cut_all(lid_assembled, [box_aabb(*box) for box in slots])
        flares = bed_face_flare_boxes_from_slots(
            slots,
            wall=lay.wall,
            outer_w=lay.outer_w,
            roof_outer=lay.outer_z,
        )
        if flares:
            lid_assembled = cut_all(lid_assembled, [box_aabb(*box) for box in flares])
        report["header_slot_count"] = len(slots)
        report["header_slots_mm"] = [
            [round(v, 3) for v in (x0, y0, x1, y1)] for x0, y0, _z0, x1, y1, _z1 in slots
        ]
        report["header_chimney"] = True
        segs = bead_x_segments(spec, lay)
        report["bead_x_segments_mm"] = [[round(a, 3), round(b, 3)] for a, b in segs]
        if len(segs) < 2:
            warnings.append(
                "header-snap: pin wells leave no 3.2 mm island for end clips; "
                "measure row x0/x1 before print"
            )
    style = button_style(spec)
    if style == "flex_tab":
        plan = flex_tab_plan(spec, lay)
        if plan is not None:
            base, flex_warns = apply_flex_tab(base, plan, lay)
            warnings.extend(flex_warns)
            kept, _cuts, _note = flex_ties_applied(plan)
            report["button_face"] = plan.face
            report["button_hinge"] = plan.hinge
            report["button_tab_mm"] = [
                round(v, 3) for v in (plan.along0, plan.along1, plan.z0, plan.z1)
            ]
            report["button_nub_mm"] = [
                round(v, 3)
                for v in (plan.nub_along0, plan.nub_along1, plan.nub_z0, plan.nub_z1)
            ]
            report["button_slot_mm"] = round(plan.slot, 3)
            report["button_isolation"] = "u-slot-ties" if kept else "u-slot"
            report["button_tie_w_mm"] = round(plan.tie_w, 3)
            report["button_tie_along_mm"] = [round(x, 3) for x in kept]
    elif style == "window":
        btn = button_cut_aabb(spec, lay)
        if btn is not None:
            base = cut_through(base, box_aabb(*btn))
            report["button_face"] = str((spec.get("button") or {}).get("face") or "plus_x")
            report["button_cut_mm"] = [round(v, 3) for v in btn]
            if _overlaps_usb(btn, lay):
                warnings.append(
                    "button window overlaps the USB cutter on +X; "
                    "measure RESET vs the jack before print"
                )
    return base, lid_assembled, warnings, report


def _overlaps_usb(btn: AABB, lay: SnapLayout) -> bool:
    usb = (
        lay.outer_l - lay.wall - 1.4,
        lay.usb_cy - lay.cut_w / 2.0,
        lay.usb_z0,
        lay.outer_l + 0.3,
        lay.usb_cy + lay.cut_w / 2.0,
        lay.usb_z1,
    )
    return (
        btn[0] < usb[3]
        and btn[3] > usb[0]
        and btn[1] < usb[4]
        and btn[4] > usb[1]
        and btn[2] < usb[5]
        and btn[5] > usb[2]
    )
