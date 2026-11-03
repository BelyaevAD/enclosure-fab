"""Clamshell with snap beads, corner posts, USB window, inlet U-slot.

Print orientation: both halves roof/floor on the bed, no supports.
A 1.0 mm lid rib cannot reach the PCB under a 9.5 / 3.5 split — press pads
are computed to the board top when case.press_board is true. press_board
false emits no pads (USB-A can / tall parts stay clear of the lid).

Lid: extrude the skirt frame from the roof face (clean-solid). Press is
corner pads in leftover X islands (chimney wells stay inset). Ligament-end
pads only if a SKU ever loses those islands — not long ±Y ribs across slots.

Snap: groove is cut into the wall from the inner face; the bead sits on the
outer skirt. With headers the bead is two end clips, not a full ±Y lock.
`case.lid_open_usb` drops the +X lid rim (U-bay) so a tall USB can is not
pinched; the roof plate stays. USB z is the shell centre from the PCB
bottom (board_oz).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import cadquery as cq

from fabkit.enclosure_box import EnclosureBuild
from fabkit.kernel import box_aabb, intersect_volume
from fabkit.snap_geom import layout_from_spec, layout_report
from fabkit.solid import PENETRATE_MM, combine_disjoint, cut_through, fuse
from fabkit.validate import walk_path
from fabkit.headers import (
    apply_headers,
    bead_x_segments,
    button_vent_exclude,
    header_block,
)
from fabkit.vents import SnapVentCtx, apply_snap_vents, lid_roof_slots, vent_block

PRESS_PAD_L_MM = 2.2
PRESS_PAD_W_MM = 1.2


def _lid_blank(
    outer_l: float,
    outer_w: float,
    roof_h: float,
    skirt_h: float,
    sx0: float,
    sy0: float,
    sx1: float,
    sy1: float,
    sw: float,
) -> cq.Workplane:
    """Roof plate, then extrude the skirt frame from its inner face.

    Do not union a second box through the roof — that leaves the roof's
    inner face inside the skirt (stacked faces at the transition).
    """
    lid = (
        cq.Workplane("XY")
        .center(outer_l / 2.0, outer_w / 2.0)
        .rect(outer_l, outer_w)
        .extrude(roof_h)
    )
    return (
        lid.faces(">Z")
        .workplane()
        .rect(sx1 - sx0, sy1 - sy0)
        .rect((sx1 - sx0) - 2.0 * sw, (sy1 - sy0) - 2.0 * sw)
        .extrude(skirt_h)
    )


def press_pad_boxes(
    *,
    pocket_x0: float,
    pocket_y0: float,
    pocket_x1: float,
    pocket_y1: float,
    roof_h: float,
    rib_h: float,
    snap: float,
    outer_l: float,
    wall: float,
    usb_cuts_lid: bool,
    header_mode: bool = False,
    lid_slot_xy: list[tuple[float, float, float, float]] | None = None,
) -> list[tuple[float, float, float, float, float, float]]:
    """Print-CS AABBs of press pads.

    Chimney wells stay inset (end rails ≥ LID_X_MARGIN) so corner pads sit
    in the leftover X islands. If a SKU ever opens both short ends, pads
    fall back to the ligaments. Pin-row slots occupy the ±Y islands: then
    two pads on the Y midline (header-snap).
    """
    pad_l, pad_w = PRESS_PAD_L_MM, PRESS_PAD_W_MM
    slot_x0, slot_x1 = _print_slot_x_span(lid_slot_xy, outer_l)
    usb_x0 = (outer_l - wall - 1.4) if usb_cuts_lid else outer_l + 10.0
    xs: list[float] = []
    minus_end = min(pocket_x1, slot_x0)
    if minus_end - pocket_x0 >= pad_l + 0.25:
        xs.append(pocket_x0 + 0.15)
    plus_start = max(pocket_x0, slot_x1)
    plus_end = min(pocket_x1, usb_x0)
    if plus_end - plus_start >= pad_l + 0.25:
        xs.append(plus_end - pad_l - 0.15)
    z0, z1 = roof_h - PENETRATE_MM, roof_h + rib_h
    if header_mode:
        y_mid = 0.5 * (pocket_y0 + pocket_y1) - pad_w / 2.0
        if y_mid < pocket_y0 or y_mid + pad_w > pocket_y1:
            return []
        return [(x0, y_mid, z0, x0 + pad_l, y_mid + pad_w, z1) for x0 in xs]
    if not xs and lid_slot_xy:
        return _ligament_end_pads(
            lid_slot_xy, pocket_x0, pocket_x1, z0, z1, pad_l, pad_w
        )
    y_lo = pocket_y0 + snap + 0.15
    y_hi = pocket_y1 - snap - 0.15 - pad_w
    if y_hi < y_lo - 1e-9 or not xs:
        return []
    return [
        (x0, y0, z0, x0 + pad_l, y0 + pad_w, z1)
        for x0 in xs
        for y0 in (y_lo, y_hi)
    ]


def _print_slot_x_span(
    lid_slot_xy: list[tuple[float, float, float, float]] | None, outer_l: float
) -> tuple[float, float]:
    if not lid_slot_xy:
        return 6.0, outer_l - 6.0
    return min(s[0] for s in lid_slot_xy), max(s[2] for s in lid_slot_xy)


def _ligament_end_pads(
    lid_slot_xy: list[tuple[float, float, float, float]],
    pocket_x0: float,
    pocket_x1: float,
    z0: float,
    z1: float,
    pad_l: float,
    pad_w: float,
) -> list[tuple[float, float, float, float, float, float]]:
    """Print-CS pads on the bars between chimney wells, at both X ends."""
    slots = sorted(lid_slot_xy, key=lambda s: s[1])
    ys: list[float] = []
    for left, right in zip(slots, slots[1:]):
        ly0, ly1 = left[3], right[1]
        if ly1 - ly0 >= pad_w + 0.3:
            ys.append(0.5 * (ly0 + ly1) - pad_w / 2.0)
    if not ys:
        return []
    xs = [pocket_x0 + 0.15, pocket_x1 - pad_l - 0.15]
    return [
        (x0, y0, z0, x0 + pad_l, y0 + pad_w, z1)
        for x0 in xs
        for y0 in ys
        if x0 + pad_l <= pocket_x1 + 1e-9
    ]


def slots_print_xy(
    ctx: SnapVentCtx, slot_w: float, ligament: float
) -> list[tuple[float, float, float, float]]:
    """Roof-slot XY in print CS (Y flips with the 180° X rotation)."""
    boxes: list[tuple[float, float, float, float]] = []
    for x0, y0, _z0, x1, y1, _z1 in lid_roof_slots(ctx, slot_w, ligament):
        boxes.append((x0, ctx.outer_w - y1, x1, ctx.outer_w - y0))
    return boxes


def aabbs_overlap_xy(
    a: tuple[float, float, float, float, float, float],
    slot_xy: tuple[float, float, float, float],
) -> bool:
    ax0, ay0, _az0, ax1, ay1, _az1 = a
    bx0, by0, bx1, by1 = slot_xy
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def _template_sha256() -> str:
    digest = hashlib.sha256()
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


def _vent_ctx(lay) -> SnapVentCtx:
    inlet_y0 = lay.board_oy + lay.width / 2.0 - lay.inlet_d / 2.0
    return SnapVentCtx(
        wall=lay.wall,
        outer_l=lay.outer_l,
        outer_w=lay.outer_w,
        base_h=lay.base_h,
        roof_h=lay.roof_h,
        groove_z0=lay.groove_z0,
        inlet_y0=inlet_y0,
        inlet_d=lay.inlet_d,
        fit=lay.fit,
        skirt_h=lay.skirt_h,
    )


def snap_press_from_spec(
    spec: dict[str, Any],
) -> tuple[list[tuple[float, float, float, float, float, float]], SnapVentCtx]:
    """Pads and vent ctx from the same millimetres `build_parts` uses."""
    lay = layout_from_spec(spec)
    ctx = _vent_ctx(lay)
    if not lay.press_board:
        return [], ctx
    cfg = vent_block(spec)
    lid_slot_xy: list[tuple[float, float, float, float]] = []
    if cfg is not None and "lid" in cfg["faces"]:
        lid_slot_xy = slots_print_xy(ctx, cfg["slot_w"], cfg["ligament"])
    pads = press_pad_boxes(
        pocket_x0=lay.sx0 + lay.sw,
        pocket_y0=lay.sy0 + lay.sw,
        pocket_x1=lay.sx1 - lay.sw,
        pocket_y1=lay.sy1 - lay.sw,
        roof_h=lay.roof_h,
        rib_h=lay.rib_h,
        snap=lay.snap,
        outer_l=lay.outer_l,
        wall=lay.wall,
        # Lid is never punched for USB; pads may use leftover X islands.
        usb_cuts_lid=False,
        header_mode=header_block(spec) is not None,
        lid_slot_xy=lid_slot_xy or None,
    )
    return pads, ctx


def _engage_probe(lay, plus: bool) -> cq.Workplane | None:
    span = lay.engage_plus_y if plus else lay.engage_minus_y
    z0 = max(lay.bead_z0_asm, lay.groove_z0)
    z1 = min(lay.bead_z1_asm, lay.groove_z1)
    if span.y1 - span.y0 <= 1e-9 or z1 - z0 <= 1e-9:
        return None
    return box_aabb(lay.bead_x0, span.y0, z0, lay.bead_x1, span.y1, z1)


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    lay = layout_from_spec(spec)
    wall = lay.wall
    length = lay.length
    width = lay.width
    snap = lay.snap
    outer_l = lay.outer_l
    outer_w = lay.outer_w
    base_h = lay.base_h
    roof_h = lay.roof_h
    floor = lay.floor
    board_ox = lay.board_ox
    board_oy = lay.board_oy
    board_oz = lay.board_oz

    cavity = box_aabb(wall, wall, floor, outer_l - wall, outer_w - wall, base_h + 0.2)
    base = cut_through(box_aabb(0, 0, 0, outer_l, outer_w, base_h), cavity)

    usb_z1_cut = lay.usb_z1
    if lay.lid_open_usb:
        usb_z1_cut = max(lay.usb_z1, base_h + 0.25)
    usb_cut = box_aabb(
        outer_l - wall - 1.4,
        lay.usb_cy - lay.cut_w / 2.0,
        lay.usb_z0,
        outer_l + 0.3,
        lay.usb_cy + lay.cut_w / 2.0,
        usb_z1_cut,
    )
    base = cut_through(base, usb_cut)

    inlet_y0 = board_oy + width / 2.0 - max(lay.inlet_d, 0.0) / 2.0
    if lay.inlet_d > 0.2:
        inlet_cut = box_aabb(
            -0.3, inlet_y0, base_h - lay.inlet_d, wall + 0.4, inlet_y0 + lay.inlet_d, base_h + 0.3
        )
        base = cut_through(base, inlet_cut)

    # Groove into the wall from the inner face (tiny penetrate so the cut opens).
    base = cut_through(
        base,
        box_aabb(
            wall + 1.0,
            outer_w - wall - PENETRATE_MM,
            lay.groove_z0,
            outer_l - wall - 1.0,
            outer_w - wall + snap,
            lay.groove_z1,
        ),
    )
    base = cut_through(
        base,
        box_aabb(
            wall + 1.0,
            wall - snap,
            lay.groove_z0,
            outer_l - wall - 1.0,
            wall + PENETRATE_MM,
            lay.groove_z1,
        ),
    )

    post = lay.post_size
    inset = lay.post_inset
    posts = [
        box_aabb(px, py, floor - PENETRATE_MM, px + post, py + post, board_oz - 0.05)
        for px, py in (
            (board_ox + inset, board_oy + inset),
            (board_ox + length - inset - post, board_oy + inset),
            (board_ox + inset, board_oy + width - inset - post),
            (board_ox + length - inset - post, board_oy + width - inset - post),
        )
    ]
    base = fuse(base, combine_disjoint(*posts))

    vent_ctx = _vent_ctx(lay)

    # Lid in print pose: outer roof on the bed, skirt and pads +Z (no supports).
    lid = _lid_blank(
        outer_l, outer_w, roof_h, lay.skirt_h, lay.sx0, lay.sy0, lay.sx1, lay.sy1, lay.sw
    )
    if lay.lid_open_usb:
        # Print CS: drop the +X skirt (and ±Y tails) from the USB can onward.
        # Roof plate stays — this is not a C-punch through the lid.
        lid = cut_through(
            lid,
            box_aabb(
                lay.usb_skirt_stop_x,
                -0.4,
                roof_h - PENETRATE_MM,
                outer_l + 0.5,
                outer_w + 0.4,
                roof_h + lay.skirt_h + 0.4,
            ),
        )
    # Bead on the outer skirt face (print −Y → assembled +Y after the 180° flip).
    # Header-snap: two short clips outside the pin wells, not a full-length lock.
    bead_boxes = []
    for x0, x1 in bead_x_segments(spec, lay):
        bead_boxes.append(
            box_aabb(
                x0,
                lay.sy1 - PENETRATE_MM,
                lay.bead_z0_print,
                x1,
                lay.sy1 + snap,
                lay.bead_z1_print,
            )
        )
        bead_boxes.append(
            box_aabb(
                x0,
                lay.sy0 - snap,
                lay.bead_z0_print,
                x1,
                lay.sy0 + PENETRATE_MM,
                lay.bead_z1_print,
            )
        )
    lid = fuse(lid, combine_disjoint(*bead_boxes))

    pads, _ = snap_press_from_spec(spec)
    if pads:
        lid = fuse(lid, combine_disjoint(*[box_aabb(*box) for box in pads]))

    lid_assembled = lid.rotate((0, 0, 0), (1, 0, 0), 180).translate(
        (0, outer_w, base_h + roof_h)
    )
    # Never punch the lid with the USB cutter — roof stays intact.
    if lay.inlet_d > 0.2:
        lid_assembled = cut_through(
            lid_assembled,
            box_aabb(
                -0.3,
                inlet_y0,
                base_h - 0.2,
                wall + 0.4,
                inlet_y0 + lay.inlet_d,
                base_h + roof_h + 0.2,
            ),
        )
    base, lid_assembled, vent_warnings = apply_snap_vents(
        base,
        lid_assembled,
        spec,
        vent_ctx,
        wall_exclude=button_vent_exclude(spec, lay),
    )
    base, lid_assembled, header_warnings, header_report = apply_headers(
        base, lid_assembled, spec, lay
    )
    # Rebuild printable lid from the assembled solid so USB/inlet/vent cuts stay in sync.
    lid_printable = lid_assembled.rotate((0, 0, 0), (1, 0, 0), 180).translate(
        (0, outer_w, base_h + roof_h)
    )

    assembled = fuse(base, lid_assembled)
    printable = combine_disjoint(base, lid_printable.translate((outer_l + 5.0, 0, 0)))

    plus_probe = _engage_probe(lay, True)
    minus_probe = _engage_probe(lay, False)
    plus_vol = intersect_volume(assembled, plus_probe) if plus_probe is not None else 0.0
    minus_vol = intersect_volume(assembled, minus_probe) if minus_probe is not None else 0.0
    plus_base = intersect_volume(base, plus_probe) if plus_probe is not None else 0.0
    minus_base = intersect_volume(base, minus_probe) if minus_probe is not None else 0.0

    ko = walk_path(spec, "keepout.board")
    kmin = [float(v) for v in ko["min"]]
    kmax = [float(v) for v in ko["max"]]
    keepout = box_aabb(
        board_ox + kmin[0],
        board_oy + kmin[1],
        board_oz + kmin[2],
        board_ox + kmax[0],
        board_oy + kmax[1],
        board_oz + kmax[2],
    )
    report = layout_report(lay)
    report["template_sha256"] = _template_sha256()
    cfg = vent_block(spec)
    if cfg is not None and "lid" in cfg["faces"]:
        roof_slots = lid_roof_slots(vent_ctx, cfg["slot_w"], cfg["ligament"])
        report["lid_exhaust"] = "roof-bed-well"
        report["lid_well"] = True
        report["lid_slot_open_ends"] = bool(roof_slots and roof_slots[0][0] < 0)
        report["lid_slot_count"] = len(roof_slots)
    report["snap_engage_plus_volume_mm3"] = plus_vol
    report["snap_engage_minus_volume_mm3"] = minus_vol
    report["snap_groove_plus_empty_mm3"] = plus_base
    report["snap_groove_minus_empty_mm3"] = minus_base
    report.update(header_report)
    warnings = list(lay.warnings)
    warnings.extend(vent_warnings)
    warnings.extend(header_warnings)
    return EnclosureBuild(
        base=base,
        lid=lid_printable,
        assembled=assembled,
        printable=printable,
        keepout=keepout,
        keepout_volume=intersect_volume(assembled, keepout),
        outer=(outer_l, outer_w, base_h + roof_h),
        usb_cut_wh=(lay.cut_w, lay.cut_h),
        cavity_lw=lay.cavity_lw,
        warnings=warnings,
        report=report,
    )
