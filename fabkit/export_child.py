"""CAD worker. Isolated so VTK/OCP heap teardown cannot fail the parent CLI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN", "1")


def main(argv: list[str]) -> None:
    if len(argv) != 5:
        print("usage: export_child.py SPEC MODE OUT_DIR RESULT_JSON", file=sys.stderr)
        os._exit(2)
    spec_path = Path(argv[1])
    mode = argv[2]
    out_dir = Path(argv[3])
    result_json = Path(argv[4])
    zone = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(zone))

    from fabkit.runtime import require_cpython_312

    require_cpython_312()

    from fabkit.build import build_parts
    from fabkit.kernel import export_shape
    from fabkit.validate import load_spec

    try:
        spec = load_spec(spec_path)
        if mode not in {"preview", "print"}:
            raise ValueError(f"unknown export mode {mode!r}")
        board = spec.get("board_id", "board")
        template = spec.get("template_id", "enclosure_box")
        stem = f"{board}-{template}"
        if mode == "preview":
            stem = f"PREVIEW-{stem}"
        parts = build_parts(spec)
        files: dict[str, str] = {}
        for suffix in (".stl", ".3mf", ".step"):
            dest = out_dir / f"{stem}{suffix}"
            export_shape(parts.printable, dest)
            files[suffix.lstrip(".")] = str(dest)
        if mode == "preview":
            from fabkit.render_png import render_previews

            button = spec.get("button") or {}
            button_face = (
                str(button.get("face"))
                if str(button.get("style") or "") == "flex_tab"
                else None
            )
            files.update(render_previews(parts, out_dir, stem, button_face=button_face))
        vents = (spec.get("case") or {}).get("vents") or {}
        payload = {
            "stem": stem,
            "files": files,
            "keepout_volume": parts.keepout_volume,
            "outer_mm": list(parts.outer),
            "usb_cut_wh_mm": list(parts.usb_cut_wh),
            "cavity_lw_mm": list(parts.cavity_lw),
            "vent_faces": list(vents.get("faces") or []),
            "warnings": list(getattr(parts, "warnings", None) or []),
        }
        payload.update(getattr(parts, "report", None) or {})
        result_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — worker must not raise into VTK teardown
        print(f"export_child: {exc}", file=sys.stderr)
        os._exit(1)
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv)
