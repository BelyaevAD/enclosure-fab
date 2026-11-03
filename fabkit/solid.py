"""Boolean helpers so enclosure solids stay one manifold volume.

Kissing coplanar faces (union at a shared plane, or a cutter flush with a face)
leave leftover edges inside the part. OCCT then tessellates them as stacked
faces. Fuse with a real volume overlap + a small fuzzy tolerance; cut with the
same tolerance; sink add-on features into the parent.
"""

from __future__ import annotations

import cadquery as cq

# Absorbs near-coplanar slivers; well below the 0.4 mm nozzle / 0.42 line.
FUSE_TOL_MM = 0.02
# How far a rib / bead / post enters the parent so the union is not a kiss.
PENETRATE_MM = 0.15


def face_count(wp: cq.Workplane) -> int:
    return sum(len(solid.Faces()) for solid in wp.solids().vals())


def edge_count(wp: cq.Workplane) -> int:
    return sum(len(solid.Edges()) for solid in wp.solids().vals())


def is_one_valid_solid(wp: cq.Workplane) -> bool:
    solids = wp.solids().vals()
    return len(solids) == 1 and bool(solids[0].isValid())


def fuse(a: cq.Workplane, b: cq.Workplane) -> cq.Workplane:
    return a.union(b, clean=True, tol=FUSE_TOL_MM)


def intersect(a: cq.Workplane, b: cq.Workplane) -> cq.Workplane | None:
    try:
        hit = a.intersect(b, clean=True, tol=FUSE_TOL_MM)
    except Exception:
        return None
    if not hit.solids().vals():
        return None
    return hit


def combine_disjoint(first: cq.Workplane, *rest: cq.Workplane) -> cq.Workplane:
    out = first
    for other in rest:
        out = out.union(other, clean=True, glue=True, tol=FUSE_TOL_MM)
    return out


def cut_through(solid: cq.Workplane, tool: cq.Workplane) -> cq.Workplane:
    return solid.cut(tool, clean=True, tol=FUSE_TOL_MM)


def cut_all(solid: cq.Workplane, tools: list[cq.Workplane]) -> cq.Workplane:
    """Subtract each tool in order.

    Do not glue many window prisms into one compound and cut once — OCCT
    leaves the cutter's faces inside the holes (Studio Repair then deletes
    them). Sequential cuts keep one manifold solid. Overlapping tools in
    the same list are allowed (roof well + bed flare).
    """
    out = solid
    for tool in tools:
        out = cut_through(out, tool)
    return out
