"""Synthetic round pot: cylinder, separate lid, round holes in the lid.

Test fixture only. Not a live enclosure pattern.
"""

from __future__ import annotations

import math
from typing import Any

import cadquery as cq

from fabkit.enclosure_box import EnclosureBuild
from fabkit.kernel import box_aabb, intersect_volume
from fabkit.solid import combine_disjoint, cut_through


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    case = spec.get("case") or {}
    outer_d = float(case["outer_d_mm"])
    body_h = float(case["body_h_mm"])
    lid_t = float(case["lid_t_mm"])
    vent_d = float(case["vent_d_mm"])
    vent_n = int(case["vent_n"])
    wall = float(spec.get("wall_mm") or 2.0)
    radius = outer_d / 2.0
    inner_r = radius - wall
    if inner_r <= vent_d or vent_n < 1:
        raise ValueError("round pot vents do not fit inside the wall")

    base = cq.Workplane("XY").circle(radius).extrude(body_h)
    cavity = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .circle(inner_r)
        .extrude(body_h - wall + 0.2)
    )
    base = cut_through(base, cavity)

    lid = cq.Workplane("XY").circle(radius).extrude(lid_t)
    pitch_r = inner_r * 0.55
    for index in range(vent_n):
        angle = 2.0 * math.pi * index / vent_n
        hole = (
            cq.Workplane("XY")
            .center(pitch_r * math.cos(angle), pitch_r * math.sin(angle))
            .circle(vent_d / 2.0)
            .extrude(lid_t + 0.4)
            .translate((0, 0, -0.2))
        )
        lid = cut_through(lid, hole)

    assembled = base.union(lid.translate((0, 0, body_h)))
    printable = combine_disjoint(base, lid.translate((outer_d + 6.0, 0, 0)))
    keepout = box_aabb(-1.0, -1.0, wall + 1.0, 1.0, 1.0, wall + 3.0)
    return EnclosureBuild(
        base=base,
        lid=lid,
        assembled=assembled,
        printable=printable,
        keepout=keepout,
        keepout_volume=intersect_volume(assembled, keepout),
        outer=(outer_d, outer_d, body_h + lid_t),
        report={"vent_n": vent_n, "vent_d_mm": vent_d, "outer_d_mm": outer_d},
    )
