"""Screw-lid outer shell around a rectangular device envelope.

The device (G202 class) is dropped in whole. Not a PCB snap, not a copy of
the OEM housing. Coordinate system: origin at the outer box corner;
device nest after a −X gallery; terminals face +X into the cable chamber;
+Z up. Print: base floor on the bed, lid outer roof on the bed.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cadquery as cq

from fabkit.enclosure_box import EnclosureBuild
from fabkit.fit import LID_FIT_MM, MIN_FEATURE_MM, OPENING_CLEARANCE_MM, PRINT_POSE_GAP_MM
from fabkit.kernel import box_aabb, intersect_volume
from fabkit.solid import PENETRATE_MM, combine_disjoint, cut_all, cut_through, fuse
from fabkit.validate import walk_path

TEMPLATE_ID = "enclosure_shell"
# ruthex M3 standard / CNC Kitchen datasheet hole. Spec millimetres are the
# recommended plastic bore; we do not bake one filament's shrink into CAD.
INSERT_HOLE_D_MM = 4.0
INSERT_BOSS_D_MM = 8.8
INSERT_DEPTH_MM = 6.0
SCREW_CLEAR_D_MM = 3.4
# Cembre / Bimed panel holes, plus FDM opening clearance in the cutter.
GLAND_HV_D_MM = 16.2
GLAND_LV_D_MM = 12.5
SMA_CLEARANCE_D_MM = 20.0
LIP_MM = 2.0
GALLERY_MM = 8.0
CHAMBER_MM = 26.0
PARTITION_T_MM = 2.4
HV_WIDTH_MM = 32.0
FLOOR_MM = 3.0
LID_MM = 2.5
GAP_XY_MM = 1.5
GAP_Z_MM = 3.0
BOSS_INSET_MM = 6.5
BED_CHAMFER_MM = 0.6


def _mm(spec: dict[str, Any], path: str) -> float:
    return float(walk_path(spec, path)["value"])


def _template_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ShellLayout:
    wall: float
    floor: float
    lid_h: float
    lip: float
    lid_fit: float
    device_l: float
    device_w: float
    device_h: float
    gap_xy: float
    gap_z: float
    gallery: float
    chamber: float
    pocket_l: float
    pocket_w: float
    pocket_h: float
    partition_t: float
    hv_w: float
    lv_w: float
    insert_hole: float
    insert_boss: float
    insert_depth: float
    screw_clear: float
    boss_inset: float
    gland_hv: float
    gland_lv: float
    sma_x: float
    sma_y: float
    sma_d: float
    sma_slot: bool
    corner_r: float
    outer_l: float
    outer_w: float
    base_h: float
    nest_x0: float
    nest_y0: float
    nest_z0: float
    device_ox: float
    device_oy: float
    device_oz: float
    chamber_x0: float
    part_y0: float
    warnings: tuple[str, ...]


def layout_from_spec(spec: dict[str, Any]) -> ShellLayout:
    wall = float(spec.get("wall_mm") or 3.0)
    shell = spec.get("shell") or {}
    gap_xy = float(shell.get("gap_xy_mm") if shell.get("gap_xy_mm") is not None else GAP_XY_MM)
    gap_z = float(shell.get("gap_z_mm") if shell.get("gap_z_mm") is not None else GAP_Z_MM)
    gallery = float(shell.get("gallery_mm") if shell.get("gallery_mm") is not None else GALLERY_MM)
    chamber = float(
        shell.get("cable_chamber_mm") if shell.get("cable_chamber_mm") is not None else CHAMBER_MM
    )
    partition_t = float(
        shell.get("partition_t_mm") if shell.get("partition_t_mm") is not None else PARTITION_T_MM
    )
    hv_w = float(shell.get("hv_width_mm") if shell.get("hv_width_mm") is not None else HV_WIDTH_MM)
    floor = float(shell.get("floor_mm") if shell.get("floor_mm") is not None else FLOOR_MM)
    lid_h = float(shell.get("lid_mm") if shell.get("lid_mm") is not None else LID_MM)
    lip = float(shell.get("lip_mm") if shell.get("lip_mm") is not None else LIP_MM)
    lid_fit = float(shell.get("lid_fit_mm") if shell.get("lid_fit_mm") is not None else LID_FIT_MM)
    insert_hole = float(
        shell.get("insert_hole_d_mm") if shell.get("insert_hole_d_mm") is not None else INSERT_HOLE_D_MM
    )
    insert_boss = float(
        shell.get("insert_boss_d_mm") if shell.get("insert_boss_d_mm") is not None else INSERT_BOSS_D_MM
    )
    insert_depth = float(
        shell.get("insert_depth_mm") if shell.get("insert_depth_mm") is not None else INSERT_DEPTH_MM
    )
    screw_clear = float(
        shell.get("screw_clear_d_mm") if shell.get("screw_clear_d_mm") is not None else SCREW_CLEAR_D_MM
    )
    boss_inset = float(
        shell.get("boss_inset_mm") if shell.get("boss_inset_mm") is not None else BOSS_INSET_MM
    )
    gland_hv = float(
        shell.get("gland_hv_d_mm") if shell.get("gland_hv_d_mm") is not None else GLAND_HV_D_MM
    )
    gland_lv = float(
        shell.get("gland_lv_d_mm") if shell.get("gland_lv_d_mm") is not None else GLAND_LV_D_MM
    )
    corner_r = float(shell.get("corner_r_mm") if shell.get("corner_r_mm") is not None else 0.0)
    sma = shell.get("sma") or {}
    sma_x = _mm(spec, "shell.sma.x_mm")
    sma_y = _mm(spec, "shell.sma.y_mm")
    sma_d = float(sma.get("clearance_d_mm") if sma.get("clearance_d_mm") is not None else SMA_CLEARANCE_D_MM)
    # Closed well is the default: a U-slot to −X is a second exit on the
    # SMA-end short face (wired-switch / pre-fitted whip). Opt in per spec.
    sma_slot = bool(sma.get("slot_to_minus_x") if sma.get("slot_to_minus_x") is not None else False)

    device_l = _mm(spec, "device.length_mm")
    device_w = _mm(spec, "device.width_mm")
    device_h = _mm(spec, "device.height_mm")
    pocket_l = device_l + 2.0 * gap_xy
    pocket_w = device_w + 2.0 * gap_xy
    pocket_h = device_h + gap_z
    lv_w = pocket_w - partition_t - hv_w
    nest_x0 = wall + gallery
    nest_y0 = wall
    nest_z0 = floor
    outer_l = wall + gallery + pocket_l + chamber + wall
    outer_w = wall + pocket_w + wall
    base_h = floor + pocket_h
    warnings: list[str] = []
    if lv_w + 1e-9 < 12.0:
        warnings.append(
            f"LV chamber width {lv_w:.1f} mm is tight for an M12 gland + nut; "
            "widen hv_width_mm or the device pocket"
        )
    if corner_r + 0.8 >= wall and corner_r > 0.05:
        warnings.append(
            f"shell.corner_r_mm={corner_r} would eat wall_mm={wall}; "
            "outer fillet skipped (R3–R5 needs wall > R or corner ears)"
        )
        corner_r = 0.0
    if insert_depth + 0.4 > base_h - 0.8:
        warnings.append(
            f"insert_depth_mm={insert_depth} nearly through the {base_h:.1f} mm base"
        )
    if gland_hv + 2.0 > chamber:
        warnings.append(
            f"M16 gland OD / nut may not sit in cable_chamber_mm={chamber}"
        )
    for label, value in (
        ("wall_mm", wall),
        ("partition_t_mm", partition_t),
        ("floor_mm", floor),
        ("lid_mm", lid_h),
    ):
        if value + 1e-9 < MIN_FEATURE_MM:
            raise ValueError(f"{label}={value} < {MIN_FEATURE_MM}")
    if lv_w <= 0 or hv_w <= 0:
        raise ValueError("HV/LV partition leaves a non-positive chamber")
    return ShellLayout(
        wall=wall,
        floor=floor,
        lid_h=lid_h,
        lip=lip,
        lid_fit=lid_fit,
        device_l=device_l,
        device_w=device_w,
        device_h=device_h,
        gap_xy=gap_xy,
        gap_z=gap_z,
        gallery=gallery,
        chamber=chamber,
        pocket_l=pocket_l,
        pocket_w=pocket_w,
        pocket_h=pocket_h,
        partition_t=partition_t,
        hv_w=hv_w,
        lv_w=lv_w,
        insert_hole=insert_hole,
        insert_boss=insert_boss,
        insert_depth=insert_depth,
        screw_clear=screw_clear,
        boss_inset=boss_inset,
        gland_hv=gland_hv,
        gland_lv=gland_lv,
        sma_x=sma_x,
        sma_y=sma_y,
        sma_d=sma_d,
        sma_slot=sma_slot,
        corner_r=corner_r,
        outer_l=outer_l,
        outer_w=outer_w,
        base_h=base_h,
        nest_x0=nest_x0,
        nest_y0=nest_y0,
        nest_z0=nest_z0,
        device_ox=nest_x0 + gap_xy,
        device_oy=nest_y0 + gap_xy,
        device_oz=nest_z0,
        chamber_x0=nest_x0 + pocket_l,
        part_y0=nest_y0 + lv_w,
        warnings=tuple(warnings),
    )


def boss_xy(lay: ShellLayout) -> tuple[tuple[float, float], ...]:
    x0, x1 = lay.boss_inset, lay.outer_l - lay.boss_inset
    y0, y1 = lay.boss_inset, lay.outer_w - lay.boss_inset
    return ((x0, y0), (x0, y1), (x1, y0), (x1, y1))


def teardrop_along_x(x0: float, x1: float, cy: float, cz: float, d: float) -> cq.Workplane:
    """Standing-wall gland bore: circle + 45° peak toward +Z. No FDM thread."""
    r = d / 2.0
    peak = r * math.sqrt(2.0)
    dx = (x1 - x0) + 0.4
    x_start = x0 - 0.2
    half = r / math.sqrt(2.0)
    circ = (
        cq.Workplane("YZ")
        .workplane(offset=x_start)
        .moveTo(cy, cz)
        .circle(r)
        .extrude(dx)
    )
    tri = (
        cq.Workplane("YZ")
        .workplane(offset=x_start)
        .polyline(
            [
                (cy - half, cz + half),
                (cy + half, cz + half),
                (cy, cz + peak),
            ]
        )
        .close()
        .extrude(dx)
    )
    return fuse(circ, tri)


def _z_cyl(x: float, y: float, z0: float, z1: float, d: float) -> cq.Workplane:
    if z1 <= z0:
        raise ValueError(f"degenerate Z cylinder {z0}→{z1}")
    r = d / 2.0
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .moveTo(x, y)
        .circle(r)
        .extrude(z1 - z0)
    )


def _lid_blank(lay: ShellLayout) -> cq.Workplane:
    """Outer roof on the bed; locating lip +Z (print pose)."""
    lid = (
        cq.Workplane("XY")
        .center(lay.outer_l / 2.0, lay.outer_w / 2.0)
        .rect(lay.outer_l, lay.outer_w)
        .extrude(lay.lid_h)
    )
    if lay.lip <= 0.05:
        return lid
    sx0 = lay.wall + lay.lid_fit
    sy0 = lay.wall + lay.lid_fit
    sx1 = lay.outer_l - lay.wall - lay.lid_fit
    sy1 = lay.outer_w - lay.wall - lay.lid_fit
    lip_t = min(lay.wall - 0.6, 1.5)
    if sx1 - sx0 <= 2.0 * lip_t or sy1 - sy0 <= 2.0 * lip_t:
        return lid
    return (
        lid.faces(">Z")
        .workplane()
        .rect(sx1 - sx0, sy1 - sy0)
        .rect((sx1 - sx0) - 2.0 * lip_t, (sy1 - sy0) - 2.0 * lip_t)
        .extrude(lay.lip)
    )


def _assembled_lid(lid_print: cq.Workplane, lay: ShellLayout) -> cq.Workplane:
    return lid_print.rotate((0, 0, 0), (1, 0, 0), 180).translate(
        (0, lay.outer_w, lay.base_h + lay.lid_h)
    )


def _sma_cutters(lay: ShellLayout) -> list[cq.Workplane]:
    cx = lay.device_ox + lay.sma_x
    cy = lay.device_oy + lay.sma_y
    r = lay.sma_d / 2.0
    z0 = lay.base_h - lay.lip - 0.3
    z1 = lay.base_h + lay.lid_h + 0.3
    tools = [_z_cyl(cx, cy, z0, z1, lay.sma_d)]
    if lay.sma_slot:
        tools.append(box_aabb(-0.4, cy - r, z0, cx, cy + r, z1))
    return tools


def _gland_z(lay: ShellLayout, d: float) -> float:
    r = d / 2.0
    peak = r * math.sqrt(2.0)
    lo = lay.floor + r + 3.2
    hi = lay.base_h - peak - 1.2
    if hi <= lo:
        return lay.floor + (lay.pocket_h / 2.0)
    return min(max(lay.floor + 12.0, lo), hi)


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    lay = layout_from_spec(spec)
    warnings = list(lay.warnings)
    solid = box_aabb(0, 0, 0, lay.outer_l, lay.outer_w, lay.base_h)
    if lay.corner_r > 0.05:
        try:
            solid = cq.Workplane(solid.val()).edges("|Z").fillet(lay.corner_r)
        except Exception as exc:  # noqa: BLE001 — fillet is optional cosmetics
            warnings.append(f"outer fillet R{lay.corner_r} skipped: {exc}")
    cavity = box_aabb(
        lay.wall,
        lay.wall,
        lay.floor,
        lay.outer_l - lay.wall,
        lay.outer_w - lay.wall,
        lay.base_h + 0.3,
    )
    base = cut_through(solid, cavity)

    partition = box_aabb(
        lay.chamber_x0 - PENETRATE_MM,
        lay.part_y0,
        lay.floor - PENETRATE_MM,
        lay.outer_l - lay.wall + PENETRATE_MM,
        lay.part_y0 + lay.partition_t,
        lay.base_h + 0.05,
    )
    base = fuse(base, partition)

    boss_r = lay.insert_boss / 2.0
    bosses = [
        _z_cyl(x, y, lay.floor - PENETRATE_MM, lay.base_h, lay.insert_boss)
        for x, y in boss_xy(lay)
    ]
    base = fuse(base, combine_disjoint(*bosses))
    insert_tools = [
        _z_cyl(
            x,
            y,
            lay.base_h - lay.insert_depth,
            lay.base_h + 0.3,
            lay.insert_hole,
        )
        for x, y in boss_xy(lay)
    ]
    base = cut_all(base, insert_tools)

    gland_clear = OPENING_CLEARANCE_MM
    lv_cy = lay.nest_y0 + lay.lv_w / 2.0
    hv_cy = lay.part_y0 + lay.partition_t + lay.hv_w / 2.0
    lv_d = lay.gland_lv + 2.0 * gland_clear
    hv_d = lay.gland_hv + 2.0 * gland_clear
    lv_cz = _gland_z(lay, lv_d)
    hv_cz = _gland_z(lay, hv_d)
    x_wall0 = lay.outer_l - lay.wall - 0.2
    x_wall1 = lay.outer_l + 0.2
    base = cut_all(
        base,
        [
            teardrop_along_x(x_wall0, x_wall1, lv_cy, lv_cz, lv_d),
            teardrop_along_x(x_wall0, x_wall1, hv_cy, hv_cz, hv_d),
        ],
    )
    if BED_CHAMFER_MM > 0.05:
        try:
            base = cq.Workplane(base.val()).faces("<Z").edges().chamfer(BED_CHAMFER_MM)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"bed chamfer skipped: {exc}")

    lid_print = _lid_blank(lay)
    lid_assembled = _assembled_lid(lid_print, lay)
    lip_clear = []
    if lay.lip > 0.05:
        lip_clear = [
            _z_cyl(
                x,
                y,
                lay.base_h - lay.lip - 0.3,
                lay.base_h + 0.05,
                lay.insert_boss + 0.8,
            )
            for x, y in boss_xy(lay)
        ]
    screw_tools = [
        _z_cyl(
            x,
            y,
            lay.base_h - lay.lip - 0.3,
            lay.base_h + lay.lid_h + 0.3,
            lay.screw_clear,
        )
        for x, y in boss_xy(lay)
    ]
    lid_assembled = cut_all(lid_assembled, lip_clear + screw_tools + _sma_cutters(lay))
    lid_printable = _assembled_lid(lid_assembled, lay)

    assembled = fuse(base, lid_assembled)
    printable = combine_disjoint(
        base, lid_printable.translate((lay.outer_l + PRINT_POSE_GAP_MM, 0, 0))
    )

    ko = walk_path(spec, "keepout.device")
    kmin = [float(v) for v in ko["min"]]
    kmax = [float(v) for v in ko["max"]]
    keepout = box_aabb(
        lay.device_ox + kmin[0],
        lay.device_oy + kmin[1],
        lay.device_oz + kmin[2],
        lay.device_ox + kmax[0],
        lay.device_oy + kmax[1],
        lay.device_oz + kmax[2],
    )
    report = {
        "template_id": TEMPLATE_ID,
        "template_sha256": _template_sha256(),
        "pattern": "device-shell",
        "outer_mm": [lay.outer_l, lay.outer_w, lay.base_h + lay.lid_h],
        "pocket_mm": [lay.pocket_l, lay.pocket_w, lay.pocket_h],
        "gallery_mm": lay.gallery,
        "cable_chamber_mm": lay.chamber,
        "partition_t_mm": lay.partition_t,
        "hv_width_mm": lay.hv_w,
        "lv_width_mm": lay.lv_w,
        "boss_xy_mm": [list(xy) for xy in boss_xy(lay)],
        "gland_lv_cut_d_mm": lv_d,
        "gland_hv_cut_d_mm": hv_d,
        "gland_lv_yz_mm": [lv_cy, lv_cz],
        "gland_hv_yz_mm": [hv_cy, hv_cz],
        "sma_world_xy_mm": [lay.device_ox + lay.sma_x, lay.device_oy + lay.sma_y],
        "sma_slot": lay.sma_slot,
        "insert_hole_d_mm": lay.insert_hole,
        "closure": "m3-heat-set",
        "device_origin_mm": [lay.device_ox, lay.device_oy, lay.device_oz],
    }
    warnings.append(
        "FDM PETG/ASA shell is not a certified UL94 / IEC mains enclosure; "
        "heat-set M3 + bought glands; no snap as the only latch"
    )
    if abs(lay.device_l - 96.5) < 0.2:
        warnings.append(
            "device.length_mm=96.5 looks like G202 Plus docs; "
            "the 80 mm listing is a different housing revision"
        )
    if abs(lay.device_l - 80.0) < 0.2:
        warnings.append(
            "device.length_mm=80 is the short listing; G202/G202 Plus docs "
            "also quote 96.5×50×31.5 — caliper the unit before print"
        )
    return EnclosureBuild(
        base=base,
        lid=lid_printable,
        assembled=assembled,
        printable=printable,
        keepout=keepout,
        keepout_volume=intersect_volume(assembled, keepout),
        outer=(lay.outer_l, lay.outer_w, lay.base_h + lay.lid_h),
        usb_cut_wh=(0.0, 0.0),
        cavity_lw=(lay.pocket_l + lay.gallery + lay.chamber, lay.pocket_w),
        warnings=warnings,
        report=report,
    )
