"""Fixture checks for the public tree. Personal project specs are not in this repo."""

from __future__ import annotations

import math

from fabkit.paths import FIXTURES_DIR, LIBRARY_DIR
from fabkit.protocol import list_templates
from fabkit.validate import load_spec, validate_spec

FIXTURES = (
    "demo_rect.yaml",
    "demo_shell.yaml",
    "demo_tray.yaml",
    "demo_round.yaml",
)


def test_fixtures_preview_ok() -> None:
    for name in FIXTURES:
        gate = validate_spec(load_spec(FIXTURES_DIR / name), "preview")
        assert gate.ok, (name, gate.errors)


def test_wemos_stub_print_blocked() -> None:
    gate = validate_spec(load_spec(LIBRARY_DIR / "wemos.yaml"), "print")
    assert not gate.ok


def test_templates_listed() -> None:
    names = list_templates()
    assert "enclosure_box" in names
    assert "enclosure_round" in names


def test_round_lid_has_vents() -> None:
    from fabkit.enclosure_round import build_parts

    spec = load_spec(FIXTURES_DIR / "demo_round.yaml")
    parts = build_parts(spec)
    solid = math.pi * 20.0 * 20.0 * 2.0
    assert parts.lid.val().Volume() < solid - 20
    box = parts.base.val().BoundingBox()
    assert abs((box.xmax - box.xmin) - (box.ymax - box.ymin)) < 0.05
    assert parts.report["vent_n"] == 6
