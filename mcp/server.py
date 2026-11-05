#!/usr/bin/env python3
"""stdio MCP for the enclosure wrapper. Logs to stderr only."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

ZONE = Path(__file__).resolve().parents[1]
if str(ZONE) not in sys.path:
    sys.path.insert(0, str(ZONE))

from fabkit.runtime import require_cpython_312  # noqa: E402

require_cpython_312()

from mcp.server.mcpserver import MCPServer  # noqa: E402

from fabkit.generate import generate  # noqa: E402
from fabkit.freshness import freshness_report  # noqa: E402
from fabkit.last_gate import read as read_gate, record  # noqa: E402
from fabkit.primitives import list_primitives  # noqa: E402
from fabkit.protocol import list_boards, list_templates, protocol, resolve_spec_path  # noqa: E402
from fabkit.validate import GateError, load_spec, validate_spec  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
server = MCPServer("fab")

_TOOL_ERRORS = (GateError, FileNotFoundError, KeyError, OSError, ValueError)
_PROCESS_STARTED = time.time()
_STALE_HINT = (
    " If this spec exists on disk, Reload MCP — this chat's fab process "
    "does not load fabkit until then. CLI: "
    "python scripts/fab.py preview <spec.yaml>."
)
_NON_PCB_TEMPLATES = frozenset(
    {"enclosure_tray", "enclosure_shell", "enclosure_magnet_box", "doll_mary_jane", "ring_yoke", "strip_clip"}
)


def _resolve_spec(spec_path: str) -> Path:
    return resolve_spec_path(spec_path)


def _fabkit_disk_newer() -> bool:
    root = ZONE / "fabkit"
    try:
        return any(path.stat().st_mtime > _PROCESS_STARTED for path in root.glob("*.py"))
    except OSError:
        return False


def _pcb_fields_on_non_pcb(spec: dict, unconfirmed: list[str]) -> bool:
    if spec.get("template_id") not in _NON_PCB_TEMPLATES:
        return False
    return any(
        item.startswith("board.")
        or item.startswith("usb.")
        or item.startswith("keepout.board")
        for item in unconfirmed
    )


def _stale_process_warnings(spec: dict | None = None, unconfirmed: list[str] | None = None) -> list[str]:
    extra: list[str] = []
    if _fabkit_disk_newer():
        extra.append(
            "fabkit/*.py on disk is newer than this MCP process — Reload MCP; "
            "trust CLI fab.py until then"
        )
    if spec is not None and unconfirmed is not None and _pcb_fields_on_non_pcb(spec, unconfirmed):
        extra.append(
            "non-PCB template listed board.*/usb.*/keepout.board — stale fab "
            "process, Reload MCP; trust CLI fab.py validate / preview"
        )
    return extra


def _error_text(exc: BaseException, *, preview: bool = False) -> str:
    prefix = "NOT_FOR_PRINT\n" if preview else ""
    extra = _STALE_HINT if isinstance(exc, FileNotFoundError) else ""
    return f"{prefix}ERROR: {exc}{extra}"


@server.tool(name="list_templates")
def list_templates_tool() -> str:
    """List committed enclosure templates."""
    return "\n".join(list_templates())


@server.tool(name="list_boards")
def list_boards_tool() -> str:
    """List library stubs and project specs; report unconfirmed fit-critical fields."""
    return json.dumps(list_boards(), indent=2)


@server.tool(name="list_primitives")
def list_primitives_tool() -> str:
    """Named enclosure parts (buttons, vents, wells) and upstream recipe pins. Live CAD is fabkit, not a vendored OpenSCAD repo."""
    return json.dumps(list_primitives(), indent=2, ensure_ascii=False)


@server.tool(name="measurement_protocol")
def measurement_protocol(family: str = "") -> str:
    """Required measurement fields and coordinate system for a board family."""
    try:
        return json.dumps(protocol(family or None), indent=2, ensure_ascii=False)
    except _TOOL_ERRORS as exc:
        return _error_text(exc)


@server.tool(name="validate_spec")
def validate_spec_tool(spec_path: str) -> str:
    """Validate a spec YAML without building CAD. Tray/shell listing board.* means Reload MCP."""
    try:
        path = _resolve_spec(spec_path)
        spec = load_spec(path)
        gate = validate_spec(spec, "validate")
        record("validate", str(path), gate)
    except _TOOL_ERRORS as exc:
        return _error_text(exc)
    warnings = list(gate.warnings) + _stale_process_warnings(spec, gate.unconfirmed)
    return json.dumps(
        {
            "ok": gate.ok,
            "errors": gate.errors,
            "warnings": warnings,
            "unconfirmed": gate.unconfirmed,
        },
        indent=2,
    )


@server.tool(name="generate_preview")
def generate_preview(spec_path: str) -> str:
    """Build a PREVIEW model and PNG stills. Allowed with unconfirmed millimetres. NOT_FOR_PRINT."""
    try:
        result = generate(_resolve_spec(spec_path), "preview")
    except _TOOL_ERRORS as exc:
        return _error_text(exc, preview=True)
    banner = result.get("banner", "NOT_FOR_PRINT")
    stale = _stale_process_warnings()
    extra = ("\n" + "\n".join(stale)) if stale else ""
    return banner + extra + "\n" + freshness_report(result) + "\n" + json.dumps(result, indent=2)


@server.tool(name="generate_print")
def generate_print(spec_path: str) -> str:
    """Build a printable model. Fails if any fit-critical field is unconfirmed or keep-out intersects."""
    try:
        result = generate(_resolve_spec(spec_path), "print")
    except _TOOL_ERRORS as exc:
        return _error_text(exc)
    return json.dumps(result, indent=2)


@server.tool(name="explain_last_gate")
def explain_last_gate() -> str:
    """Explain the last validate/generate gate (errors, unconfirmed fields)."""
    return json.dumps(read_gate(), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    server.run()
