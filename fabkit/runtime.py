"""Interpreter pin for the CadQuery kernel."""

from __future__ import annotations

import sys

REQUIRED = (3, 12)


def require_cpython_312() -> None:
    if sys.version_info[:2] != REQUIRED:
        raise SystemExit(
            "enclosure-fab requires CPython 3.12 (CadQuery/OCP wheels). "
            f"This interpreter is {sys.version.split()[0]}. "
            "Use `py -3.12`."
        )
