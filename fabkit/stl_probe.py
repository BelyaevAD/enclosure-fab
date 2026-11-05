"""AABB, fill ratio, Z-slices and cavity hints from a binary/ASCII STL.

Does not load the mesh into CadQuery. For large sculpted STLs.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

HEADER = 80
TRI_BYTES = 50


def _load_binary(data: bytes) -> np.ndarray:
    n = struct.unpack_from("<I", data, HEADER)[0]
    expected = HEADER + 4 + n * TRI_BYTES
    if len(data) < expected:
        raise ValueError(f"truncated binary STL: {len(data)} < {expected} ({n} tris)")
    dt = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("ab", "<u2")])
    rec = np.frombuffer(data, dtype=dt, offset=HEADER + 4, count=n)
    return rec["v"].copy()


def _load_ascii(text: str) -> np.ndarray:
    verts: list[list[float]] = []
    tri: list[list[float]] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("vertex"):
            parts = s.split()
            tri.append([float(parts[1]), float(parts[2]), float(parts[3])])
            if len(tri) == 3:
                verts.append(tri)
                tri = []
    if not verts:
        raise ValueError("no ASCII vertices")
    return np.asarray(verts, dtype=np.float32)


def load_tris(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if data[:5].lower() == b"solid" and b"facet" in data[:4096].lower():
        try:
            return _load_ascii(data.decode("utf-8", errors="replace"))
        except ValueError:
            pass
    return _load_binary(data)


def signed_volume(tris: np.ndarray) -> float:
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    return float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0)


def _plane_segments(tris: np.ndarray, z: float) -> np.ndarray:
    zs = tris[:, :, 2]
    mask = (zs.min(axis=1) <= z) & (zs.max(axis=1) >= z)
    sub = tris[mask]
    if len(sub) == 0:
        return np.zeros((0, 2, 2), dtype=np.float64)
    i0 = np.array([0, 1, 2])
    i1 = np.array([1, 2, 0])
    p0 = sub[:, i0, :]
    p1 = sub[:, i1, :]
    z0 = p0[:, :, 2]
    z1 = p1[:, :, 2]
    dz = z1 - z0
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (z - z0) / dz
    valid = (np.abs(dz) > 1e-8) & (t >= 0.0) & (t <= 1.0)
    t3 = np.where(valid[..., None], t[..., None], 0.0)
    xy = p0[:, :, :2] + t3 * (p1[:, :, :2] - p0[:, :, :2])
    counts = valid.sum(axis=1)
    good = counts >= 2
    if not np.any(good):
        return np.zeros((0, 2, 2), dtype=np.float64)
    first = np.argmax(valid, axis=1)
    valid2 = valid.copy()
    valid2[np.arange(len(valid)), first] = False
    second = np.argmax(valid2, axis=1)
    rows = np.arange(len(xy))
    segs = np.stack([xy[rows, first], xy[rows, second]], axis=1)
    return segs[good].astype(np.float64, copy=False)


def _raster_segments(segs: np.ndarray, xmin, xmax, ymin, ymax, nx: int, ny: int) -> np.ndarray:
    grid = np.zeros((ny, nx), dtype=np.uint8)
    if segs.size == 0 or xmax <= xmin or ymax <= ymin:
        return grid
    sx = (nx - 1) / (xmax - xmin)
    sy = (ny - 1) / (ymax - ymin)
    for p0, p1 in segs:
        x0 = int(round((p0[0] - xmin) * sx))
        y0 = int(round((p0[1] - ymin) * sy))
        x1 = int(round((p1[0] - xmin) * sx))
        y1 = int(round((p1[1] - ymin) * sy))
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        xs = np.linspace(x0, x1, n + 1).astype(int)
        ys = np.linspace(y0, y1, n + 1).astype(int)
        ok = (xs >= 0) & (xs < nx) & (ys >= 0) & (ys < ny)
        grid[ys[ok], xs[ok]] = 1
    return grid


def _flood_from_border(walls: np.ndarray) -> np.ndarray:
    ny, nx = walls.shape
    outside = np.zeros_like(walls, dtype=bool)
    stack = []
    for x in range(nx):
        if walls[0, x] == 0:
            stack.append((0, x))
        if walls[ny - 1, x] == 0:
            stack.append((ny - 1, x))
    for y in range(ny):
        if walls[y, 0] == 0:
            stack.append((y, 0))
        if walls[y, nx - 1] == 0:
            stack.append((y, nx - 1))
    seen = np.zeros_like(walls, dtype=bool)
    while stack:
        y, x = stack.pop()
        if y < 0 or y >= ny or x < 0 or x >= nx or seen[y, x] or walls[y, x]:
            continue
        seen[y, x] = True
        outside[y, x] = True
        stack.extend(((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)))
    return outside


def _cavity_metrics(walls: np.ndarray, enclosed: np.ndarray, px_x: float, px_y: float) -> dict:
    if not np.any(enclosed):
        return {"cavity_aabb_px": None, "wall_est_mm": None, "cavity_span_mm": None}
    ys, xs = np.where(enclosed)
    aabb = {
        "x0": int(xs.min()),
        "x1": int(xs.max()),
        "y0": int(ys.min()),
        "y1": int(ys.max()),
        "nx": int(xs.max() - xs.min() + 1),
        "ny": int(ys.max() - ys.min() + 1),
    }
    wy, wx = np.where(walls == 1)
    if len(wx) == 0:
        return {"cavity_aabb_px": aabb, "wall_est_mm": None, "cavity_span_mm": None}
    sample = np.random.default_rng(0).choice(len(xs), size=min(80, len(xs)), replace=False)
    dpx = []
    for i in sample:
        d = np.hypot((xs[i] - wx) * px_x, (ys[i] - wy) * px_y).min()
        dpx.append(float(d))
    span_x = (xs.max() - xs.min() + 1) * px_x
    span_y = (ys.max() - ys.min() + 1) * px_y
    return {
        "cavity_aabb_px": aabb,
        "wall_est_mm": round(float(np.median(dpx)), 2) if dpx else None,
        "cavity_span_mm": [round(float(span_x), 2), round(float(span_y), 2)],
    }


def slice_report(tris: np.ndarray, z: float, xmin, xmax, ymin, ymax, nx: int = 96, ny: int = 64) -> dict:
    segs = _plane_segments(tris, z)
    pad = 0.4
    x0, x1, y0, y1 = xmin - pad, xmax + pad, ymin - pad, ymax + pad
    walls = _raster_segments(segs, x0, x1, y0, y1, nx, ny)
    outside = _flood_from_border(walls)
    enclosed_empty = (~outside) & (walls == 0)
    enclosed = int(enclosed_empty.sum())
    px_x = (x1 - x0) / max(nx - 1, 1)
    px_y = (y1 - y0) / max(ny - 1, 1)
    extra = _cavity_metrics(walls, enclosed_empty, px_x, px_y)
    return {
        "z_mm": round(float(z), 3),
        "segments": int(len(segs)),
        "wall_px": int((walls == 1).sum()),
        "enclosed_empty_px": enclosed,
        "has_cavity": enclosed >= 8,
        "cavity_frac_of_slice": round(float(enclosed) / float(nx * ny), 4),
        **extra,
    }


def x_profile(pts: np.ndarray, bins: int = 20) -> list[dict]:
    xmin, xmax = float(pts[:, 0].min()), float(pts[:, 0].max())
    edges = np.linspace(xmin, xmax, bins + 1)
    rows = []
    for i in range(bins):
        hi = edges[i + 1] if i < bins - 1 else edges[i + 1] + 1e-9
        m = (pts[:, 0] >= edges[i]) & (pts[:, 0] < hi)
        if not np.any(m):
            continue
        sl = pts[m]
        rows.append(
            {
                "x_mm": round(float(0.5 * (edges[i] + edges[i + 1])), 2),
                "y_span_mm": round(float(sl[:, 1].max() - sl[:, 1].min()), 2),
                "z_min_mm": round(float(sl[:, 2].min()), 2),
                "z_max_mm": round(float(sl[:, 2].max()), 2),
                "height_mm": round(float(sl[:, 2].max() - sl[:, 2].min()), 2),
            }
        )
    return rows


def y_clusters(pts: np.ndarray) -> dict:
    ys = pts[:, 1]
    span = float(ys.max() - ys.min())
    hist, _edges = np.histogram(ys, bins=24)
    mid = len(hist) // 2
    valley = int(hist[mid - 2 : mid + 3].min()) if span > 1 else 0
    peaks = (int(hist[:mid].max()), int(hist[mid:].max()))
    likely_pair = bool(span > 18.0 and valley < 0.35 * max(peaks) and min(peaks) > 0)
    return {
        "y_span_mm": round(span, 3),
        "likely_pair": likely_pair,
        "hist_peak_counts": peaks,
        "hist_mid_valley": valley,
    }


def probe(path: Path, *, verbose: bool = True) -> dict:
    if verbose:
        print(f"probe {path.name} ({path.stat().st_size} bytes)", file=sys.stderr)
    tris = load_tris(path)
    pts = tris.reshape(-1, 3)
    mn = pts.min(axis=0)
    mx = pts.max(axis=0)
    size = mx - mn
    vol = abs(signed_volume(tris))
    aabb_vol = float(np.prod(np.maximum(size, 1e-6)))
    zmin = float(mn[2])
    zs = [zmin + f * float(size[2]) for f in (0.18, 0.42, 0.68)]
    xmin, xmax = float(mn[0]), float(mx[0])
    ymin, ymax = float(mn[1]), float(mx[1])
    slices = [slice_report(tris, z, xmin, xmax, ymin, ymax) for z in zs]
    fill = vol / aabb_vol if aabb_vol else None
    any_cav = any(s["has_cavity"] for s in slices)
    # Outline-only slices treat a solid cross-section as a hole; trust fill first.
    if fill is not None and fill >= 0.45:
        kind = "mostly_solid"
    elif fill is not None and fill < 0.35 and any_cav:
        kind = "open_or_thin_shell_with_last_cavity"
    elif any_cav:
        kind = "has_enclosed_cavity"
    else:
        kind = "no_slice_cavity_detected"
    return {
        "path": str(path),
        "name": path.name,
        "bytes": path.stat().st_size,
        "triangles": int(len(tris)),
        "aabb_min_mm": [round(float(v), 3) for v in mn],
        "aabb_max_mm": [round(float(v), 3) for v in mx],
        "size_mm": [round(float(v), 3) for v in size],
        "signed_volume_abs_mm3": round(vol, 1),
        "aabb_volume_mm3": round(aabb_vol, 1),
        "fill_vs_aabb": round(fill, 4) if fill is not None else None,
        "kind": kind,
        "pair": y_clusters(pts),
        "slices": slices,
        "x_profile": x_profile(pts),
    }


def write_cube_stl(path: Path, size_mm: float = 10.0) -> None:
    """Axis-aligned cube [0, size]^3 as a binary STL (tests)."""
    s = float(size_mm)
    faces = (
        ((0, 0, 0), (s, 0, 0), (s, s, 0)),
        ((0, 0, 0), (s, s, 0), (0, s, 0)),
        ((0, 0, s), (s, s, s), (s, 0, s)),
        ((0, 0, s), (0, s, s), (s, s, s)),
        ((0, 0, 0), (0, 0, s), (s, 0, s)),
        ((0, 0, 0), (s, 0, s), (s, 0, 0)),
        ((0, s, 0), (s, s, 0), (s, s, s)),
        ((0, s, 0), (s, s, s), (0, s, s)),
        ((0, 0, 0), (0, s, 0), (0, s, s)),
        ((0, 0, 0), (0, s, s), (0, 0, s)),
        ((s, 0, 0), (s, 0, s), (s, s, s)),
        ((s, 0, 0), (s, s, s), (s, s, 0)),
    )
    rec = np.zeros(
        12,
        dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("ab", "<u2")]),
    )
    rec["v"] = np.asarray(faces, dtype=np.float32)
    path.write_bytes(b"\0" * HEADER + struct.pack("<I", 12) + rec.tobytes())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="probe_stl")
    p.add_argument("stl", nargs="+", type=Path)
    p.add_argument("-o", "--out", type=Path, help="write JSON here as well as stdout")
    args = p.parse_args(argv)
    out = []
    for path in args.stl:
        if not path.is_file():
            print(f"missing: {path}", file=sys.stderr)
            return 1
        out.append(probe(path.resolve()))
    payload = out if len(out) > 1 else out[0]
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return 0
