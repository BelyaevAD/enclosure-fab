from __future__ import annotations

import json
from typing import Any

from fabkit.paths import LAST_GATE_PATH, WORK_DIR
from fabkit.validate import GateResult


def record(mode: str, spec_path: str, gate: GateResult, extra: dict[str, Any] | None = None) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": mode,
        "spec_path": spec_path,
        "ok": gate.ok,
        "errors": gate.errors,
        "warnings": gate.warnings,
        "unconfirmed": gate.unconfirmed,
        "extra": extra or {},
    }
    LAST_GATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read() -> dict[str, Any]:
    if not LAST_GATE_PATH.is_file():
        return {"ok": False, "errors": ["no gate recorded yet"]}
    return json.loads(LAST_GATE_PATH.read_text(encoding="utf-8"))
