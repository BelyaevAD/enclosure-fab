"""FDM fit defaults. Spec millimetres are the part; the template adds clearance."""

from __future__ import annotations

# Station printer. Not a print gate.
STATION_PRINTER = "bambu-p1s"
NOZZLE_MM = 0.4
NOZZLE_TYPE = "hardened-steel"
# Bambu Studio keeps line width near the nozzle (wiki: 0.75–1.5×; default ≈ 0.42).
LINE_WIDTH_MM = 0.42
BUILD_MM = (256.0, 256.0, 256.0)
# Two halves on the bed, not the assembled stack.
PRINT_POSE_GAP_MM = 5.0


def print_pose_fits_bed(outer_l: float, outer_w: float, gap: float = PRINT_POSE_GAP_MM) -> tuple[bool, bool]:
    """(single half fits the 256 cube, two halves can sit side-by-side)."""
    bed_x, bed_y, _bed_z = BUILD_MM
    single = outer_l <= bed_x and outer_w <= bed_y
    two = single and (
        (2.0 * outer_l + gap <= bed_x) or (2.0 * outer_w + gap <= bed_y)
    )
    return single, two

# Per side on a panel cut. Close slide-in for 0.4 mm nozzle (Flashforge / MiniCAD).
OPENING_CLEARANCE_MM = 0.3
# Lid skirt vs base cavity, per side.
LID_FIT_MM = 0.25
# Board pocket XY if the spec omits gap_mm.
BOARD_GAP_MM = 0.3
# FDM visual minimum (p1s-0.4, ~2 lines). Strap/wall still target ≥ 1.2 (3 perimeters).
MIN_FEATURE_MM = 0.8


def opening_cut_size(
    nominal_w: float,
    nominal_h: float,
    clearance: float = OPENING_CLEARANCE_MM,
) -> tuple[float, float]:
    return nominal_w + 2.0 * clearance, nominal_h + 2.0 * clearance


def wall_for_span(longest_inner_mm: float) -> float:
    """Starting wall, not a gate. Larger boxes get ribs, not a 5 mm shell."""
    if longest_inner_mm < 50:
        return 1.5
    if longest_inner_mm < 120:
        return 2.0
    return 2.4
