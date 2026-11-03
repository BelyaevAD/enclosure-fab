from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cadquery as cq

from fabkit.fit import OPENING_CLEARANCE_MM, opening_cut_size
from fabkit.kernel import box_aabb, intersect_volume
from fabkit.solid import combine_disjoint
from fabkit.validate import walk_path


def _mm(spec: dict[str, Any], path: str) -> float:
    return float(walk_path(spec, path)["value"])


def _defaults(spec: dict[str, Any]) -> tuple[float, float, float]:
    wall = float(spec.get("wall_mm") or 2.0)
    gap = float(spec.get("gap_mm") or 0.4)
    clearance = float(spec.get("component_clearance_mm") or 8.0)
    return wall, gap, clearance


@dataclass
class EnclosureBuild:
    base: cq.Workplane
    lid: cq.Workplane
    assembled: cq.Workplane
    printable: cq.Workplane
    keepout: cq.Workplane
    keepout_volume: float
    outer: tuple[float, float, float]
    usb_cut_wh: tuple[float, float] = (0.0, 0.0)
    cavity_lw: tuple[float, float] = (0.0, 0.0)
    warnings: list[str] = field(default_factory=list)
    report: dict[str, Any] = field(default_factory=dict)


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    wall, gap, clearance = _defaults(spec)
    length = _mm(spec, "board.length_mm")
    width = _mm(spec, "board.width_mm")
    thick = _mm(spec, "board.thickness_mm")
    usb_w = _mm(spec, "usb.opening_wh_mm.w")
    usb_h = _mm(spec, "usb.opening_wh_mm.h")
    usb_y = _mm(spec, "usb.offset_mm.y")
    usb_z = _mm(spec, "usb.offset_mm.z")
    case = spec.get("case") or {}
    opening_clearance = float(case.get("opening_clearance_mm") or OPENING_CLEARANCE_MM)
    cut_w, cut_h = opening_cut_size(usb_w, usb_h, opening_clearance)
    # usb.offset_mm.x is a gate (must sit on the +X face); the slot is always the +X wall.

    inner_l = length + 2 * gap
    inner_w = width + 2 * gap
    inner_h = thick + clearance
    outer_l = inner_l + 2 * wall
    outer_w = inner_w + 2 * wall
    base_h = wall + inner_h

    solid = box_aabb(0, 0, 0, outer_l, outer_w, base_h)
    cavity = box_aabb(wall, wall, wall, wall + inner_l, wall + inner_w, base_h + 0.2)
    board_ox, board_oy, board_oz = wall + gap, wall + gap, wall
    usb_cy = board_oy + usb_y
    usb_cz = board_oz + usb_z
    slot_box = box_aabb(
        outer_l - wall - 0.2,
        usb_cy - cut_w / 2.0,
        usb_cz - cut_h / 2.0,
        outer_l + 0.2,
        usb_cy + cut_w / 2.0,
        usb_cz + cut_h / 2.0,
    )
    base = solid.cut(cavity).cut(slot_box)

    lid = box_aabb(0, 0, 0, outer_l, outer_w, wall)
    assembled = base.union(lid.translate((0, 0, base_h)))
    printable = combine_disjoint(base, lid.translate((outer_l + 5.0, 0, 0)))

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
    return EnclosureBuild(
        base=base,
        lid=lid,
        assembled=assembled,
        printable=printable,
        keepout=keepout,
        keepout_volume=intersect_volume(assembled, keepout),
        outer=(outer_l, outer_w, base_h + wall),
        usb_cut_wh=(cut_w, cut_h),
    )
