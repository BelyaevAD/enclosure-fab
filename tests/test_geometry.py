"""Geometry snapshots, mesh checks, and the preview/print gates on the fixtures.

Refresh the snapshot after an intended geometry change:
FAB_UPDATE_GOLDEN=1 python -m pytest tests/test_geometry.py
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import cadquery as cq
import numpy as np
import pytest
import yaml

from fabkit.build import build_parts
from fabkit.generate import generate
from fabkit.paths import FIXTURES_DIR
from fabkit.stl_probe import load_tris
from fabkit.validate import GateError, load_spec

GOLDEN_PATH = Path(__file__).with_name("golden.json")
FIXTURES = sorted(path.stem for path in FIXTURES_DIR.glob("*.yaml"))
SOLIDS = ("base", "lid", "assembled", "printable")
VOLUME_REL = 1e-4
SIZE_MM = 0.01
UPDATE = os.environ.get("FAB_UPDATE_GOLDEN") == "1"


def _shape_facts(workplane: cq.Workplane | None) -> dict | None:
    shapes = [value for value in (workplane.vals() if workplane is not None else []) if isinstance(value, cq.Shape)]
    if not shapes:
        return None
    compound = cq.Compound.makeCompound(shapes)
    box = compound.BoundingBox()
    return {
        "solids": len(compound.Solids()),
        "volume": round(sum(shape.Volume() for shape in shapes), 3),
        "size": [round(box.xlen, 3), round(box.ylen, 3), round(box.zlen, 3)],
    }


def _metrics(name: str) -> dict:
    parts = build_parts(load_spec(FIXTURES_DIR / f"{name}.yaml"))
    facts = {label: _shape_facts(getattr(parts, label)) for label in SOLIDS}
    facts = {label: value for label, value in facts.items() if value is not None}
    facts["keepout_volume"] = round(parts.keepout_volume, 4)
    return facts


def _open_edges(tris: np.ndarray) -> int:
    """Edges not shared by exactly two triangles. Zero means a closed mesh."""
    _, index = np.unique(np.round(tris.reshape(-1, 3), 5), axis=0, return_inverse=True)
    faces = index.reshape(-1, 3)
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return int((counts != 2).sum())


def _objects_in_3mf(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        model = archive.read("3D/3dmodel.model").decode("utf-8")
    return model.count("<object ")


@pytest.fixture(scope="module")
def golden() -> dict:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8")) if GOLDEN_PATH.is_file() else {}
    yield data
    if UPDATE:
        GOLDEN_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_matches_snapshot(name: str, golden: dict) -> None:
    actual = _metrics(name)
    if UPDATE:
        golden[name] = actual
        return
    assert name in golden, f"no snapshot for {name}; run with FAB_UPDATE_GOLDEN=1"
    expected = golden[name]
    assert sorted(actual) == sorted(expected), name
    assert actual["keepout_volume"] == pytest.approx(expected["keepout_volume"], abs=1e-3), name
    for label in SOLIDS:
        if label not in expected:
            continue
        got, want = actual[label], expected[label]
        assert got["solids"] == want["solids"], (name, label)
        assert got["volume"] == pytest.approx(want["volume"], rel=VOLUME_REL), (name, label)
        assert got["size"] == pytest.approx(want["size"], abs=SIZE_MM), (name, label)


def test_preview_files_are_marked_and_closed(tmp_path: Path) -> None:
    result = generate(FIXTURES_DIR / "demo_round.yaml", "preview", tmp_path)
    assert result["banner"] == "NOT_FOR_PRINT"
    written = [path for path in tmp_path.iterdir() if path.suffix in {".3mf", ".stl", ".step"}]
    assert len(written) == 3
    assert all(path.name.startswith("PREVIEW-") for path in written)
    stl = next(path for path in written if path.suffix == ".stl")
    assert _open_edges(load_tris(stl)) == 0
    three_mf = next(path for path in written if path.suffix == ".3mf")
    printable = build_parts(load_spec(FIXTURES_DIR / "demo_round.yaml")).printable
    assert _objects_in_3mf(three_mf) == len(printable.val().Solids())


def test_print_without_confirmed_fields_writes_nothing(tmp_path: Path) -> None:
    with pytest.raises(GateError, match="not confirmed"):
        generate(FIXTURES_DIR / "demo_ring_yoke.yaml", "print", tmp_path)
    assert not any(tmp_path.glob("*.3mf"))


def test_print_of_confirmed_fixture_is_not_marked(tmp_path: Path) -> None:
    result = generate(FIXTURES_DIR / "demo_snap.yaml", "print", tmp_path)
    assert "banner" not in result
    meshes = list(tmp_path.glob("*.3mf"))
    assert len(meshes) == 1
    assert not meshes[0].name.startswith("PREVIEW-")


def test_keepout_hit_removes_print_files(tmp_path: Path) -> None:
    spec = load_spec(FIXTURES_DIR / "demo_snap.yaml")
    spec["keepout"]["board"]["max"] = [24.0, 17.0, 5.0]  # reaches the +Y board rib
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(GateError, match="keep-out"):
        generate(spec_path, "print", out)
    assert not any(out.glob("*.3mf"))
