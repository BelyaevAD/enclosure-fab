from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from fabkit.fit import (
    BUILD_MM,
    MIN_FEATURE_MM,
    NOZZLE_MM,
    STATION_PRINTER,
    print_pose_fits_bed,
    wall_for_span,
)
from fabkit.io_yaml import load_yaml
from fabkit.paths import SCHEMA_DIR
from fabkit.vent_catalog import catalog_issues
from fabkit.vents import LID_MIN_SLOT_W_MM, SLOT_W_MM

ENCLOSURE_FIT_CRITICAL = (
    "board.length_mm",
    "board.width_mm",
    "board.thickness_mm",
    "usb.offset_mm.x",
    "usb.offset_mm.y",
    "usb.offset_mm.z",
    "usb.opening_wh_mm.w",
    "usb.opening_wh_mm.h",
    "keepout.board",
)
DOLL_FIT_CRITICAL = (
    "shoe.foot_length_mm",
    "shoe.foot_width_mm",
    "shoe.foot_height_mm",
    "shoe.heel_lift_mm",
    "shoe.ankle_diameter_mm",
    "shoe.strap_width_mm",
    "shoe.strap_thickness_mm",
    "shoe.clip_gap_mm",
    "keepout.foot",
)
SHELL_FIT_CRITICAL = (
    "device.length_mm",
    "device.width_mm",
    "device.height_mm",
    "keepout.device",
    "shell.sma.x_mm",
    "shell.sma.y_mm",
)
TRAY_FIT_CRITICAL = (
    "tray.inner_l_mm",
    "tray.inner_w_mm",
    "tray.inner_h_mm",
    "pockets.gsm.x_mm",
    "pockets.gsm.y_mm",
    "pockets.gsm.length_mm",
    "pockets.gsm.width_mm",
    "pockets.gsm.height_mm",
    "pockets.psu.x_mm",
    "pockets.psu.y_mm",
    "pockets.psu.length_mm",
    "pockets.psu.width_mm",
    "pockets.psu.height_mm",
    "pockets.socket.x_mm",
    "pockets.socket.y_mm",
    "pockets.socket.length_mm",
    "pockets.socket.width_mm",
    "pockets.socket.height_mm",
    "keepout.tray",
)
MAGNET_BOX_FIT_CRITICAL = (
    "box.outer_l_mm",
    "box.outer_w_mm",
    "box.outer_h_mm",
    "box.magnet_d_mm",
    "box.magnet_h_mm",
    "keepout.box",
)
# Default / enclosure alias — protocol.py and older tests.
FIT_CRITICAL_PATHS = ENCLOSURE_FIT_CRITICAL
DOLL_TEMPLATE = "doll_mary_jane"
SHELL_TEMPLATE = "enclosure_shell"
TRAY_TEMPLATE = "enclosure_tray"
MAGNET_BOX_TEMPLATE = "enclosure_magnet_box"
RING_TEMPLATE = "ring_yoke"
STRIP_TEMPLATE = "strip_clip"
RING_FIT_CRITICAL = (
    "rings.band_mm",
    "rings.bar.circumference_mm",
    "rings.bar.mouth_mm",
    "rings.handle.circumference_mm",
    "rings.handle.mouth_mm",
    "keepout.bores",
)
STRIP_FIT_CRITICAL = (
    "clip.inner_x_mm",
    "clip.inner_z_mm",
    "clip.band_mm",
    "clip.tooth_mm",
    "clip.hole_d_mm",
    "keepout.pocket",
)
_NON_ENCLOSURE = frozenset(
    {DOLL_TEMPLATE, SHELL_TEMPLATE, TRAY_TEMPLATE, MAGNET_BOX_TEMPLATE, RING_TEMPLATE, STRIP_TEMPLATE}
)

PRINT_BLOCKED_FAMILIES = frozenset({"esp32_cam"})
# enclosure_box cuts USB only on the +X face. x should sit at the +X end of the PCB.
USB_PLUS_X_TOLERANCE_MM = 4.0


@dataclass
class GateResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unconfirmed: list[str] = field(default_factory=list)

    def raise_if_failed(self) -> None:
        if not self.ok:
            raise GateError("\n".join(self.errors))


class GateError(ValueError):
    pass


