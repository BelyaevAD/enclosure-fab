"""Operator names for enclosure vents. The messages below name the live cutters."""

from __future__ import annotations

from typing import Any

KIND_WINDOW = "window"
KIND_SLOTS = "slots"
KIND_GRID_45 = "grid-45"
KIND_LOUVER_45 = "louver-45"
KIND_HONEYCOMB = "honeycomb"

ORIENT_HORIZONTAL = "horizontal"
ORIENT_VERTICAL = "vertical"

PROT_OPEN = "open"
PROT_INDOOR = "indoor"
PROT_DUST = "dust"
PROT_DRIP = "drip"
PROT_SEALED = "sealed"

LIVE_KINDS = frozenset({KIND_WINDOW, KIND_SLOTS})
LIVE_ORIENTATIONS = frozenset({ORIENT_HORIZONTAL})
LIVE_WALL_KINDS = frozenset({KIND_WINDOW, KIND_SLOTS, KIND_GRID_45})

# IEC 60529 probe diameters — analogy for clear opening, not a certified IP.
PROBE_TOOL_MM = 2.5
PROBE_WIRE_MM = 1.0
OPEN_PROSVET_MM = 2.4
INDOOR_PROSVET_MIN_MM = 1.8
DUST_PROSVET_MAX_MM = 1.2


def resolve_kind(block: dict[str, Any]) -> str:
    raw = block.get("kind")
    if raw:
        return str(raw)
    pattern = str(block.get("pattern") or KIND_SLOTS)
    if pattern == KIND_HONEYCOMB:
        return KIND_HONEYCOMB
    return KIND_WINDOW


def resolve_orientation(block: dict[str, Any]) -> str:
    raw = block.get("orientation")
    if raw:
        return str(raw)
    return ORIENT_HORIZONTAL


def catalog_issues(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Warnings, errors for named vent kinds that the live cutter does not cut."""
    warnings: list[str] = []
    errors: list[str] = []
    case = spec.get("case") or {}
    block = case.get("vents")
    if not block:
        return warnings, errors
    template = spec.get("template_id") or "enclosure_box"
    faces = {str(f) for f in (block.get("faces") or [])}
    kind = resolve_kind(block)
    orientation = resolve_orientation(block)
    protection = str(block.get("protection") or "")
    slot_w = float(block.get("slot_w_mm") or OPEN_PROSVET_MM)

    if protection == PROT_SEALED and faces:
        errors.append(
            "case.vents.protection=sealed means no openings; "
            "remove case.vents and copy sealed-snap, do not punch a vented SKU"
        )

    if template != "enclosure_snap":
        return warnings, errors

    if kind == KIND_LOUVER_45:
        errors.append(
            "case.vents.kind=louver-45 (45-degree blades through the wall) "
            "has no live cutter; not grid-45."
        )
    elif kind not in LIVE_WALL_KINDS and kind != KIND_HONEYCOMB:
        errors.append(
            f"case.vents.kind={kind} is not a catalog name "
            "(window|slots|grid-45|louver-45|honeycomb)."
        )

    if kind in LIVE_KINDS and orientation == ORIENT_VERTICAL:
        errors.append(
            "case.vents.orientation=vertical (upright rectangles) "
            "has no live cutter; live windows are horizontal."
        )
    elif kind in LIVE_KINDS and orientation not in LIVE_ORIENTATIONS:
        errors.append(
            f"case.vents.orientation={orientation} is not horizontal|vertical."
        )

    if protection == PROT_DRIP:
        errors.append(
            "case.vents.protection=drip needs kind=louver-45 (drip louvers); "
            "that cutter is not live."
        )
    if protection == PROT_DUST:
        if "lid" in faces:
            errors.append(
                "case.vents.protection=dust cannot use lid exhaust: "
                "roof-on-bed wells need a gap ≥ 2.4 mm (see the vent notes)"
            )
        elif slot_w > DUST_PROSVET_MAX_MM:
            warnings.append(
                f"case.vents.protection=dust but slot_w_mm={slot_w} > "
                f"{DUST_PROSVET_MAX_MM} mm gap. Narrow the slot or use indoor"
            )
        else:
            errors.append(
                "case.vents.protection=dust (gap ≤ 1.2 mm) has no live cutter; "
                "indoor wall windows start at 1.8 mm."
            )
    if protection == PROT_OPEN and slot_w + 1e-9 < OPEN_PROSVET_MM:
        warnings.append(
            f"case.vents.protection=open expects a gap ≥ {OPEN_PROSVET_MM} mm; "
            f"slot_w_mm={slot_w} is indoor-class"
        )
    if protection == PROT_INDOOR and slot_w + 1e-9 >= PROBE_TOOL_MM:
        warnings.append(
            f"case.vents.protection=indoor but slot_w_mm={slot_w} ≥ {PROBE_TOOL_MM} "
            "(tool probe); that is an open-class gap"
        )
    if protection and protection not in {
        PROT_OPEN,
        PROT_INDOOR,
        PROT_DUST,
        PROT_DRIP,
        PROT_SEALED,
        "",
    }:
        errors.append(
            f"case.vents.protection={protection} is not "
            "open|indoor|dust|drip|sealed."
        )
    return warnings, errors
