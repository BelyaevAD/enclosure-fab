from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from fabkit.freshness import (
    file_facts,
    missing_or_stale,
    stale_live_previews,
    utc_stamp,
)
from fabkit.last_gate import record
from fabkit.paths import default_generated_dir, project_dir_for_spec
from fabkit.readme_preview import upsert_readme_preview
from fabkit.validate import GateError, GateResult, load_spec, validate_spec

MESH_SUFFIXES = (".stl", ".3mf", ".step")
PNG_SUFFIXES = ("-assembled.png", "-print.png")
LIVE_PREVIEW_KEYS = ("preview_png", "preview_print_png", "readme")


def _stem(spec: dict[str, Any], mode: str) -> str:
    board = spec.get("board_id", "board")
    template = spec.get("template_id", "enclosure_box")
    name = f"{board}-{template}"
    if mode == "preview":
        return f"PREVIEW-{name}"
    return name


def _belongs_to_stem(name: str, stem: str) -> bool:
    return name.startswith(f"{stem}.") or name.startswith(f"{stem}-")


def _unlink_stem(dest: Path, stem: str) -> None:
    for suffix in (*MESH_SUFFIXES, ".result.json", *PNG_SUFFIXES):
        (dest / f"{stem}{suffix}").unlink(missing_ok=True)


def reset_generated_dir(dest: Path, stem: str | None = None) -> None:
    """Drop leftover files. If stem is set, keep that stem (last good survives a failed child)."""
    if not dest.is_dir():
        return
    for path in dest.iterdir():
        if not path.is_file():
            continue
        if stem and _belongs_to_stem(path.name, stem):
            continue
        path.unlink()


def _dest_is_under(dest: Path, parent: Path) -> bool:
    try:
        dest.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def should_publish_stills(mode: str, dest: Path, project: Path | None) -> bool:
    return mode == "preview" and project is not None and _dest_is_under(dest, project)


def _publish_project_stills(
    project: Path,
    files: dict[str, str],
    *,
    stem: str = "",
) -> dict[str, str]:
    published: dict[str, str] = {}
    assembled = files.get("png_assembled")
    printed = files.get("png_print")
    button = files.get("png_button")
    if assembled and Path(assembled).is_file():
        hero = project / "preview.png"
        shutil.copy2(assembled, hero)
        published["preview_png"] = str(hero)
    if printed and Path(printed).is_file():
        hero_print = project / "preview-print.png"
        shutil.copy2(printed, hero_print)
        published["preview_print_png"] = str(hero_print)
    if button and Path(button).is_file():
        hero_button = project / "preview-button.png"
        shutil.copy2(button, hero_button)
        published["preview_button_png"] = str(hero_button)
    readme = project / "README.md"
    if (
        "preview_png" in published
        and "preview_print_png" in published
        and readme.is_file()
    ):
        upsert_readme_preview(
            readme, stem=stem, button="preview_button_png" in published
        )
        published["readme"] = str(readme)
    return published


