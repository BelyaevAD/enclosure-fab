"""Closed box with a magnetic lid. Pattern `magnet-box`.

Four corner posts fused into the walls, disc-magnet cups in the posts and
in matching lid bosses that hang down. Not a device tray (no pockets, no
open well) and not a snap enclosure.

Coordinate system: origin at the outer −X/−Y/floor corner. +X and +Y are
the plan, +Z up. External L×W×H are the part. The lip drops inside the
cavity, so assembled height is base + lid plate.

Print: base floor on the bed. The lid in the 3MF is rotated 180° about X
so the smooth outer roof is on z=0 and the ribs and magnet cups face
+Z. Four corner magnets and the X of ribs are symmetric under that
turn. Assembled view stays closed (roof up). The two parts still do
not fit side by side on a 256 mm bed.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cadquery as cq

from fabkit.enclosure_box import EnclosureBuild
from fabkit.enclosure_shell import BED_CHAMFER_MM, _z_cyl
from fabkit.enclosure_tray import (
    MAGNET_CUP_EXTRA_MM,
    MAGNET_EDGE_CLEAR_MM,
    MAGNET_FIT_MM,
    MAGNET_LID_FLOOR_MM,
    MAGNET_WALL_MM,
)
from fabkit.fit import LID_FIT_MM, MIN_FEATURE_MM, PRINT_POSE_GAP_MM, wall_for_span
from fabkit.kernel import box_aabb, intersect_volume
from fabkit.solid import PENETRATE_MM, combine_disjoint, cut_all, cut_through, fuse
from fabkit.validate import walk_path

TEMPLATE_ID = "enclosure_magnet_box"
FLOOR_MM = 1.68
LID_MM = 1.26
LIP_MM = 2.0
RIB_T_MM = 1.68


def _lid_lip_t(wall: float, lid_fit: float) -> float:
    """Radial thickness of the print-bed lip. Keep ≥ MIN_FEATURE on a thin wall."""
    return min(max(wall - lid_fit - 0.15, MIN_FEATURE_MM), 1.5)


def _mm(spec: dict[str, Any], path: str) -> float:
    return float(walk_path(spec, path)["value"])


def _template_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class BoxLayout:
    wall: float
    floor: float
    lid_h: float
    lip: float
    lid_fit: float
    outer_l: float
    outer_w: float
    outer_h: float
    inner_l: float
    inner_w: float
    inner_h: float
    base_h: float
    magnet_d: float
    magnet_h: float
    magnet_fit: float
    insert_boss: float
    boss_inset: float
    rib_t: float
    warnings: tuple[str, ...]

    @property
    def magnet_cut_d(self) -> float:
        return self.magnet_d + self.magnet_fit

    @property
    def magnet_cup_h(self) -> float:
        return self.magnet_h + MAGNET_CUP_EXTRA_MM

    @property
    def lid_magnet_inner_h(self) -> float:
        """Downward boss on the lip/bed face. Outer roof stays flat."""
        needed = self.magnet_cup_h + MAGNET_LID_FLOOR_MM - self.lid_h
        return max(self.lip, needed)

    @property
    def post_top_z(self) -> float:
        """Base post stops where the lid boss meets it."""
        return self.base_h - self.lid_magnet_inner_h


def layout_from_spec(spec: dict[str, Any]) -> BoxLayout:
    wall = float(spec.get("wall_mm") or 1.26)
    box = spec.get("box") or {}
    floor = float(box.get("floor_mm") if box.get("floor_mm") is not None else FLOOR_MM)
    lid_h = float(box.get("lid_mm") if box.get("lid_mm") is not None else LID_MM)
    lip = float(box.get("lip_mm") if box.get("lip_mm") is not None else LIP_MM)
    lid_fit = float(box.get("lid_fit_mm") if box.get("lid_fit_mm") is not None else LID_FIT_MM)
    magnet_fit = float(
        box.get("magnet_fit_mm") if box.get("magnet_fit_mm") is not None else MAGNET_FIT_MM
    )
    rib_t = float(box.get("rib_t_mm") if box.get("rib_t_mm") is not None else RIB_T_MM)
    outer_l = _mm(spec, "box.outer_l_mm")
    outer_w = _mm(spec, "box.outer_w_mm")
    outer_h = _mm(spec, "box.outer_h_mm")
    magnet_d = _mm(spec, "box.magnet_d_mm")
    magnet_h = _mm(spec, "box.magnet_h_mm")
    warnings: list[str] = []
    for label, value in (
        ("wall_mm", wall),
        ("floor_mm", floor),
        ("lid_mm", lid_h),
        ("box.magnet_d_mm", magnet_d),
        ("box.magnet_h_mm", magnet_h),
        ("rib_t_mm", rib_t),
    ):
        if value + 1e-9 < MIN_FEATURE_MM:
            raise ValueError(f"{label}={value} < {MIN_FEATURE_MM}")
    if outer_l <= 2.0 * wall or outer_w <= 2.0 * wall or outer_h <= floor + lid_h:
        raise ValueError("outer L/W/H leaves no cavity after wall, floor, and lid")
    inner_l = outer_l - 2.0 * wall
    inner_w = outer_w - 2.0 * wall
    base_h = outer_h - lid_h
    inner_h = base_h - floor
    cut_d = magnet_d + magnet_fit
    insert_boss = cut_d + 2.0 * MAGNET_WALL_MM
    boss_inset = insert_boss / 2.0 + MAGNET_EDGE_CLEAR_MM
    if magnet_h + MAGNET_CUP_EXTRA_MM + 0.6 > base_h - 0.8:
        warnings.append(
            f"magnet_h_mm={magnet_h} nearly through the {base_h:.1f} mm post"
        )
    need_lip = magnet_h + MAGNET_CUP_EXTRA_MM + MAGNET_LID_FLOOR_MM - lid_h
    if need_lip > lip + 1e-9:
        warnings.append(
            f"lip_mm={lip} raised to {need_lip:.1f} so Ø{magnet_d:.0f}×{magnet_h:.0f} "
            f"cup keeps {MAGNET_LID_FLOOR_MM} mm floor under lid_mm={lid_h}"
        )
        lip = need_lip
    span = max(inner_l, inner_w)
    suggested = wall_for_span(span)
    if wall + 1e-9 < suggested:
        warnings.append(
            f"wall_mm={wall} is below wall_for_span({span:.0f})={suggested}; "
            "operator asked for a thin shell (about three 0.42 mm perimeters)"
        )
    if wall + 1e-9 < 1.2:
        warnings.append(
            f"wall_mm={wall} < 1.2: three perimeters of a 0.4 mm nozzle want ≥ 1.2"
        )
    return BoxLayout(
        wall=wall,
        floor=floor,
        lid_h=lid_h,
        lip=lip,
        lid_fit=lid_fit,
        outer_l=outer_l,
        outer_w=outer_w,
        outer_h=outer_h,
        inner_l=inner_l,
        inner_w=inner_w,
        inner_h=inner_h,
        base_h=base_h,
        magnet_d=magnet_d,
        magnet_h=magnet_h,
        magnet_fit=magnet_fit,
        insert_boss=insert_boss,
        boss_inset=boss_inset,
        rib_t=rib_t,
        warnings=tuple(warnings),
    )


def _lid_lip_outer_xy(lay: BoxLayout) -> tuple[float, float, float, float]:
    sx0 = lay.wall + lay.lid_fit
    sy0 = lay.wall + lay.lid_fit
    sx1 = lay.outer_l - lay.wall - lay.lid_fit
    sy1 = lay.outer_w - lay.wall - lay.lid_fit
    return sx0, sy0, sx1, sy1


def _lid_fit_gap_tools(lay: BoxLayout) -> list[cq.Workplane]:
    """Clear the wall–lip gap so the downward boss does not jam the lid."""
    sx0, sy0, sx1, sy1 = _lid_lip_outer_xy(lay)
    z1 = lay.lip - 0.05
    if z1 <= 0.05:
        return []
    return [
        box_aabb(-2.0, -2.0, -0.5, sx0, lay.outer_w + 2.0, z1),
        box_aabb(sx1, -2.0, -0.5, lay.outer_l + 2.0, lay.outer_w + 2.0, z1),
        box_aabb(-2.0, -2.0, -0.5, lay.outer_l + 2.0, sy0, z1),
        box_aabb(-2.0, sy1, -0.5, lay.outer_l + 2.0, lay.outer_w + 2.0, z1),
    ]


def boss_xy(lay: BoxLayout) -> tuple[tuple[float, float], ...]:
    """Four outer corners. Centre = boss radius + 0.8 mm from each outer face."""
    inset = lay.boss_inset
    return (
        (inset, inset),
        (inset, lay.outer_w - inset),
        (lay.outer_l - inset, inset),
        (lay.outer_l - inset, lay.outer_w - inset),
    )


def _diagonal_bar(
    a: tuple[float, float],
    b: tuple[float, float],
    z0: float,
    z1: float,
    thickness: float,
) -> cq.Workplane:
    """Bar along AB, thickness in plan, height z0..z1. Centred on the segment."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1.0 or z1 <= z0 or thickness <= 0:
        raise ValueError("degenerate lid rib")
    angle = math.degrees(math.atan2(dy, dx))
    return (
        cq.Workplane("XY")
        .box(length, thickness, z1 - z0)
        .rotate((0, 0, 0), (0, 0, 1), angle)
        .translate(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (z0 + z1) / 2.0))
    )


