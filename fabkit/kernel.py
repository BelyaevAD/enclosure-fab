from __future__ import annotations

from pathlib import Path

import cadquery as cq
from cadquery import exporters

from fabkit.paths import STL_ANGULAR_TOLERANCE, STL_TOLERANCE


def box_aabb(xmin: float, ymin: float, zmin: float, xmax: float, ymax: float, zmax: float) -> cq.Workplane:
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    if dx <= 0 or dy <= 0 or dz <= 0:
        raise ValueError(f"degenerate AABB {(xmin, ymin, zmin)}–{(xmax, ymax, zmax)}")
    return (
        cq.Workplane("XY")
        .box(dx, dy, dz)
        .translate((xmin + dx / 2.0, ymin + dy / 2.0, zmin + dz / 2.0))
    )


def intersect_volume(a: cq.Workplane, b: cq.Workplane) -> float:
    shape_a = a.val()
    shape_b = b.val()
    common = shape_a.intersect(shape_b)
    if common is None or common.isNull():
        return 0.0
    try:
        return float(common.Volume())
    except Exception as exc:
        raise RuntimeError(f"keep-out boolean failed: {exc}") from exc


def export_shape(shape: cq.Workplane, dest: Path) -> None:
    """Write STL/3MF/STEP. Mesh formats must get STL_TOLERANCE.

    CadQuery ``export()`` defaults to 0.1 mm deflection. Putting tolerance
    only in ``opt`` is ignored for STL. 3MF is written by ``threemf`` as
    one plate object per solid (no CadQuery component wrapper).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    solids = shape.solids()
    vals = solids.vals()
    if not vals:
        raise ValueError(f"export_shape: no solids for {dest.name}")
    suffix = dest.suffix.lower()
    if suffix == ".3mf":
        from fabkit.threemf import write_solids_3mf

        write_solids_3mf(
            vals,
            dest,
            tolerance=STL_TOLERANCE,
            angular_tolerance=STL_ANGULAR_TOLERANCE,
        )
        return
    kwargs = {
        "tolerance": STL_TOLERANCE,
        "angularTolerance": STL_ANGULAR_TOLERANCE,
    }
    if suffix == ".stl":
        exporters.export(
            solids,
            str(dest),
            **kwargs,
            opt={"ascii": False},
        )
        return
    exporters.export(solids, str(dest), **kwargs)