def generate(spec_path: Path, mode: str, out_dir: Path | None = None) -> dict[str, Any]:
    spec_path = spec_path.resolve()
    spec = load_spec(spec_path)
    gate = validate_spec(spec, mode)
    extra: dict[str, Any] = {}
    if not gate.ok:
        record(mode, str(spec_path), gate)
        raise GateError("\n".join(gate.errors))

    dest = out_dir or default_generated_dir(spec_path, mode)
    dest.mkdir(parents=True, exist_ok=True)
    stem = _stem(spec, mode)
    result_json = dest / f"{stem}.result.json"
    reset_generated_dir(dest, stem)
    # Do not treat a previous run's JSON as this child's result (ADR 047 p.10).
    result_json.unlink(missing_ok=True)
    t0 = time.time()

    child = Path(__file__).resolve().parent / "export_child.py"
    cmd = [
        sys.executable,
        str(child),
        str(spec_path),
        mode,
        str(dest),
        str(result_json),
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env.setdefault("VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN", "1")
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    extra["exit"] = proc.returncode
    if not result_json.is_file():
        extra["stderr"] = (proc.stderr or "")[-2000:]
        fail = GateResult(
            False,
            [f"CAD export failed (exit {proc.returncode})"],
            gate.warnings,
            gate.unconfirmed,
        )
        record(mode, str(spec_path), fail, extra)
        raise GateError(fail.errors[0] + "\n" + extra["stderr"])

    payload = json.loads(result_json.read_text(encoding="utf-8"))
    files = payload.get("files") or {}
    leftover = missing_or_stale(files, t0)
    if leftover or not files:
        extra["stderr"] = (proc.stderr or "")[-2000:]
        msg = (
            "generated files were not written this run (stale leftover): "
            + (", ".join(leftover) if leftover else "files missing")
        )
        fail = GateResult(False, [msg], gate.warnings, gate.unconfirmed)
        record(mode, str(spec_path), fail, extra)
        raise GateError(msg)
    if proc.returncode != 0:
        note = (
            f"export_child exit {proc.returncode} after a this-run write "
            "(Windows VTK/OCP teardown); meshes are new"
        )
        if note not in gate.warnings:
            gate.warnings.append(note)

    generated_at = utc_stamp()
    payload["generated_at"] = generated_at
    payload["files_written"] = file_facts(files)
    result_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    extra.update(payload)
    siblings = stale_live_previews(exclude=spec_path)
    extra["stale_siblings"] = [row["id"] for row in siblings]
    extra["stale_sibling_detail"] = siblings
    if siblings:
        listed = ", ".join(row["id"] for row in siblings)
        gate.warnings.append(
            "live preview older than fabkit (preview these): " + listed
        )
    for warning in extra.pop("warnings", []) or []:
        if warning not in gate.warnings:
            gate.warnings.append(str(warning))
    reset_generated_dir(dest, stem)
    project = project_dir_for_spec(spec_path)
    if project is not None:
        extra["project"] = str(project)
        if should_publish_stills(mode, dest, project):
            published = _publish_project_stills(
                project,
                payload.get("files") or {},
                stem=stem,
            )
            extra.update(published)
            missing = [key for key in LIVE_PREVIEW_KEYS if key not in published]
            if missing:
                msg = (
                    "preview stills/README were not written next to spec: "
                    + ", ".join(missing)
                )
                fail = GateResult(False, [msg], gate.warnings, gate.unconfirmed)
                record(mode, str(spec_path), fail, extra)
                raise GateError(msg)
    if payload.get("keepout_volume", 0) > 1e-6:
        msg = f"keep-out intersection volume {payload['keepout_volume']:.4f} mm^3 on assembled solid"
        if mode == "print":
            _unlink_stem(dest, stem)
            extra["files"] = {}
            fail = GateResult(False, [msg], gate.warnings, gate.unconfirmed)
            record(mode, str(spec_path), fail, extra)
            raise GateError(msg)
        gate.warnings.append(msg)
    if spec.get("template_id") == "enclosure_snap":
        plus_vol = float(payload.get("snap_engage_plus_volume_mm3") or 0.0)
        minus_vol = float(payload.get("snap_engage_minus_volume_mm3") or 0.0)
        if plus_vol <= 1e-6 or minus_vol <= 1e-6:
            msg = (
                "snap bead does not sit in the groove (assembled): "
                f"+Y {plus_vol:.4f} mm^3 / -Y {minus_vol:.4f} mm^3"
            )
            if mode == "print":
                _unlink_stem(dest, stem)
                extra["files"] = {}
                fail = GateResult(False, [msg], gate.warnings, gate.unconfirmed)
                record(mode, str(spec_path), fail, extra)
                raise GateError(msg)
            if msg not in gate.warnings:
                gate.warnings.append(msg)
    if mode == "preview":
        extra["banner"] = "NOT_FOR_PRINT"
    record(mode, str(spec_path), gate, extra)
    extra["warnings"] = gate.warnings
    extra["unconfirmed"] = gate.unconfirmed
    extra["mode"] = mode
    extra["ok"] = True
    return extra


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
