"""Classic Mary Jane pump for a 1:6 fashion-doll last. Print sole + heel tip on Z=0.

Construction (shoemaking, not a solid brick): loft/extrude an outer upper+sole,
boolean-subtract a last that follows the insole and punches out the collar so
the foot can enter. Spec millimetres are the doll; gap_mm is per side.
C-clip is an open ring the operator snaps; the agent does not.
"""

from __future__ import annotations

from typing import Any

import cadquery as cq

from fabkit.enclosure_box import EnclosureBuild
from fabkit.fit import FOOT_GAP_MM, MIN_FEATURE_MM, PRINT_POSE_GAP_MM
from fabkit.kernel import box_aabb, intersect_volume
from fabkit.solid import combine_disjoint
from fabkit.validate import walk_path

HEEL_TIP_D_MM = 4.8
BALL_FRACTION = 0.55
VAMP_FRACTION = 0.62
LAST_PUNCH_MM = 4.0


def _mm(spec: dict[str, Any], path: str) -> float:
    return float(walk_path(spec, path)["value"])


def _xz_prism(pts: list[tuple[float, float]], half_y: float) -> cq.Workplane:
    if len(pts) < 3:
        raise ValueError("XZ profile needs at least 3 points")
    return cq.Workplane("XZ").polyline(pts).close().extrude(half_y, both=True)


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    wall = float(spec.get("wall_mm") or 1.2)
    gap = float(spec.get("gap_mm") if spec.get("gap_mm") is not None else FOOT_GAP_MM)
    foot_l = _mm(spec, "shoe.foot_length_mm")
    foot_w = _mm(spec, "shoe.foot_width_mm")
    foot_h = _mm(spec, "shoe.foot_height_mm")
    heel_lift = _mm(spec, "shoe.heel_lift_mm")
    ankle_d = _mm(spec, "shoe.ankle_diameter_mm")
    strap_w = _mm(spec, "shoe.strap_width_mm")
    strap_t = _mm(spec, "shoe.strap_thickness_mm")
    clip_gap = _mm(spec, "shoe.clip_gap_mm")

    for label, value in (
        ("wall_mm", wall),
        ("strap_thickness_mm", strap_t),
        ("strap_width_mm", strap_w),
        ("clip_gap_mm", clip_gap),
    ):
        if value + 1e-9 < MIN_FEATURE_MM:
            raise ValueError(f"{label}={value} is thinner than MIN_FEATURE_MM={MIN_FEATURE_MM}")

    cav_l = foot_l + 2.0 * gap
    cav_w = foot_w + 2.0 * gap
    half_cav = cav_w / 2.0
    half_outer = half_cav + wall
    x_cav0 = wall
    x_cav1 = wall + cav_l
    x_last0 = wall + gap
    x_last1 = x_last0 + foot_l
    x_ball = x_last0 + BALL_FRACTION * foot_l
    x_vamp = x_last0 + VAMP_FRACTION * foot_l
    outer_l = x_cav1 + wall
    heel_r = HEEL_TIP_D_MM / 2.0
    heel_cx = heel_r
    x_arch0 = heel_cx + heel_r
    sole_z = wall
    toe_cavity_h = max(foot_h * 0.55, 3.0)
    z_collar = heel_lift + foot_h
    z_clip = z_collar + 0.15

    # Last sits on the insole and punches through the collar (open instep).
    last_pts = [
        (x_cav0, heel_lift),
        (x_ball, sole_z),
        (x_cav1, sole_z),
        (x_cav1, sole_z + toe_cavity_h),
        (x_vamp, sole_z + foot_h * 0.8),
        (x_vamp, z_collar + LAST_PUNCH_MM),
        (x_cav0, z_collar + LAST_PUNCH_MM),
    ]
    last = _xz_prism(last_pts, half_cav)

    # Outer: sole on Z=0 at the ball/toe, counter at the heel, vamp closed over the toe.
    outer_pts = [
        (0.0, heel_lift),
        (x_arch0, heel_lift),
        (x_ball, 0.0),
        (outer_l, 0.0),
        (outer_l, sole_z + toe_cavity_h + wall),
        (x_vamp, sole_z + foot_h * 0.8 + wall),
        (x_vamp, z_collar + wall),
        (0.0, z_collar + wall),
    ]
    outer = _xz_prism(outer_pts, half_outer)

    heel = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(heel_cx, 0.0, 0.0))
        .circle(heel_r)
        .extrude(heel_lift + 0.45)
    )
    hull = outer.union(heel).cut(last)

    # Pointed vamp: trim the boxy toe after the last boolean.
    toe_half = max(half_cav * 0.42, 1.6)
    taper = (
        cq.Workplane("XY")
        .moveTo(x_vamp, half_outer + 2.0)
        .lineTo(outer_l + 2.0, half_outer + 2.0)
        .lineTo(outer_l + 2.0, toe_half)
        .lineTo(x_cav1 + 0.2, toe_half)
        .close()
        .extrude(z_collar + LAST_PUNCH_MM + wall + 2.0)
    )
    hull = hull.cut(taper).cut(taper.mirror("XZ"))

    inner_r = (ankle_d + 2.0 * gap) / 2.0
    outer_r = inner_r + strap_t
    ankle_x = x_cav0 + 2.2
    clip = (
        cq.Workplane("XY")
        .workplane(offset=z_clip)
        .transformed(offset=cq.Vector(ankle_x, 0.0, 0.0))
        .circle(outer_r)
        .circle(inner_r)
        .extrude(strap_w)
    )
    gap_cut = box_aabb(
        ankle_x - outer_r - 1.5,
        -clip_gap / 2.0,
        z_clip - 0.2,
        ankle_x - inner_r * 0.15,
        clip_gap / 2.0,
        z_clip + strap_w + 0.2,
    )
    clip = clip.cut(gap_cut)
    hull = hull.union(clip)

    # Keep-out is the wearable last (no collar punch), inset so it sits in the void.
    inset = 0.2
    keep_pts = [
        (x_last0 + inset, heel_lift + inset),
        (x_ball, sole_z + inset),
        (x_last1 - inset, sole_z + inset),
        (x_last1 - inset, sole_z + toe_cavity_h - inset),
        (x_vamp, sole_z + foot_h * 0.8 - inset),
        (x_last0 + inset, z_collar - inset),
    ]
    keepout = _xz_prism(keep_pts, max(foot_w / 2.0 - inset, 0.8))

    right = hull
    left = right.mirror("XZ").translate((0.0, 2.0 * half_outer + PRINT_POSE_GAP_MM, 0.0))
    printable = combine_disjoint(right, left)
    assembled = right

    bb = assembled.val().BoundingBox()
    outer_size = (float(bb.xlen), float(bb.ylen), float(bb.zlen))
    return EnclosureBuild(
        base=right,
        lid=left,
        assembled=assembled,
        printable=printable,
        keepout=keepout,
        keepout_volume=intersect_volume(assembled, keepout),
        outer=outer_size,
        cavity_lw=(round(cav_l, 3), round(cav_w, 3)),
    )
