from __future__ import annotations

from typing import Any

from fabkit.doll_mary_jane import build_parts as build_doll
from fabkit.enclosure_box import EnclosureBuild, build_parts as build_box
from fabkit.ring_yoke import build_parts as build_ring_yoke
from fabkit.strip_clip import build_parts as build_strip_clip
from fabkit.enclosure_snap import build_parts as build_snap
from fabkit.enclosure_shell import build_parts as build_shell
from fabkit.enclosure_magnet_box import build_parts as build_magnet_box
from fabkit.enclosure_round import build_parts as build_round
from fabkit.enclosure_tray import build_parts as build_tray

TEMPLATES = {
    "enclosure_box": build_box,
    "enclosure_snap": build_snap,
    "enclosure_shell": build_shell,
    "enclosure_tray": build_tray,
    "enclosure_magnet_box": build_magnet_box,
    "enclosure_round": build_round,
    "doll_mary_jane": build_doll,
    "ring_yoke": build_ring_yoke,
    "strip_clip": build_strip_clip,
}


def build_parts(spec: dict[str, Any]) -> EnclosureBuild:
    template = spec.get("template_id")
    builder = TEMPLATES.get(template)
    if builder is None:
        known = ", ".join(sorted(TEMPLATES))
        raise ValueError(f"unknown template {template!r}; known: {known}")
    return builder(spec)