def _spec_validator() -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / "spec.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def walk_path(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def is_confirmed_node(node: Any) -> bool:
    if isinstance(node, dict) and "confirmed" in node:
        return bool(node["confirmed"])
    return False


def fit_critical_paths(spec: dict[str, Any]) -> tuple[str, ...]:
    template = spec.get("template_id")
    if template == DOLL_TEMPLATE:
        return DOLL_FIT_CRITICAL
    if template == SHELL_TEMPLATE:
        return SHELL_FIT_CRITICAL
    if template == TRAY_TEMPLATE:
        return TRAY_FIT_CRITICAL
    if template == MAGNET_BOX_TEMPLATE:
        return MAGNET_BOX_FIT_CRITICAL
    if template == RING_TEMPLATE:
        return RING_FIT_CRITICAL
    if template == STRIP_TEMPLATE:
        return STRIP_FIT_CRITICAL
    if template == "enclosure_round":
        return ()
    return ENCLOSURE_FIT_CRITICAL


def unconfirmed_fit_critical(spec: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for path in fit_critical_paths(spec):
        try:
            node = walk_path(spec, path)
        except KeyError:
            missing.append(f"{path} (absent)")
            continue
        if not is_confirmed_node(node):
            missing.append(path)
    template = spec.get("template_id")
    if template not in _NON_ENCLOSURE:
        usb = spec.get("usb")
        if isinstance(usb, dict) and "body_l_mm" in usb:
            if not is_confirmed_node(usb["body_l_mm"]):
                missing.append("usb.body_l_mm")
        headers = spec.get("headers")
        if isinstance(headers, dict):
            for index, row in enumerate(headers.get("rows") or []):
                if not isinstance(row, dict):
                    continue
                for key in ("y_mm", "x0_mm", "x1_mm"):
                    path = f"headers.rows[{index}].{key}"
                    if not is_confirmed_node(row.get(key)):
                        missing.append(path)
        button = spec.get("button")
        if isinstance(button, dict):
            face = str(button.get("face") or "plus_x")
            along = "button.offset_mm.x" if face in {"plus_y", "minus_y"} else "button.offset_mm.y"
            for path in (
                along,
                "button.offset_mm.z",
                "button.opening_wh_mm.w",
                "button.opening_wh_mm.h",
            ):
                try:
                    node = walk_path(spec, path)
                except KeyError:
                    missing.append(f"{path} (absent)")
                    continue
                if not is_confirmed_node(node):
                    missing.append(path)
    tray = spec.get("tray")
    if isinstance(tray, dict) and "magnet_d_mm" in tray:
        if not is_confirmed_node(tray.get("magnet_d_mm")):
            missing.append("tray.magnet_d_mm")
    return missing


def _flex_tab_tie_warnings(btn: dict[str, Any]) -> list[str]:
    if str(btn.get("style") or "") != "flex_tab":
        return []
    raw = btn.get("tie_mm")
    if raw is None:
        return []
    try:
        tie = float(raw)
    except (TypeError, ValueError):
        return []
    extra: list[str] = []
    if tie <= 1e-9:
        extra.append(
            "button.tie_mm=0 leaves a hanging U-slot on a standing wall; "
            "CAD whiskers (tie_mm ~0.42) or the tongue sags."
        )
        return extra
    if tie + 1e-9 < NOZZLE_MM:
        extra.append(
            f"button.tie_mm={tie} is thinner than nozzle {NOZZLE_MM} mm; "
            "tick would not extrude anyway."
        )
    return extra


def geometry_checks(spec: dict[str, Any], mode: str) -> tuple[list[str], list[str]]:
    """Template-level geometry gates that JSON Schema cannot express."""
    if spec.get("template_id") == "enclosure_round":
        return [], []
    if spec.get("template_id") == DOLL_TEMPLATE:
        return _doll_geometry_checks(spec)
    if spec.get("template_id") == SHELL_TEMPLATE:
        return _shell_geometry_checks(spec)
    if spec.get("template_id") == TRAY_TEMPLATE:
        return _tray_geometry_checks(spec)
    if spec.get("template_id") == MAGNET_BOX_TEMPLATE:
        return _magnet_box_geometry_checks(spec)
    if spec.get("template_id") == RING_TEMPLATE:
        return _ring_geometry_checks(spec)
    if spec.get("template_id") == STRIP_TEMPLATE:
        return _strip_geometry_checks(spec)
    warnings: list[str] = []
    errors: list[str] = []
    try:
        length = float(walk_path(spec, "board.length_mm")["value"])
        usb_x = float(walk_path(spec, "usb.offset_mm.x")["value"])
    except (KeyError, TypeError, ValueError):
        return warnings, errors
    if usb_x < length - USB_PLUS_X_TOLERANCE_MM:
        msg = (
            "enclosure_box expects USB on the +X face; "
            f"usb.offset_mm.x={usb_x} is not near board.length_mm={length}"
        )
        if mode == "print":
            errors.append(msg)
        else:
            warnings.append(msg)
    warnings.extend(_flex_tab_tie_warnings(spec.get("button") or {}))
    try:
        ko = walk_path(spec, "keepout.board")
        kmin = [float(v) for v in ko["min"]]
        kmax = [float(v) for v in ko["max"]]
    except (KeyError, TypeError, ValueError):
        return warnings, errors
    if len(kmin) != 3 or len(kmax) != 3 or any(a >= b for a, b in zip(kmin, kmax)):
        errors.append("keepout.board AABB is degenerate (min >= max on some axis)")
    warnings.extend(_fit_warnings(spec))
    catalog_w, catalog_e = catalog_issues(spec)
    warnings.extend(catalog_w)
    errors.extend(catalog_e)
    if spec.get("template_id") == "enclosure_snap":
        from fabkit.snap_geom import layout_from_spec

        try:
            lay = layout_from_spec(spec)
        except (KeyError, TypeError, ValueError):
            return warnings, errors
        warnings.extend(lay.warnings)
        if mode == "print":
            errors.extend(lay.print_errors)
        vents = (spec.get("case") or {}).get("vents") or {}
        faces = {str(f) for f in (vents.get("faces") or [])}
        if "lid" in faces:
            slot_w = float(vents.get("slot_w_mm") or SLOT_W_MM)
            if slot_w + 1e-9 < LID_MIN_SLOT_W_MM:
                msg = (
                    f"case.vents.slot_w_mm={slot_w} < {LID_MIN_SLOT_W_MM}: "
                    "roof-on-bed exhaust narrower than ~6 lines closes in Studio"
                )
                if mode == "print":
                    errors.append(msg)
    return warnings, errors


def _shell_geometry_checks(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        ko = walk_path(spec, "keepout.device")
        kmin = [float(v) for v in ko["min"]]
        kmax = [float(v) for v in ko["max"]]
    except (KeyError, TypeError, ValueError):
        errors.append("keepout.device AABB is missing")
        return warnings, errors
    if len(kmin) != 3 or len(kmax) != 3 or any(a >= b for a, b in zip(kmin, kmax)):
        errors.append("keepout.device AABB is degenerate (min >= max on some axis)")
    try:
        length = float(walk_path(spec, "device.length_mm")["value"])
        width = float(walk_path(spec, "device.width_mm")["value"])
        height = float(walk_path(spec, "device.height_mm")["value"])
        aabb = (kmax[0] - kmin[0], kmax[1] - kmin[1], kmax[2] - kmin[2])
        if any(abs(a - b) > 0.25 for a, b in zip(aabb, (length, width, height))):
            warnings.append(
                f"keepout.device {aabb[0]:.1f}×{aabb[1]:.1f}×{aabb[2]:.1f} vs "
                f"device {length}×{width}×{height} (device CS: +X terminals, +Z up)"
            )
    except (KeyError, TypeError, ValueError, IndexError):
        pass
    shell = spec.get("shell") or {}
    partition = shell.get("partition_t_mm")
    if partition is not None and float(partition) + 1e-9 < 2.0:
        errors.append(
            f"shell.partition_t_mm={partition} < 2.0: HV/LV barrier is a mains finger-stop"
        )
    warnings.extend(_fit_warnings(spec))
    catalog_w, catalog_e = catalog_issues(spec)
    warnings.extend(catalog_w)
    errors.extend(catalog_e)
    return warnings, errors


def _tray_geometry_checks(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        ko = walk_path(spec, "keepout.tray")
        kmin = [float(v) for v in ko["min"]]
        kmax = [float(v) for v in ko["max"]]
    except (KeyError, TypeError, ValueError):
        errors.append("keepout.tray AABB is missing")
        return warnings, errors
    if len(kmin) != 3 or len(kmax) != 3 or any(a >= b for a, b in zip(kmin, kmax)):
        errors.append("keepout.tray AABB is degenerate (min >= max on some axis)")
    socket = (spec.get("pockets") or {}).get("socket") or {}
    if socket.get("covered") is True:
        errors.append(
            "pockets.socket.covered=true: this tray's socket well must stay open "
            "(no lid over the Schuko face)"
        )
    try:
        from fabkit.enclosure_tray import layout_from_spec

        lay = layout_from_spec(spec)
        warnings.extend(lay.warnings)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"tray layout: {exc}")
        return warnings, errors
    warnings.extend(_fit_warnings(spec))
    catalog_w, catalog_e = catalog_issues(spec)
    warnings.extend(catalog_w)
    errors.extend(catalog_e)
    return warnings, errors


def _magnet_box_geometry_checks(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        ko = walk_path(spec, "keepout.box")
        kmin = [float(v) for v in ko["min"]]
        kmax = [float(v) for v in ko["max"]]
    except (KeyError, TypeError, ValueError):
        errors.append("keepout.box AABB is missing")
        return warnings, errors
    if len(kmin) != 3 or len(kmax) != 3 or any(a >= b for a, b in zip(kmin, kmax)):
        errors.append("keepout.box AABB is degenerate (min >= max on some axis)")
    try:
        from fabkit.enclosure_magnet_box import layout_from_spec

        lay = layout_from_spec(spec)
        warnings.extend(lay.warnings)
        if kmax[0] - kmin[0] > lay.inner_l + 0.05 or kmax[1] - kmin[1] > lay.inner_w + 0.05:
            warnings.append("keepout.box plan is larger than the inner cavity")
        if kmax[2] - kmin[2] > lay.inner_h + 0.05:
            warnings.append("keepout.box height exceeds the inner cavity")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"magnet-box layout: {exc}")
        return warnings, errors
    warnings.extend(_fit_warnings(spec))
    return warnings, errors


def _doll_geometry_checks(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        ko = walk_path(spec, "keepout.foot")
        kmin = [float(v) for v in ko["min"]]
        kmax = [float(v) for v in ko["max"]]
    except (KeyError, TypeError, ValueError):
        errors.append("keepout.foot AABB is missing")
        return warnings, errors
    if len(kmin) != 3 or len(kmax) != 3 or any(a >= b for a, b in zip(kmin, kmax)):
        errors.append("keepout.foot AABB is degenerate (min >= max on some axis)")
    try:
        foot_l = float(walk_path(spec, "shoe.foot_length_mm")["value"])
        aabb_l = kmax[0] - kmin[0]
        if abs(aabb_l - foot_l) > 0.25:
            warnings.append(
                f"keepout.foot length {aabb_l:.2f} mm vs shoe.foot_length_mm={foot_l} "
                "(last CS: x along the foot, z up from the local sole)"
            )
    except (KeyError, TypeError, ValueError, IndexError):
        pass
    try:
        strap_t = float(walk_path(spec, "shoe.strap_thickness_mm")["value"])
        if strap_t + 1e-9 < MIN_FEATURE_MM:
            errors.append(f"shoe.strap_thickness_mm={strap_t} < {MIN_FEATURE_MM}")
    except (KeyError, TypeError, ValueError):
        pass
    warnings.extend(_fit_warnings(spec))
    return warnings, errors


def _ring_geometry_checks(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        ko = walk_path(spec, "keepout.bores")
    except KeyError:
        errors.append("keepout.bores is missing")
        return warnings, errors
    if not isinstance(ko, dict) or "confirmed" not in ko:
        errors.append("keepout.bores needs origin and confirmed")
        return warnings, errors
    try:
        from fabkit.ring_yoke import layout_from_spec

        lay = layout_from_spec(spec)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"ring layout: {exc}")
        return warnings, errors
    for label, mouth, bore in (
        ("rings.bar.mouth_mm", lay.bar_mouth, lay.bar_bore),
        ("rings.handle.mouth_mm", lay.handle_mouth, lay.handle_bore),
    ):
        if mouth + 1e-9 >= bore:
            errors.append(f"{label}={mouth} must stay under the bore {bore:.2f} mm")
        elif mouth < 8.0:
            errors.append(f"{label}={mouth} < 8 mm: not a snap mouth on a 0.4 nozzle")
    if lay.band + 1e-9 < 8.0:
        errors.append(f"rings.band_mm={lay.band} < 8 mm: grip band is too narrow to hold")
    if lay.bar_wall + 1e-9 < 1.2:
        errors.append(f"rings.bar.wall_mm={lay.bar_wall} < 1.2")
    if lay.handle_wall + 1e-9 < 1.2:
        errors.append(f"rings.handle.wall_mm={lay.handle_wall} < 1.2")
    warnings.extend(lay.warnings)
    warnings.extend(_fit_warnings(spec))
    return warnings, errors


def _strip_geometry_checks(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        ko = walk_path(spec, "keepout.pocket")
    except KeyError:
        errors.append("keepout.pocket is missing")
        return warnings, errors
    if not isinstance(ko, dict) or "confirmed" not in ko:
        errors.append("keepout.pocket needs origin and confirmed")
        return warnings, errors
    try:
        from fabkit.strip_clip import layout_from_spec

        lay = layout_from_spec(spec)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"strip-clip layout: {exc}")
        return warnings, errors
    if lay.inner_x + 1e-9 < 8.0 or lay.inner_z + 1e-9 < 8.0:
        errors.append(
            f"clip opening {lay.inner_x}×{lay.inner_z} mm is under 8 mm on an axis"
        )
    if lay.band + 1e-9 < 8.0:
        errors.append(f"clip.band_mm={lay.band} < 8 mm: the clip is too narrow to hold")
    if lay.tooth + 1e-9 < 2.0:
        errors.append(f"clip.tooth_mm={lay.tooth} < 2 mm: not a catch on a 0.4 nozzle")
    if lay.entrance <= 1.2:
        errors.append(
            f"two clip.tooth_mm={lay.tooth} close the {lay.inner_x} mm opening "
            f"(entrance {lay.entrance:.1f} mm)"
        )
    if lay.wall + 1e-9 < 1.2:
        errors.append(f"wall_mm={lay.wall} < 1.2")
    if lay.hole_d + 1e-9 < 1.2:
        errors.append(f"clip.hole_d_mm={lay.hole_d} < 1.2 mm")
    if lay.hole_d + 2.4 > lay.band + 1e-9:
        errors.append(
            f"clip.hole_d_mm={lay.hole_d} does not leave 1.2 mm of the {lay.band} mm band"
        )
    warnings.extend(lay.warnings)
    warnings.extend(_fit_warnings(spec))
    return warnings, errors


def _span_xy(spec: dict[str, Any]) -> tuple[float, float] | None:
    if spec.get("template_id") == DOLL_TEMPLATE:
        try:
            return (
                float(walk_path(spec, "shoe.foot_length_mm")["value"]),
                float(walk_path(spec, "shoe.foot_width_mm")["value"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    if spec.get("template_id") == RING_TEMPLATE:
        try:
            from fabkit.ring_yoke import layout_from_spec

            lay = layout_from_spec(spec)
            span_x = (
                lay.bar_bore / 2.0
                + lay.bar_wall
                + lay.x0
                + lay.handle_bore / 2.0
                + lay.handle_wall
            )
            span_y = lay.handle_bore + 2.0 * lay.handle_wall
            return span_x, span_y
        except (KeyError, TypeError, ValueError):
            return None
    if spec.get("template_id") == STRIP_TEMPLATE:
        try:
            from fabkit.strip_clip import layout_from_spec

            lay = layout_from_spec(spec)
            return lay.outer_x, lay.band
        except (KeyError, TypeError, ValueError):
            return None
    if spec.get("template_id") == TRAY_TEMPLATE:
        try:
            return (
                float(walk_path(spec, "tray.inner_l_mm")["value"]),
                float(walk_path(spec, "tray.inner_w_mm")["value"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    if spec.get("template_id") == SHELL_TEMPLATE:
        try:
            return (
                float(walk_path(spec, "device.length_mm")["value"]),
                float(walk_path(spec, "device.width_mm")["value"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    try:
        return (
            float(walk_path(spec, "board.length_mm")["value"]),
            float(walk_path(spec, "board.width_mm")["value"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _fit_warnings(spec: dict[str, Any]) -> list[str]:
    out: list[str] = []
    span_xy = _span_xy(spec)
    if span_xy is None:
        return out
    length, width = span_xy
    span = max(length, width)
    wall = spec.get("wall_mm")
    if wall is not None:
        wall_f = float(wall)
        if wall_f < 1.2:
            out.append(
                f"wall_mm={wall_f} < 1.2: {STATION_PRINTER} hardened {NOZZLE_MM} mm "
                "usually wants ≥3 perimeters (~1.2 mm)"
            )
        if span < 50 and wall_f > 2.4:
            out.append(
                f"wall_mm={wall_f} is thick for a {span:.0f} mm span; "
                "stiffer large boxes use ribs, not a 5 mm shell"
            )
    case = spec.get("case") or {}
    outer_l = case.get("outer_l_mm")
    inner_l = case.get("inner_l_mm")
    if outer_l is not None and inner_l is not None and wall is not None:
        computed = float(outer_l) - 2.0 * float(wall)
        if abs(computed - float(inner_l)) > 0.15:
            out.append(
                f"case.inner_l_mm={inner_l} is a brief note; "
                f"cavity length is outer-2*wall={computed:.1f} mm "
                "(template does not read inner_l_mm)"
            )
    vents = case.get("vents")
    if vents:
        template = spec.get("template_id") or "enclosure_box"
        faces = [str(f) for f in (vents.get("faces") or [])]
        face_set = set(faces)
        slot_w = float(vents.get("slot_w_mm") or SLOT_W_MM)
        if template != "enclosure_snap":
            out.append(
                "case.vents is set but this template does not cut vents yet; "
                "extend the committed template (no overlay) or the mesh stays sealed"
            )
        else:
            if "plus_x" in face_set:
                out.append(
                    "case.vents plus_x: USB window already occupies +X; "
                    "enclosure_snap skips extra +X vents"
                )
            if "floor" in face_set:
                out.append(
                    "case.vents floor: the base floor prints on the bed "
                    "(elephant foot / closed holes)"
                )
            if "lid" in face_set and not face_set & {"minus_x", "plus_y", "minus_y", "floor"}:
                out.append("case.vents lid only: chimney has no intake; add a low face")
            if face_set & {"plus_y", "minus_y"}:
                from fabkit.vent_catalog import KIND_GRID_45, resolve_kind

                if resolve_kind(vents) == KIND_GRID_45:
                    out.append(
                        "case.vents +/-Y: grid-45 parallel 45° slits in the face; "
                        "rim stays a loop (no 90° lintel)"
                    )
                else:
                    out.append(
                        "case.vents +/-Y: enclosure_snap cuts closed face slots "
                        "(45° shed lintel, rim stays a loop)"
                    )
            if vents.get("pattern") == "honeycomb" or vents.get("kind") == "honeycomb":
                out.append(
                    "kind/pattern honeycomb: enclosure_snap still cuts "
                    "rectangular windows (VENTS.md); do not expect hex cells"
                )
        if slot_w < 1.5:
            out.append(f"case.vents.slot_w_mm={slot_w} < 1.5: FDM slots usually close")
        if "lid" in face_set and slot_w + 1e-9 < 2.4:
            out.append(
                f"case.vents.slot_w_mm={slot_w} < 2.4: roof-on-bed through-slots "
                "narrower than ~6 lines often close in Studio even when CAD looks open"
            )
        ligament = vents.get("ligament_mm")
        if ligament is not None and float(ligament) < 2.0:
            out.append(
                f"case.vents.ligament_mm={ligament} < 2.0: bridges between "
                f"{STATION_PRINTER} 0.4 mm slots usually want >= 2 mm"
            )
    profile = spec.get("print_profile") or {}
    nozzle = profile.get("nozzle_mm")
    if nozzle is not None and abs(float(nozzle) - NOZZLE_MM) > 0.05:
        out.append(
            f"print_profile.nozzle_mm={nozzle}: station designs for {NOZZLE_MM} "
            f"hardened on {STATION_PRINTER}"
        )
    outer = _outer_xy_mm(spec)
    if outer is not None:
        outer_l, outer_w = outer
        single, two = print_pose_fits_bed(outer_l, outer_w)
        bed = f"{BUILD_MM[0]:.0f}×{BUILD_MM[1]:.0f}"
        if not single:
            out.append(
                f"outer {outer_l:.1f}×{outer_w:.1f} mm exceeds {STATION_PRINTER} bed {bed}"
            )
        elif not two:
            out.append(
                f"two print halves {outer_l:.1f}×{outer_w:.1f} may not sit side-by-side "
                f"on {STATION_PRINTER} {bed}; print one at a time"
            )
    return out


def _outer_xy_mm(spec: dict[str, Any]) -> tuple[float, float] | None:
    case = spec.get("case") or {}
    outer_l = case.get("outer_l_mm")
    outer_w = case.get("outer_w_mm")
    if outer_l is not None and outer_w is not None:
        return float(outer_l), float(outer_w)
    span_xy = _span_xy(spec)
    if span_xy is None:
        return None
    length, width = span_xy
    wall = spec.get("wall_mm")
    if spec.get("template_id") == DOLL_TEMPLATE:
        wall_f = float(wall) if wall is not None else 1.2
        gap = float(spec.get("gap_mm") if spec.get("gap_mm") is not None else 0.15)
        return length + 2.0 * gap + 2.0 * wall_f, width + 2.0 * gap + 2.0 * wall_f
    if spec.get("template_id") == RING_TEMPLATE:
        return span_xy
    if spec.get("template_id") == STRIP_TEMPLATE:
        return span_xy
    if spec.get("template_id") == SHELL_TEMPLATE:
        try:
            from fabkit.enclosure_shell import layout_from_spec

            lay = layout_from_spec(spec)
            return lay.outer_l, lay.outer_w
        except (KeyError, TypeError, ValueError):
            return None
    if spec.get("template_id") == TRAY_TEMPLATE:
        try:
            from fabkit.enclosure_tray import layout_from_spec as tray_layout

            lay = tray_layout(spec)
            return lay.outer_l, lay.outer_w
        except (KeyError, TypeError, ValueError):
            return None
    if spec.get("template_id") == MAGNET_BOX_TEMPLATE:
        try:
            from fabkit.enclosure_magnet_box import layout_from_spec as box_layout

            lay = box_layout(spec)
            return lay.outer_l, lay.outer_w
        except (KeyError, TypeError, ValueError):
            return None
    wall_f = float(wall) if wall is not None else wall_for_span(max(length, width))
    return length + 2.0 * wall_f, width + 2.0 * wall_f


def validate_schema(spec: dict[str, Any]) -> list[str]:
    errors = []
    for err in sorted(_spec_validator().iter_errors(spec), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in err.path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors


def validate_spec(spec: dict[str, Any], mode: str) -> GateResult:
    if mode not in {"preview", "print", "validate"}:
        return GateResult(False, [f"unknown mode {mode!r}"])
    errors = validate_schema(spec)
    unconfirmed = unconfirmed_fit_critical(spec)
    warnings: list[str] = []
    geo_w, geo_e = geometry_checks(spec, mode)
    warnings.extend(geo_w)
    errors.extend(geo_e)
    if unconfirmed:
        warnings.append(
            "unconfirmed fit-critical fields (measure before print): "
            + ", ".join(unconfirmed)
        )
    if mode == "print":
        family = spec.get("family")
        if family in PRINT_BLOCKED_FAMILIES:
            errors.append(
                f"print rejected: template enclosure_box does not cover family {family} "
                "(lens/LED/SD). Use preview or wait for a CAM template."
            )
        if unconfirmed:
            errors.append(
                "print rejected: fit-critical fields are not confirmed. "
                "Ask the operator to measure; do not invent millimetres. "
                f"Fields: {', '.join(unconfirmed)}"
            )
        return GateResult(ok=not errors, errors=errors, warnings=warnings, unconfirmed=unconfirmed)
    return GateResult(ok=not errors, errors=errors, warnings=warnings, unconfirmed=unconfirmed)


def load_spec(path: Path) -> dict[str, Any]:
    return load_yaml(path)
