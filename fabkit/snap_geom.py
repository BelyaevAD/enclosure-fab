"""Millimetre layout for enclosure_snap. No CadQuery.

usb.offset_mm.z is the connector-shell centre from the PCB bottom
(board_oz), same contract as enclosure_box. Do not treat it as the FR4
top or the shell underside.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fabkit.fit import LID_FIT_MM, LINE_WIDTH_MM, OPENING_CLEARANCE_MM, opening_cut_size

TEMPLATE_ID = "enclosure_snap"
LINTEL_CANDIDATE_MM = 1.2
# Remaining plastic in the *base* above the USB window. Assembled lintel can
# look fine (lid roof 1.5) while the base only has a 0.1 mm hair at the split;
# Studio drops anything thinner than ~3 lines.
BASE_USB_MIN_MM = round(3.0 * LINE_WIDTH_MM, 2)
GROOVE_Z0_DOWN_MM = 1.35
GROOVE_Z1_DOWN_MM = 0.65
BEAD_Z0_FROM_ROOF_MM = 0.7
BEAD_H_MM = 0.55
SKIRT_W_MM = 1.0
POST_SIZE_MM = 2.2
POST_INSET_MM = 0.7
# Lid skirt hangs this far below the split; USB must finish below it
# unless case.lid_open_usb (U-bay: +X rim gone, snaps stop at the can).
SKIRT_USB_CLEAR_MM = 0.5
USB_BAY_CLEAR_MM = 0.6
USB_BODY_L_DEFAULT_MM = 14.0
GROOVE_X_INSET_MM = 1.0
BEAD_X_INSET_MM = 0.4
# Copied from vents.py — P0c does not change that cutter.
BED_CLEAR_MM = 3.2
SNAP_CLEAR_MM = 1.2
INTAKE_MIN_BAND_MM = 2.4
INTAKE_FALLBACK_CLEAR_MM = 0.8
INTAKE_SAFE_EXTRA_MM = SNAP_CLEAR_MM + INTAKE_MIN_BAND_MM + GROOVE_Z0_DOWN_MM


def _opt_mm(spec: dict[str, Any], path: str, default: float) -> float:
    try:
        return _mm(spec, path)
    except KeyError:
        return default


def _mm(spec: dict[str, Any], path: str) -> float:
    cur: Any = spec
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(path)
        cur = cur[part]
    return float(cur["value"])


def _case(spec: dict[str, Any], key: str, default: float | bool) -> float | bool:
    block = spec.get("case") or {}
    if key not in block or block[key] is None:
        return default
    if isinstance(default, bool):
        return bool(block[key])
    return float(block[key])


@dataclass(frozen=True)
class YSpan:
    y0: float
    y1: float

    def overlap(self, other: YSpan) -> float:
        return max(0.0, min(self.y1, other.y1) - max(self.y0, other.y0))

    def as_list(self) -> list[float]:
        return [round(self.y0, 4), round(self.y1, 4)]


@dataclass(frozen=True)
class SnapLayout:
    wall: float
    gap_x: float
    gap_y: float
    length: float
    width: float
    thick: float
    usb_w: float
    usb_h: float
    usb_y: float
    usb_z: float
    opening_clearance: float
    cut_w: float
    cut_h: float
    outer_l: float
    outer_w: float
    base_h: float
    lid_h: float
    post_h: float
    post_size: float
    post_inset: float
    rib_h_spec: float
    snap: float
    inlet_d: float
    press_board: bool
    lid_open_usb: bool
    usb_body_l: float
    usb_skirt_stop_x: float
    roof_h: float
    skirt_h: float
    fit: float
    floor: float
    board_ox: float
    board_oy: float
    board_oz: float
    usb_cy: float
    usb_cz: float
    usb_z0: float
    usb_z1: float
    outer_z: float
    rib_h: float
    groove_z0: float
    groove_z1: float
    sx0: float
    sy0: float
    sx1: float
    sy1: float
    sw: float
    bead_z0_print: float
    bead_z1_print: float
    bead_z0_asm: float
    bead_z1_asm: float
    bead_x0: float
    bead_x1: float
    groove_plus_y: YSpan
    groove_minus_y: YSpan
    bead_plus_y_asm: YSpan
    bead_minus_y_asm: YSpan
    engage_plus_y: YSpan
    engage_minus_y: YSpan
    cavity_lw: tuple[float, float]
    lintel_left_mm: float
    lintel_ok: bool
    usb_open_at_split: bool
    base_usb_remain_mm: float
    usb_base_sliver: bool
    has_vents: bool
    intake_z0: float
    intake_z1: float
    intake_fallback: bool
    intake_clearance: float
    intake_safe_base_h: float
    warnings: tuple[str, ...]
    print_errors: tuple[str, ...]


def _intake_band(wall: float, groove_z0: float) -> tuple[float, float, bool, float]:
    z0 = max(wall + 0.3, BED_CLEAR_MM)
    z1_nominal = groove_z0 - SNAP_CLEAR_MM
    fallback = z1_nominal < z0 + INTAKE_MIN_BAND_MM
    if fallback:
        z1 = min(groove_z0 - INTAKE_FALLBACK_CLEAR_MM, z0 + INTAKE_MIN_BAND_MM)
    else:
        z1 = z1_nominal
    return z0, z1, fallback, groove_z0 - z1


def _engage(a: YSpan, b: YSpan) -> YSpan:
    return YSpan(max(a.y0, b.y0), min(a.y1, b.y1))


def layout_from_spec(spec: dict[str, Any]) -> SnapLayout:
    wall = float(spec.get("wall_mm") or 1.5)
    gap_x = float(spec.get("gap_mm") or 0.3)
    gap_y = float(_case(spec, "gap_y_mm", 0.25))
    length = _mm(spec, "board.length_mm")
    width = _mm(spec, "board.width_mm")
    thick = _mm(spec, "board.thickness_mm")
    usb_w = _mm(spec, "usb.opening_wh_mm.w")
    usb_h = _mm(spec, "usb.opening_wh_mm.h")
    usb_y = _mm(spec, "usb.offset_mm.y")
    usb_z = _mm(spec, "usb.offset_mm.z")
    opening_clearance = float(_case(spec, "opening_clearance_mm", OPENING_CLEARANCE_MM))
    cut_w, cut_h = opening_cut_size(usb_w, usb_h, opening_clearance)
    outer_l = float(_case(spec, "outer_l_mm", 31.0))
    outer_w = float(_case(spec, "outer_w_mm", 18.5))
    base_h = float(_case(spec, "base_h_mm", 9.5))
    lid_h = float(_case(spec, "lid_h_mm", 3.5))
    post_h = float(_case(spec, "post_h_mm", 1.5))
    post_size = float(_case(spec, "post_size_mm", POST_SIZE_MM))
    post_inset = float(_case(spec, "post_inset_mm", POST_INSET_MM))
    rib_h_spec = float(_case(spec, "rib_h_mm", 1.0))
    snap = float(_case(spec, "snap_mm", 0.4))
    inlet_d = float(_case(spec, "inlet_d_mm", 3.0))
    press_board = bool(_case(spec, "press_board", True))
    lid_open_usb = bool(_case(spec, "lid_open_usb", False))
    usb_body_l = _opt_mm(spec, "usb.body_l_mm", USB_BODY_L_DEFAULT_MM)
    roof_h = min(1.5, lid_h)
    skirt_h = max(lid_h - roof_h, 1.6)
    fit = float(_case(spec, "lid_fit_mm", LID_FIT_MM))
    floor = wall
    board_ox = wall + gap_x
    board_oy = wall + gap_y
    board_oz = floor + post_h
    usb_skirt_stop_x = outer_l
    if lid_open_usb:
        usb_skirt_stop_x = board_ox + length - usb_body_l - USB_BAY_CLEAR_MM
    usb_cy = board_oy + usb_y
    usb_cz = board_oz + usb_z
    usb_z0 = usb_cz - cut_h / 2.0
    usb_z1 = usb_cz + cut_h / 2.0
    outer_z = base_h + roof_h
    rib_h = (base_h - board_oz - thick + 0.15) if press_board else rib_h_spec
    rib_h = max(rib_h, 0.6)
    groove_z0 = base_h - GROOVE_Z0_DOWN_MM
    groove_z1 = base_h - GROOVE_Z1_DOWN_MM
    sx0, sy0 = wall + fit, wall + fit
    sx1, sy1 = outer_l - wall - fit, outer_w - wall - fit
    sw = SKIRT_W_MM
    bead_z0_print = roof_h + BEAD_Z0_FROM_ROOF_MM
    bead_z1_print = bead_z0_print + BEAD_H_MM
    bead_z0_asm = outer_z - bead_z1_print
    bead_z1_asm = outer_z - bead_z0_print
    bead_x0 = sx0 + sw + BEAD_X_INSET_MM
    bead_x1 = sx1 - sw - BEAD_X_INSET_MM
    # Groove into the wall from the inner face (assembled = print on the base).
    groove_plus_y = YSpan(outer_w - wall, outer_w - wall + snap)
    groove_minus_y = YSpan(wall - snap, wall)
    # Print −Y bead (outer skirt) becomes assembled +Y after the 180° X flip.
    bead_plus_y_asm = YSpan(outer_w - sy0, outer_w - sy0 + snap)
    bead_minus_y_asm = YSpan(outer_w - sy1 - snap, outer_w - sy1)
    engage_plus_y = _engage(bead_plus_y_asm, groove_plus_y)
    engage_minus_y = _engage(bead_minus_y_asm, groove_minus_y)
    lintel_left = outer_z - usb_z1
    lintel_ok = usb_z1 <= outer_z - LINTEL_CANDIDATE_MM + 1e-9
    usb_open_at_split = usb_z1 > base_h + 1e-9
    base_usb_remain = base_h - usb_z1
    usb_base_sliver = 1e-9 < base_usb_remain < BASE_USB_MIN_MM - 1e-9
    vents = (spec.get("case") or {}).get("vents") or {}
    has_vents = bool(vents.get("faces"))
    intake_z0, intake_z1, intake_fallback, intake_clearance = _intake_band(wall, groove_z0)
    intake_safe_base_h = intake_z0 + INTAKE_SAFE_EXTRA_MM

    warnings: list[str] = []
    print_errors: list[str] = []
    if not press_board:
        warnings.append(
            "press_board is false: lid has no press pads (USB/components not crushed)"
        )
    if lid_open_usb:
        warnings.append(
            "lid_open_usb: +X lid rim is a U-bay to the USB can; "
            "roof plate stays; ±Y snaps stop at the can"
        )
    skirt_bottom = base_h - skirt_h
    if (not lid_open_usb) and usb_z1 + SKIRT_USB_CLEAR_MM > skirt_bottom + 1e-9:
        warnings.append(
            f"USB cutter top {usb_z1:.2f} mm meets the lid skirt "
            f"(bottom {skirt_bottom:.2f} mm); raise base_h so the can is "
            f"not pinched at the latch"
        )
    if not lintel_ok:
        msg = (
            f"USB cutter top {usb_z1:.2f} mm would leave lintel "
            f"{lintel_left:.2f} mm under the roof (need >= {LINTEL_CANDIDATE_MM:.1f}); "
            "roof left intact. Do not raise 11.0 in this pass"
        )
        warnings.append(msg)
        print_errors.append(msg)
    elif usb_open_at_split and not lid_open_usb:
        msg = (
            f"USB cutter top {usb_z1:.2f} mm is above the split {base_h:.2f} mm; "
            "lid is not punched"
        )
        warnings.append(msg)
    if usb_base_sliver and not lid_open_usb:
        msg = (
            f"USB cutter top {usb_z1:.2f} mm leaves {base_usb_remain:.2f} mm "
            f"lip in the base above the window (need >= {BASE_USB_MIN_MM:.2f}, "
            "~3 lines); Studio drops a feature thinner than a perimeter"
        )
        warnings.append(msg)
        print_errors.append(msg)
    if has_vents and (intake_fallback or intake_clearance + 1e-9 < SNAP_CLEAR_MM):
        msg = (
            f"case.vents intake band fallback or snap clearance "
            f"{intake_clearance:.2f} mm < {SNAP_CLEAR_MM:.1f} "
            f"(z0={intake_z0:.2f} z1={intake_z1:.2f} groove_z0={groove_z0:.2f}); "
            "vents.py geometry was not changed"
        )
        warnings.append(msg)
        print_errors.append(msg)
    elif has_vents and base_h + 1e-9 < intake_safe_base_h:
        warnings.append(
            f"case.vents intake is silent only when base_h >= {intake_safe_base_h:.2f} mm "
            f"(now {base_h:.2f}); vents.py geometry was not changed"
        )

    return SnapLayout(
        wall=wall,
        gap_x=gap_x,
        gap_y=gap_y,
        length=length,
        width=width,
        thick=thick,
        usb_w=usb_w,
        usb_h=usb_h,
        usb_y=usb_y,
        usb_z=usb_z,
        opening_clearance=opening_clearance,
        cut_w=cut_w,
        cut_h=cut_h,
        outer_l=outer_l,
        outer_w=outer_w,
        base_h=base_h,
        lid_h=lid_h,
        post_h=post_h,
        post_size=post_size,
        post_inset=post_inset,
        rib_h_spec=rib_h_spec,
        snap=snap,
        inlet_d=inlet_d,
        press_board=press_board,
        lid_open_usb=lid_open_usb,
        usb_body_l=usb_body_l,
        usb_skirt_stop_x=usb_skirt_stop_x,
        roof_h=roof_h,
        skirt_h=skirt_h,
        fit=fit,
        floor=floor,
        board_ox=board_ox,
        board_oy=board_oy,
        board_oz=board_oz,
        usb_cy=usb_cy,
        usb_cz=usb_cz,
        usb_z0=usb_z0,
        usb_z1=usb_z1,
        outer_z=outer_z,
        rib_h=rib_h,
        groove_z0=groove_z0,
        groove_z1=groove_z1,
        sx0=sx0,
        sy0=sy0,
        sx1=sx1,
        sy1=sy1,
        sw=sw,
        bead_z0_print=bead_z0_print,
        bead_z1_print=bead_z1_print,
        bead_z0_asm=bead_z0_asm,
        bead_z1_asm=bead_z1_asm,
        bead_x0=bead_x0,
        bead_x1=bead_x1,
        groove_plus_y=groove_plus_y,
        groove_minus_y=groove_minus_y,
        bead_plus_y_asm=bead_plus_y_asm,
        bead_minus_y_asm=bead_minus_y_asm,
        engage_plus_y=engage_plus_y,
        engage_minus_y=engage_minus_y,
        cavity_lw=(outer_l - 2.0 * wall, outer_w - 2.0 * wall),
        lintel_left_mm=lintel_left,
        lintel_ok=lintel_ok,
        usb_open_at_split=usb_open_at_split,
        base_usb_remain_mm=base_usb_remain,
        usb_base_sliver=usb_base_sliver,
        has_vents=has_vents,
        intake_z0=intake_z0,
        intake_z1=intake_z1,
        intake_fallback=intake_fallback,
        intake_clearance=intake_clearance,
        intake_safe_base_h=intake_safe_base_h,
        warnings=tuple(warnings),
        print_errors=tuple(print_errors),
    )


def layout_report(lay: SnapLayout) -> dict[str, Any]:
    return {
        "template_id": TEMPLATE_ID,
        "usb_z0_mm": round(lay.usb_z0, 4),
        "usb_z1_mm": round(lay.usb_z1, 4),
        "usb_cz_mm": round(lay.usb_cz, 4),
        "usb_lintel_ok": lay.lintel_ok,
        "usb_base_remain_mm": round(lay.base_usb_remain_mm, 4),
        "lid_open_usb": lay.lid_open_usb,
        "usb_skirt_stop_x_mm": round(lay.usb_skirt_stop_x, 4),
        "snap_groove_plus_y_mm": lay.groove_plus_y.as_list(),
        "snap_bead_plus_y_mm": lay.bead_plus_y_asm.as_list(),
        "snap_engage_plus_y_mm": lay.engage_plus_y.as_list(),
        "snap_groove_minus_y_mm": lay.groove_minus_y.as_list(),
        "snap_bead_minus_y_mm": lay.bead_minus_y_asm.as_list(),
        "snap_engage_minus_y_mm": lay.engage_minus_y.as_list(),
        "intake_fallback": lay.intake_fallback,
        "intake_clearance_mm": round(lay.intake_clearance, 4),
    }


def aabb_overlap_1d(a0: float, a1: float, b0: float, b1: float) -> bool:
    return a0 < b1 and a1 > b0