def _cross_ribs(lay: BoxLayout) -> cq.Workplane:
    """Two diagonals on the lid inner face, same height as the lip.

    Ends sit on the corner-boss centres so the bars fuse into the bosses.
    The magnet-cup cut afterwards keeps the wells empty.
    """
    sw, nw, se, ne = boss_xy(lay)
    z1 = lay.lip + PENETRATE_MM
    return fuse(
        _diagonal_bar(sw, ne, 0.0, z1, lay.rib_t),
        _diagonal_bar(nw, se, 0.0, z1, lay.rib_t),
    )


def _lid_on_bed(lid: cq.Workplane, lay: BoxLayout) -> cq.Workplane:
    """Slicer pose: smooth roof on z=0, ribs and magnet cups toward +Z.

    180° about X. Y comes back into 0..outer_w. Corner magnets and the
    diagonal cross are the same after that turn.
    """
    roof_top = lay.lip + lay.lid_h
    spun = lid.rotate((0, 0, 0), (1, 0, 0), 180)
    return spun.translate((0, lay.outer_w, roof_top))


def _lid_blank(lay: BoxLayout) -> cq.Workplane:
    """Closed lid: lip toward the bed, outer roof +Z, no well."""
    roof_z0 = lay.lip
    roof_z1 = lay.lip + lay.lid_h
    roof = box_aabb(0, 0, roof_z0, lay.outer_l, lay.outer_w, roof_z1)
    if lay.lip <= 0.05:
        return roof
    sx0, sy0, sx1, sy1 = _lid_lip_outer_xy(lay)
    lip_t = _lid_lip_t(lay.wall, lay.lid_fit)
    if sx1 - sx0 <= 2.0 * lip_t or sy1 - sy0 <= 2.0 * lip_t:
        return roof
    frame = box_aabb(sx0, sy0, 0, sx1, sy1, lay.lip + PENETRATE_MM)
    hollow = box_aabb(
        sx0 + lip_t,
        sy0 + lip_t,
        -0.4,
        sx1 - lip_t,
        sy1 - lip_t,
        lay.lip + 0.4,
    )
    return fuse(roof, cut_through(frame, hollow))


