"""Fixture checks for the public tree. Personal project specs are not in this repo."""

from __future__ import annotations

import math

from fabkit.paths import FIXTURES_DIR, LIBRARY_DIR
from fabkit.protocol import list_templates
from fabkit.validate import load_spec, validate_spec

FIXTURES = sorted(path.name for path in FIXTURES_DIR.glob("*.yaml"))


def test_fixtures_preview_ok() -> None:
    for name in FIXTURES:
        gate = validate_spec(load_spec(FIXTURES_DIR / name), "preview")
        assert gate.ok, (name, gate.errors)


def test_wemos_stub_print_blocked() -> None:
    gate = validate_spec(load_spec(LIBRARY_DIR / "wemos.yaml"), "print")
    assert not gate.ok


def test_every_template_has_a_fixture() -> None:
    used = {load_spec(FIXTURES_DIR / name)["template_id"] for name in FIXTURES}
    assert set(list_templates()) == used


def test_round_lid_has_vents() -> None:
    from fabkit.enclosure_round import build_parts

    spec = load_spec(FIXTURES_DIR / "demo_round.yaml")
    parts = build_parts(spec)
    solid = math.pi * 20.0 * 20.0 * 2.0
    assert parts.lid.val().Volume() < solid - 20
    box = parts.base.val().BoundingBox()
    assert abs((box.xmax - box.xmin) - (box.ymax - box.ymin)) < 0.05
    assert parts.report["vent_n"] == 6
