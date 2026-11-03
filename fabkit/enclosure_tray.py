"""Tray for several devices: screw lid, open well over uncovered pockets.

Pattern `device-tray`. Not a PCB snap, not a one-device shell. Coordinate
system: origin at the outer box corner; inner cavity after wall/floor;
+X right on the A4 sketch (socket), +Y toward the GSM row, +Z up.
Print: base floor on the bed (cavity +Z); lid as closed — lip toward the
bed, outer roof +Z, same XY as the box. Lift the lid, do not flip it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cadquery as cq

from fabkit.enclosure_box import EnclosureBuild
from fabkit.enclosure_shell import (
    BED_CHAMFER_MM,
    INSERT_BOSS_D_MM,
    INSERT_DEPTH_MM,
    INSERT_HOLE_D_MM,
    LID_MM,
    LIP_MM,
    SCREW_CLEAR_D_MM,
    _z_cyl,
    teardrop_along_x,
)
from fabkit.fit import (
    LID_FIT_MM,
    MIN_FEATURE_MM,
    OPENING_CLEARANCE_MM,
    PRINT_POSE_GAP_MM,
    wall_for_span,
)
from fabkit.kernel import box_aabb, intersect_volume
from fabkit.solid import PENETRATE_MM, combine_disjoint, cut_all, cut_through, fuse
from fabkit.validate import walk_path

TEMPLATE_ID = "enclosure_tray"
FLOOR_MM = 2.0
GAP_XY_MM = 1.5
BOSS_INSET_MM = 6.5
PARTITION_T_MM = 2.0
MOUNT_PAD_D_MM = 10.0
MOUNT_PAD_H_MM = 2.0
MOUSEHOLE_W_MM = 6.0
MOUSEHOLE_CLEAR_H_MM = 7.0
GROOVE_W_MM = 5.0
FLOOR_RESERVE_MM = 0.8
REST_STRIP_W_MM = 3.0
REST_STRIP_COUNT = 3
REST_STRIP_INSET_MM = 4.0
MAGNET_WALL_MM = 1.6
MAGNET_FIT_MM = 0.25
MAGNET_CUP_EXTRA_MM = 0.2
MAGNET_LID_FLOOR_MM = 0.8
MAGNET_EDGE_CLEAR_MM = 0.8


def _lid_lip_t(wall: float, lid_fit: float) -> float:
    """Radial thickness of the print-bed lip. Keep ≥ MIN_FEATURE on a 1 mm wall."""
    return min(max(wall - lid_fit - 0.15, MIN_FEATURE_MM), 1.5)


def _lid_lip_outer_xy(lay: TrayLayout) -> tuple[float, float, float, float]:
    """Outer XY of the inserting lip. Roof stays 0…outer; this is what drops in."""
    sx0 = lay.wall + lay.lid_fit
    sy0 = lay.wall + lay.lid_fit
    sx1 = lay.outer_l - lay.wall - lay.lid_fit
    sy1 = lay.outer_w - lay.wall - lay.lid_fit
    return sx0, sy0, sx1, sy1


def _lid_fit_gap_tools(lay: TrayLayout) -> list[cq.Workplane]:
    """Clear the wall–lip gap below the roof so the lid seats without filing."""
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


def _mm(spec: dict[str, Any], path: str) -> float:
    return float(walk_path(spec, path)["value"])


def _optional_measured(block: dict[str, Any], key: str) -> float | None:
    node = block.get(key)
    if not node:
        return None
    if isinstance(node, dict):
        if node.get("value") is None:
            return None
        return float(node["value"])
    return float(node)


def _template_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class PocketMount:
    """Device screw in pocket CS (origin pocket −X/−Y). Not a lid post."""

    x: float
    y: float
    d: float


@dataclass(frozen=True)
class Pocket:
    name: str
    x: float
    y: float
    length: float
    width: float
    height: float
    covered: bool
    mounts: tuple[PocketMount, ...] = ()
    rest_strips: bool = False


@dataclass(frozen=True)
class TrayLayout:
    wall: float
    floor: float
    lid_h: float
    lip: float
    lid_fit: float
    gap_xy: float
    inner_l: float
    inner_w: float
    inner_h: float
    outer_l: float
    outer_w: float
    base_h: float
    insert_hole: float
    insert_boss: float
    insert_depth: float
    screw_clear: float
    boss_inset: float
    partition_t: float
    wire_channels: bool
    magnet_d: float | None
    magnet_h: float
    magnet_fit: float
    pockets: tuple[Pocket, ...]
    warnings: tuple[str, ...]

    @property
    def socket(self) -> Pocket:
        for pocket in self.pockets:
            if pocket.name == "socket":
                return pocket
        raise KeyError("socket pocket missing")

    @property
    def uses_magnets(self) -> bool:
        return self.magnet_d is not None and self.magnet_d > 0.05

    @property
    def magnet_cut_d(self) -> float:
        if self.magnet_d is None:
            return 0.0
        return self.magnet_d + self.magnet_fit

    @property
    def magnet_cup_h(self) -> float:
        return self.magnet_h + MAGNET_CUP_EXTRA_MM

    @property
    def lid_magnet_pad_h(self) -> float:
        """Outer roof bump. Always 0: cups open on the lip/bed face."""
        return 0.0

    @property
    def lid_magnet_inner_h(self) -> float:
        """Inner cup walls on the print-bed face (lip side). Outer roof stays flat."""
        if not self.uses_magnets:
            return 0.0
        needed = self.magnet_cup_h + MAGNET_LID_FLOOR_MM - self.lid_h
        return max(self.lip, needed)

    @property
    def post_top_z(self) -> float:
        """Base post top. Magnets: stop at the lid inner cup face, not the rim."""
        if self.uses_magnets:
            return self.base_h - self.lid_magnet_inner_h
        return self.base_h


def _pocket_mounts(block: dict[str, Any]) -> tuple[PocketMount, ...]:
    items = block.get("mounts") or []
    out: list[PocketMount] = []
    for item in items:
        x_node = item.get("x_mm") or {}
        y_node = item.get("y_mm") or {}
        out.append(
            PocketMount(
                x=float(x_node["value"]),
                y=float(y_node["value"]),
                d=float(item["d_mm"] if item.get("d_mm") is not None else SCREW_CLEAR_D_MM),
            )
        )
    return tuple(out)


def _pocket(spec: dict[str, Any], name: str) -> Pocket:
    block = (spec.get("pockets") or {}).get(name) or {}
    covered = block.get("covered")
    if covered is None:
        covered = name != "socket"
    return Pocket(
        name=name,
        x=_mm(spec, f"pockets.{name}.x_mm"),
        y=_mm(spec, f"pockets.{name}.y_mm"),
        length=_mm(spec, f"pockets.{name}.length_mm"),
        width=_mm(spec, f"pockets.{name}.width_mm"),
        height=_mm(spec, f"pockets.{name}.height_mm"),
        covered=bool(covered),
        mounts=_pocket_mounts(block),
        rest_strips=bool(block.get("rest_strips")),
    )


def layout_from_spec(spec: dict[str, Any]) -> TrayLayout:
    wall = float(spec.get("wall_mm") or 2.0)
    tray = spec.get("tray") or {}
    gap_xy = float(tray.get("gap_xy_mm") if tray.get("gap_xy_mm") is not None else GAP_XY_MM)
    wire_channels = bool(tray.get("wire_channels"))
    floor = float(tray.get("floor_mm") if tray.get("floor_mm") is not None else FLOOR_MM)
    lid_h = float(tray.get("lid_mm") if tray.get("lid_mm") is not None else LID_MM)
    lip = float(tray.get("lip_mm") if tray.get("lip_mm") is not None else LIP_MM)
    lid_fit = float(tray.get("lid_fit_mm") if tray.get("lid_fit_mm") is not None else LID_FIT_MM)
    partition_t = float(
        tray.get("partition_t_mm") if tray.get("partition_t_mm") is not None else PARTITION_T_MM
    )
    insert_hole = float(
        tray.get("insert_hole_d_mm") if tray.get("insert_hole_d_mm") is not None else INSERT_HOLE_D_MM
    )
    insert_boss = float(
        tray.get("insert_boss_d_mm") if tray.get("insert_boss_d_mm") is not None else INSERT_BOSS_D_MM
    )
    insert_depth = float(
        tray.get("insert_depth_mm") if tray.get("insert_depth_mm") is not None else INSERT_DEPTH_MM
    )
    screw_clear = float(
        tray.get("screw_clear_d_mm") if tray.get("screw_clear_d_mm") is not None else SCREW_CLEAR_D_MM
    )
    boss_inset = float(
        tray.get("boss_inset_mm") if tray.get("boss_inset_mm") is not None else BOSS_INSET_MM
    )
    magnet_d = _optional_measured(tray, "magnet_d_mm")
    magnet_h = _optional_measured(tray, "magnet_h_mm")
    if magnet_h is None:
        magnet_h = 2.0
    magnet_fit = float(
        tray.get("magnet_fit_mm") if tray.get("magnet_fit_mm") is not None else MAGNET_FIT_MM
    )
    inner_l = _mm(spec, "tray.inner_l_mm")
    inner_w = _mm(spec, "tray.inner_w_mm")
    inner_h = _mm(spec, "tray.inner_h_mm")
    pockets = tuple(_pocket(spec, name) for name in ("gsm", "psu", "socket"))
    outer_l = inner_l + 2.0 * wall
    outer_w = inner_w + 2.0 * wall
    base_h = floor + inner_h
    warnings: list[str] = []
    for label, value in (("wall_mm", wall), ("floor_mm", floor), ("lid_mm", lid_h)):
        if value + 1e-9 < MIN_FEATURE_MM:
            raise ValueError(f"{label}={value} < {MIN_FEATURE_MM}")
    if inner_l <= 0 or inner_w <= 0 or inner_h <= 0:
        raise ValueError("tray inner L/W/H must be positive")
    for pocket in pockets:
        if pocket.length <= 0 or pocket.width <= 0 or pocket.height <= 0:
            raise ValueError(f"pocket {pocket.name} has a non-positive size")
        if pocket.x < -0.05 or pocket.y < -0.05:
            raise ValueError(f"pocket {pocket.name} origin is outside the cavity")
        if pocket.x + pocket.length - inner_l > 0.25 or pocket.y + pocket.width - inner_w > 0.25:
            warnings.append(
                f"pocket {pocket.name} {pocket.length:.1f}×{pocket.width:.1f} at "
                f"({pocket.x:.1f},{pocket.y:.1f}) overshoots tray inner {inner_l}×{inner_w}"
            )
        if pocket.height - inner_h > 0.25:
            warnings.append(
                f"pocket {pocket.name} height {pocket.height} mm exceeds "
                f"tray.inner_h_mm={inner_h}"
            )
    uncovered = [pocket.name for pocket in pockets if not pocket.covered]
    if "socket" not in uncovered:
        warnings.append("socket pocket is covered; operator asked for an open well")
    if magnet_d is not None and magnet_d > 0.05:
        cut_d = magnet_d + magnet_fit
        needed_boss = cut_d + 2.0 * MAGNET_WALL_MM
        if insert_boss + 1e-9 < needed_boss:
            insert_boss = needed_boss
        # Posts sit against the outer walls. Inserting pads are clipped to
        # the lip outer (see _lid_fit_gap_tools) so the lid still drops in.
        needed_inset = insert_boss / 2.0 + MAGNET_EDGE_CLEAR_MM
        if boss_inset + 1e-9 < needed_inset:
            boss_inset = needed_inset
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
    elif insert_depth + 0.4 > base_h - 0.8:
        warnings.append(
            f"insert_depth_mm={insert_depth} nearly through the {base_h:.1f} mm base"
        )
    span = max(inner_l, inner_w)
    suggested = wall_for_span(span)
    if wall + 1e-9 < suggested:
        warnings.append(
            f"wall_mm={wall} is below wall_for_span({span:.0f})={suggested}; "
            "open tray: lid-post fasteners live in the bosses, not the floor plate"
        )
    return TrayLayout(
        wall=wall,
        floor=floor,
        lid_h=lid_h,
        lip=lip,
        lid_fit=lid_fit,
        gap_xy=gap_xy,
        inner_l=inner_l,
        inner_w=inner_w,
        inner_h=inner_h,
        outer_l=outer_l,
        outer_w=outer_w,
        base_h=base_h,
        insert_hole=insert_hole,
        insert_boss=insert_boss,
        insert_depth=insert_depth,
        screw_clear=screw_clear,
        boss_inset=boss_inset,
        partition_t=partition_t,
        wire_channels=wire_channels,
        magnet_d=magnet_d,
        magnet_h=magnet_h,
        magnet_fit=magnet_fit,
        pockets=pockets,
        warnings=tuple(warnings),
    )


def _world_pocket(lay: TrayLayout, pocket: Pocket) -> tuple[float, float, float, float]:
    x0 = lay.wall + pocket.x
    y0 = lay.wall + pocket.y
    return x0, y0, x0 + pocket.length, y0 + pocket.width


def _lid_cut_xy(lay: TrayLayout) -> tuple[float, float, float, float]:
    """Open well over the uncovered socket, extended to +X and −Y rims.

    A closed hole would leave a skinny lid strip on those two edges (socket
    sits in the corner). The remaining plate is an L over GSM + PSU.
    """
    socket = lay.socket
    x0, y0, x1, y1 = _world_pocket(lay, socket)
    x0 = max(lay.wall * 0.5, x0 - lay.gap_xy)
    y1 = min(lay.outer_w - lay.wall * 0.5, y1 + lay.gap_xy)
    return x0, -0.4, lay.outer_l + 0.4, y1


def boss_xy(lay: TrayLayout) -> tuple[tuple[float, float], ...]:
    """Lid posts: three outer L corners plus one at the socket-well inner corner.

    Same XY on the printed lid and in the base. Magnet cups (or M3 inserts)
    live in these posts. The inner post sits just −X of the well, still
    below the GSM pocket.
    """
    inset = lay.boss_inset
    r = lay.insert_boss / 2.0
    gsm = _named_pocket(lay, "gsm")
    _gx0, gy0, _gx1, _gy1 = _world_pocket(lay, gsm)
    cut_x0, _cut_y0, _cut_x1, cut_y1 = _lid_cut_xy(lay)
    socket_x0, _sy0, _sx1, socket_y1 = _world_pocket(lay, lay.socket)
    inner = (
        min(cut_x0, socket_x0) - r - 0.4,
        min(cut_y1, socket_y1, gy0 - r - 1.0),
    )
    pts = (
        (inset, inset),
        (inset, lay.outer_w - inset),
        (lay.outer_l - inset, lay.outer_w - inset),
        inner,
    )
    return tuple(pt for pt in pts if _in_remaining_lid(lay, pt[0], pt[1]))


def _in_remaining_lid(lay: TrayLayout, x: float, y: float) -> bool:
    x0, y0, x1, y1 = _lid_cut_xy(lay)
    return not (x0 <= x <= x1 and y0 <= y <= y1)


def _lid_blank(lay: TrayLayout) -> cq.Workplane:
    """Closed orientation: lip toward the bed, outer roof +Z, same XY as the box.

    The base prints cavity-up. The lid prints as the cover sitting beside it
    (top up). Operator lifts it onto the box — no flip, holes stay over the posts.
    """
    roof_z0 = lay.lip
    roof_z1 = lay.lip + lay.lid_h
    roof = box_aabb(0, 0, roof_z0, lay.outer_l, lay.outer_w, roof_z1)
    lid = roof
    if lay.lip > 0.05:
        sx0, sy0, sx1, sy1 = _lid_lip_outer_xy(lay)
        lip_t = _lid_lip_t(lay.wall, lay.lid_fit)
        if sx1 - sx0 > 2.0 * lip_t and sy1 - sy0 > 2.0 * lip_t:
            frame = box_aabb(sx0, sy0, 0, sx1, sy1, lay.lip + PENETRATE_MM)
            hollow = box_aabb(
                sx0 + lip_t,
                sy0 + lip_t,
                -0.4,
                sx1 - lip_t,
                sy1 - lip_t,
                lay.lip + 0.4,
            )
            lid = fuse(roof, cut_through(frame, hollow))
    x0, y0, x1, y1 = _lid_cut_xy(lay)
    well = box_aabb(x0, y0, -0.4, x1, y1, roof_z1 + 0.4)
    return cut_through(lid, well)


def _assembled_lid(lid_print: cq.Workplane, lay: TrayLayout) -> cq.Workplane:
    """Print already matches closed XY and Z sense. Sit the roof on the box rim."""
    return lid_print.translate((0, 0, lay.base_h - lay.lip))


def _named_pocket(lay: TrayLayout, name: str) -> Pocket:
    for pocket in lay.pockets:
        if pocket.name == name:
            return pocket
    raise KeyError(f"{name} pocket missing")


def _partition(lay: TrayLayout) -> cq.Workplane | None:
    """Low wall in the *gaps* between the socket well and covered pockets.

    Thickness is min(spec, gap − 0.2). A 2.4 mm rib into a 1.6 mm GSM–socket
    gap would hit keep-out (A4 cluster). Skip a segment below MIN_FEATURE_MM.
    """
    socket = lay.socket
    x0, y0, x1, y1 = _world_pocket(lay, socket)
    t = lay.partition_t
    if t < MIN_FEATURE_MM:
        return None
    z0 = lay.floor - PENETRATE_MM
    z1 = lay.floor + min(8.0, lay.inner_h * 0.35)
    psu = _named_pocket(lay, "psu")
    gsm = _named_pocket(lay, "gsm")
    _px0, _py0, px1, _py1 = _world_pocket(lay, psu)
    _gx0, gy0, _gx1, _gy1 = _world_pocket(lay, gsm)
    parts: list[cq.Workplane] = []
    gap_x = x0 - px1
    vt = min(t, max(0.0, gap_x - 0.2))
    if vt + 1e-9 >= MIN_FEATURE_MM:
        parts.append(
            box_aabb(
                x0 - vt,
                max(lay.wall, y0),
                z0,
                x0,
                min(lay.wall + lay.inner_w, y1),
                z1,
            )
        )
    gap_y = gy0 - y1
    ht = min(t, max(0.0, gap_y - 0.2))
    if ht + 1e-9 >= MIN_FEATURE_MM:
        parts.append(
            box_aabb(
                max(lay.wall, x0 - max(vt, t)),
                y1,
                z0,
                min(lay.wall + lay.inner_l, x1),
                y1 + ht,
                z1,
            )
        )
    if not parts:
        return None
    out = parts[0]
    for extra in parts[1:]:
        out = fuse(out, extra)
    return out


def _mount_world(lay: TrayLayout, pocket: Pocket, mount: PocketMount) -> tuple[float, float]:
    return lay.wall + pocket.x + mount.x, lay.wall + pocket.y + mount.y


def _mount_xy(lay: TrayLayout) -> list[list[float]]:
    pts: list[list[float]] = []
    for pocket in lay.pockets:
        for mount in pocket.mounts:
            x, y = _mount_world(lay, pocket, mount)
            pts.append([x, y, mount.d])
    return pts


def _mount_pads(lay: TrayLayout) -> list[cq.Workplane]:
    pads: list[cq.Workplane] = []
    z1 = lay.floor + MOUNT_PAD_H_MM
    for pocket in lay.pockets:
        for mount in pocket.mounts:
            x, y = _mount_world(lay, pocket, mount)
            pads.append(
                _z_cyl(x, y, lay.floor - PENETRATE_MM, z1, MOUNT_PAD_D_MM)
            )
    return pads


def _mount_holes(lay: TrayLayout) -> list[cq.Workplane]:
    """Bolt clearance through pad and floor. Solid pad, not a countersink well.

    The 7 mm ISO countersink looked like an empty cavity in Studio; operator
    does not want it. Cut after the bed chamfer so the hole stays through.
    """
    holes: list[cq.Workplane] = []
    z1 = lay.floor + MOUNT_PAD_H_MM + 0.4
    for pocket in lay.pockets:
        for mount in pocket.mounts:
            x, y = _mount_world(lay, pocket, mount)
            holes.append(_z_cyl(x, y, -0.3, z1, mount.d))
    return holes


def _rest_strip_axis(pocket: Pocket) -> str:
    """Strips run parallel to the mount pair so the part cannot rock off that line."""
    if len(pocket.mounts) >= 2:
        xs = [m.x for m in pocket.mounts]
        ys = [m.y for m in pocket.mounts]
        if max(xs) - min(xs) + 1e-9 >= max(ys) - min(ys):
            return "x"
        return "y"
    return "x" if pocket.length + 1e-9 >= pocket.width else "y"


def _rest_strip_aabbs(lay: TrayLayout) -> list[list[float]]:
    """World XY boxes [x0, y0, x1, y1] for anti-rock strips. Same height as mount pads."""
    boxes: list[list[float]] = []
    inset = REST_STRIP_INSET_MM
    half = REST_STRIP_W_MM / 2.0
    n = REST_STRIP_COUNT
    for pocket in lay.pockets:
        if not pocket.rest_strips:
            continue
        x0, y0, x1, y1 = _world_pocket(lay, pocket)
        axis = _rest_strip_axis(pocket)
        if axis == "x":
            span0, span1 = y0 + inset + half, y1 - inset - half
            run0, run1 = x0 + inset, x1 - inset
            if span1 - span0 < REST_STRIP_W_MM or run1 - run0 < 8.0:
                continue
            for i in range(n):
                t = i / (n - 1) if n > 1 else 0.5
                cy = span0 + t * (span1 - span0)
                boxes.append([run0, cy - half, run1, cy + half])
        else:
            span0, span1 = x0 + inset + half, x1 - inset - half
            run0, run1 = y0 + inset, y1 - inset
            if span1 - span0 < REST_STRIP_W_MM or run1 - run0 < 8.0:
                continue
            for i in range(n):
                t = i / (n - 1) if n > 1 else 0.5
                cx = span0 + t * (span1 - span0)
                boxes.append([cx - half, run0, cx + half, run1])
    return boxes


def _rest_strips(lay: TrayLayout) -> list[cq.Workplane]:
    z1 = lay.floor + MOUNT_PAD_H_MM
    out: list[cq.Workplane] = []
    for x0, y0, x1, y1 in _rest_strip_aabbs(lay):
        out.append(box_aabb(x0, y0, lay.floor - PENETRATE_MM, x1, y1, z1))
    return out


def _mousehole_centers(lay: TrayLayout) -> list[tuple[float, float]]:
    """One −Y wall exit: the PSU-side hole closer to the socket."""
    psu = _named_pocket(lay, "psu")
    px0, _py0, px1, _py1 = _world_pocket(lay, psu)
    cx = px0 + 0.65 * (px1 - px0)
    return [(cx, 0.0)]


def _mousehole_cuts(lay: TrayLayout) -> tuple[list[cq.Workplane], list[list[float]]]:
    """U-slot in the −Y wall, open to the bed. Apply AFTER the bed chamfer.

    Chamfering every `<Z` edge of a notched floor puts OCCT faces back in
    the opening (Studio: two stacked rectangles, hole not through). Floor
    grooves stay inside the cavity and meet this slot from y ≥ wall.
    """
    tools: list[cq.Workplane] = []
    exits: list[list[float]] = []
    hole_h = lay.floor + MOUSEHOLE_CLEAR_H_MM
    half = MOUSEHOLE_W_MM / 2.0
    overshoot = max(1.0, BED_CHAMFER_MM + 0.4)
    for cx, _cy in _mousehole_centers(lay):
        tools.append(
            box_aabb(cx - half, -overshoot, -1.0, cx + half, lay.wall + overshoot, hole_h)
        )
        exits.append([cx, 0.0, MOUSEHOLE_W_MM])
    return tools, exits


def _wire_cuts(lay: TrayLayout) -> list[cq.Workplane]:
    """Floor grooves from the A4 power/switching sketch. Not the −Y wall.

    Grooves must not pierce the outer shell — that kiss left cutter faces
    in the mousehole. The wall exit is `_mousehole_cuts` after chamfer.
    """
    psu = _named_pocket(lay, "psu")
    gsm = _named_pocket(lay, "gsm")
    socket = lay.socket
    px0, py0, px1, py1 = _world_pocket(lay, psu)
    gx0, gy0, _gx1, _gy1 = _world_pocket(lay, gsm)
    sx0, sy0, _sx1, _sy1 = _world_pocket(lay, socket)
    tools: list[cq.Workplane] = []
    groove_d = min(1.0, max(0.0, lay.floor - FLOOR_RESERVE_MM))
    if groove_d + 1e-9 >= MIN_FEATURE_MM:
        z0 = lay.floor - groove_d
        z1 = lay.floor + 0.3
        gw = GROOVE_W_MM
        y_in = lay.wall - PENETRATE_MM
        tools.append(box_aabb(px0 + 2.0, y_in, z0, px1 - 2.0, py0 + 1.0, z1))
        alley = sx0 - px1
        if alley >= 3.0:
            y_a = sy0 + 10.0
            y_b = sy0 + 30.0
            tools.append(box_aabb(px1, y_a, z0, sx0, y_a + gw, z1))
            tools.append(box_aabb(px1, y_b, z0, sx0, y_b + gw, z1))
            tunnel_h = min(4.0, lay.inner_h * 0.2)
            tools.append(
                box_aabb(
                    px1 - 0.2,
                    y_a,
                    lay.floor - 0.2,
                    sx0 + 0.2,
                    y_a + gw,
                    lay.floor + tunnel_h,
                )
            )
            tools.append(
                box_aabb(
                    px1 - 0.2,
                    y_b,
                    lay.floor - 0.2,
                    sx0 + 0.2,
                    y_b + gw,
                    lay.floor + tunnel_h,
                )
            )
        x_run = max(lay.wall + 0.4, gx0)
        tools.append(box_aabb(x_run, py1, z0, x_run + min(gw, 3.2), gy0, z1))
        tools.append(
            box_aabb(
                y_in,
                lay.wall,
                z0,
                x_run + min(gw, 3.2),
                lay.wall + min(gw, 3.2),
                z1,
            )
        )
    return tools


def _sma_cut(spec: dict[str, Any], lay: TrayLayout) -> tuple[cq.Workplane | None, list[float] | None]:
    """SMA whip unscrews: small hole in the +X wall at module mid-height.

    Datasheet body 31.5 mm; A4 layout puts the antenna at GSM +X. Not the
    Ø20 lid well of device-shell.
    """
    block = ((spec.get("pockets") or {}).get("gsm") or {}).get("sma") or {}
    if not block:
        return None, None
    gsm = _named_pocket(lay, "gsm")
    y = float(block["y_mm"]["value"])
    z = float(block["z_mm"]["value"])
    d = float(block["d_mm"] if block.get("d_mm") is not None else 8.0)
    cut_d = d + 2.0 * OPENING_CLEARANCE_MM
    cy = lay.wall + gsm.y + y
    cz = lay.floor + z
    x0 = lay.outer_l - lay.wall - 0.2
    x1 = lay.outer_l + 0.4
    return teardrop_along_x(x0, x1, cy, cz, cut_d), [cy, cz, cut_d]


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
    partition = _partition(lay)
    if partition is not None:
        base = fuse(base, partition)
    wire_exits: list[list[float]] = []
    mouse_tools: list[cq.Workplane] = []
    if lay.wire_channels:
        wire_tools = _wire_cuts(lay)
        if wire_tools:
            base = cut_all(base, wire_tools)
        mouse_tools, wire_exits = _mousehole_cuts(lay)
    pads = _mount_pads(lay)
    pads.extend(_rest_strips(lay))
    if pads:
        fused_pads = pads[0]
        for extra in pads[1:]:
            fused_pads = fuse(fused_pads, extra)
        base = fuse(base, fused_pads)

    xy = boss_xy(lay)
    if len(xy) < 4:
        warnings.append(
            f"only {len(xy)} lid posts sit on the remaining L lid"
        )
    bosses = [
        _z_cyl(x, y, lay.floor - PENETRATE_MM, lay.post_top_z, lay.insert_boss)
        for x, y in xy
    ]
    if bosses:
        base = fuse(base, combine_disjoint(*bosses))
    if lay.uses_magnets:
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
        if magnet_tools:
            base = cut_all(base, magnet_tools)
    else:
        insert_tools = [
            _z_cyl(x, y, lay.base_h - lay.insert_depth, lay.base_h + 0.3, lay.insert_hole)
            for x, y in xy
        ]
        if insert_tools:
            base = cut_all(base, insert_tools)
    sma_tool, sma_yz = _sma_cut(spec, lay)
    if sma_tool is not None:
        base = cut_through(base, sma_tool)
    if BED_CHAMFER_MM > 0.05:
        try:
            base = cq.Workplane(base.val()).faces("<Z").edges().chamfer(BED_CHAMFER_MM)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"bed chamfer skipped: {exc}")
    mount_holes = _mount_holes(lay)
    if mount_holes:
        base = cut_all(base, mount_holes)
    if mouse_tools:
        base = cut_all(base, mouse_tools)

    lid_print = _lid_blank(lay)
    lid_h_print = lay.lip + lay.lid_h
    if lay.uses_magnets:
        inner_h = lay.lid_magnet_inner_h
        inner_pads = [
            _z_cyl(x, y, 0.0, inner_h + PENETRATE_MM, lay.insert_boss)
            for x, y in xy
        ]
        if inner_pads:
            fused_inner = inner_pads[0]
            for extra in inner_pads[1:]:
                fused_inner = fuse(fused_inner, extra)
            lid_print = fuse(lid_print, fused_inner)
            gap_tools = _lid_fit_gap_tools(lay)
            if gap_tools:
                lid_print = cut_all(lid_print, gap_tools)
            cut_x0, cut_y0, cut_x1, cut_y1 = _lid_cut_xy(lay)
            well = box_aabb(cut_x0, cut_y0, -0.4, cut_x1, cut_y1, lid_h_print + 0.4)
            lid_print = cut_through(lid_print, well)
        lid_tools = [
            _z_cyl(x, y, -0.3, lay.magnet_cup_h, lay.magnet_cut_d)
            for x, y in xy
        ]
        if lid_tools:
            lid_print = cut_all(lid_print, lid_tools)
    else:
        lip_clear = []
        if lay.lip > 0.05:
            lip_clear = [
                _z_cyl(x, y, -0.3, lay.lip + 0.05, lay.insert_boss + 0.8)
                for x, y in xy
            ]
        screw_tools = [
            _z_cyl(x, y, -0.3, lid_h_print + 0.3, lay.screw_clear)
            for x, y in xy
        ]
        if lip_clear or screw_tools:
            lid_print = cut_all(lid_print, lip_clear + screw_tools)
    lid_assembled = _assembled_lid(lid_print, lay)

    assembled = fuse(base, lid_assembled)
    printable = combine_disjoint(
        base, lid_print.translate((lay.outer_l + PRINT_POSE_GAP_MM, 0, 0))
    )

    pocket_boxes = []
    for pocket in lay.pockets:
        x0, y0, x1, y1 = _world_pocket(lay, pocket)
        pocket_boxes.append(
            box_aabb(x0, y0, lay.floor, x1, y1, lay.floor + pocket.height)
        )
    keepout = pocket_boxes[0]
    for extra in pocket_boxes[1:]:
        keepout = combine_disjoint(keepout, extra)
    cut_x0, cut_y0, cut_x1, cut_y1 = _lid_cut_xy(lay)
    lid_stack = lay.lid_h + lay.lid_magnet_pad_h
    closure = "magnets" if lay.uses_magnets else "m3-heat-set"
    report = {
        "template_id": TEMPLATE_ID,
        "template_sha256": _template_sha256(),
        "pattern": "device-tray",
        "outer_mm": [lay.outer_l, lay.outer_w, lay.base_h + lid_stack],
        "inner_mm": [lay.inner_l, lay.inner_w, lay.inner_h],
        "lid_cut_xy_mm": [cut_x0, cut_y0, cut_x1, cut_y1],
        "boss_xy_mm": [list(pt) for pt in xy],
        "mount_xy_mm": _mount_xy(lay),
        "rest_strip_aabb_mm": _rest_strip_aabbs(lay),
        "wire_exit_xy_mm": wire_exits,
        "sma_yz_mm": sma_yz,
        "wall_mm": lay.wall,
        "floor_mm": lay.floor,
        "insert_hole_d_mm": lay.insert_hole,
        "insert_boss_d_mm": lay.insert_boss,
        "magnet_d_mm": lay.magnet_d,
        "magnet_h_mm": lay.magnet_h if lay.uses_magnets else None,
        "lid_magnet": "inner-bed-cup" if lay.uses_magnets else None,
        "closure": closure,
        "uncovered_pockets": [pocket.name for pocket in lay.pockets if not pocket.covered],
        "cavity_origin_mm": [lay.wall, lay.wall, lay.floor],
        "lid_print": "closed-outer-up",
    }
    latch_note = (
        f"disc magnets Ø{lay.magnet_d:.1f}×{lay.magnet_h:.1f} in lid posts "
        "(cups open on the lip/bed face; outer roof is flat); "
        if lay.uses_magnets
        else "heat-set M3; "
    )
    warnings.append(
        "FDM PETG/ASA tray is not a certified UL94 / IEC mains enclosure; "
        + latch_note
        + "no snap as the only latch; socket well has no lid; "
        "lid prints as closed (outer up, lip to bed)"
    )
    if _mount_xy(lay):
        warnings.append(
            "device floor mounts are photo_estimate; caliper GSM ear and "
            "socket pitch before print"
        )
    if _rest_strip_aabbs(lay):
        warnings.append(
            "anti-rock rest strips under GSM and socket sit at mount-pad "
            f"height {MOUNT_PAD_H_MM} mm, width {REST_STRIP_W_MM} mm"
        )
    if lay.wire_channels:
        warnings.append(
            "−Y mousehole and floor grooves follow the sketch routes; "
            "not bought glands; not SMA"
        )
    if sma_yz is not None:
        warnings.append(
            "SMA +X wall hole is datasheet mid-height of 31.5 mm body; "
            "caliper this unit (listings also show SMA on the lid)"
        )
    magnet_node = (spec.get("tray") or {}).get("magnet_d_mm") or {}
    if lay.uses_magnets and not bool(
        magnet_node.get("confirmed") if isinstance(magnet_node, dict) else False
    ):
        warnings.append(
            "magnet_d_mm is not confirmed — change tray.magnet_d_mm to match "
            "the disc you will glue (6/8/10/12 typical); boss OD follows"
        )
    return EnclosureBuild(
        base=base,
        lid=lid_print,
        assembled=assembled,
        printable=printable,
        keepout=keepout,
        keepout_volume=intersect_volume(assembled, keepout),
        outer=(lay.outer_l, lay.outer_w, lay.base_h + lid_stack),
        usb_cut_wh=(0.0, 0.0),
        cavity_lw=(lay.inner_l, lay.inner_w),
        warnings=warnings,
        report=report,
    )
