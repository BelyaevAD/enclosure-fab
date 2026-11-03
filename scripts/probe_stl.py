#!/usr/bin/env python3
"""CLI: extract AABB / fill / cavity slices from an STL without CadQuery."""

from __future__ import annotations

import sys
from pathlib import Path

ZONE = Path(__file__).resolve().parents[1]
if str(ZONE) not in sys.path:
    sys.path.insert(0, str(ZONE))

from fabkit.stl_probe import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