def _keepout_world(spec: dict[str, Any], lay: BoxLayout) -> cq.Workplane:
    """keepout.box is cavity CS: origin at the inner −X/−Y/floor corner."""
    ko = walk_path(spec, "keepout.box")
    kmin = [float(v) for v in ko["min"]]
    kmax = [float(v) for v in ko["max"]]
    return box_aabb(
        lay.wall + kmin[0],
        lay.wall + kmin[1],
        lay.floor + kmin[2],
        lay.wall + kmax[0],
        lay.wall + kmax[1],
        lay.floor + kmax[2],
    )


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    lay = layout_from_spec(spec)
    warnings = list(lay.warnings)
    solid = box_aabb(0, 0, 0, lay.outer_l, lay.outer_w, lay.base_h)
    cavity = box_aabb(
        lay.wall,
        lay.wall,
        lay.floor,
        lay.outer_l - lay.wall,
        lay.outer_w - lay.wall,
        lay.base_h + 0.3,
    )
    base = cut_through(solid, cavity)
    xy = boss_xy(lay)
    bosses = [
        _z_cyl(x, y, lay.floor - PENETRATE_MM, lay.post_top_z, lay.insert_boss)
        for x, y in xy
    ]
    base = fuse(base, combine_disjoint(*bosses))
    magnet_tools = [
        _z_cyl(
            x,
            y,
            lay.post_top_z - lay.magnet_cup_h,
            lay.post_top_z + 0.3,
            lay.magnet_cut_d,
        )
        for x, y in xy
    ]
    base = cut_all(base, magnet_tools)
    if BED_CHAMFER_MM > 0.05:
        try:
            base = cq.Workplane(base.val()).faces("<Z").edges().chamfer(BED_CHAMFER_MM)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"bed chamfer skipped: {exc}")

    lid_print = _lid_blank(lay)
    inner_h = lay.lid_magnet_inner_h
    inner_pads = [
        _z_cyl(x, y, 0.0, inner_h + PENETRATE_MM, lay.insert_boss) for x, y in xy
    ]
    fused_inner = inner_pads[0]
    for extra in inner_pads[1:]:
        fused_inner = fuse(fused_inner, extra)
    lid_print = fuse(lid_print, fused_inner)
    lid_print = fuse(lid_print, _cross_ribs(lay))
    gap_tools = _lid_fit_gap_tools(lay)
    if gap_tools:
        lid_print = cut_all(lid_print, gap_tools)
    lid_print = cut_all(
        lid_print,
        [_z_cyl(x, y, -0.3, lay.magnet_cup_h, lay.magnet_cut_d) for x, y in xy],
    )
    lid_assembled = lid_print.translate((0, 0, lay.base_h - lay.lip))
    assembled = fuse(base, lid_assembled)
    lid_bed = _lid_on_bed(lid_print, lay)
    printable = combine_disjoint(
        base, lid_bed.translate((lay.outer_l + PRINT_POSE_GAP_MM, 0, 0))
    )
    keepout = _keepout_world(spec, lay)
    report = {
        "template_id": TEMPLATE_ID,
        "template_sha256": _template_sha256(),
        "pattern": "magnet-box",
        "outer_mm": [lay.outer_l, lay.outer_w, lay.outer_h],
        "inner_mm": [lay.inner_l, lay.inner_w, lay.inner_h],
        "boss_xy_mm": [list(pt) for pt in xy],
        "wall_mm": lay.wall,
        "floor_mm": lay.floor,
        "lid_mm": lay.lid_h,
        "lip_mm": lay.lip,
        "rib_t_mm": lay.rib_t,
        "rib_h_mm": lay.lip,
        "insert_boss_d_mm": lay.insert_boss,
        "boss_inset_mm": lay.boss_inset,
        "magnet_d_mm": lay.magnet_d,
        "magnet_h_mm": lay.magnet_h,
        "magnet_cut_d_mm": lay.magnet_cut_d,
        "lid_magnet": "inner-bed-cup",
        "closure": "magnets",
        "post_top_z_mm": lay.post_top_z,
        "lid_boss_h_mm": lay.lid_magnet_inner_h,
        "cavity_origin_mm": [lay.wall, lay.wall, lay.floor],
        "lid_print": "roof-on-bed",
    }
    warnings.append(
        "disc magnets "
        f"Ø{lay.magnet_d:.1f}×{lay.magnet_h:.1f} in four corner posts and in "
        "lid bosses that hang down (cups open toward each other; outer roof flat); "
        "posts run from the floor and fuse into both corner walls; "
        f"lid inner face has an X of ribs {lay.rib_t:.2f}×{lay.lip:.1f} mm "
        "(height matches the lip)"
    )
    warnings.append(
        "lid prints beside the base with the smooth roof on z=0 and the ribs "
        "and magnet cups facing up (180° about X). A 250 mm plan still does "
        "not fit two halves on a 256 mm bed — print one part at a time. "
        "Do not flip the lid again in the slicer"
    )
    magnet_node = (spec.get("box") or {}).get("magnet_d_mm") or {}
    if not bool(magnet_node.get("confirmed") if isinstance(magnet_node, dict) else False):
        warnings.append(
            "magnet_d_mm is not confirmed — Ø5×2 is the operator's disc; "
            "boss OD follows magnet_d + fit + 2×1.6 mm"
        )
    return EnclosureBuild(
        base=base,
        lid=lid_print,
        assembled=assembled,
        printable=printable,
        keepout=keepout,
        keepout_volume=intersect_volume(assembled, keepout),
        outer=(lay.outer_l, lay.outer_w, lay.outer_h),
        usb_cut_wh=(0.0, 0.0),
        cavity_lw=(lay.inner_l, lay.inner_w),
        warnings=warnings,
        report=report,
    )
