"""Off-screen studio PNGs of the parts with VTK. Call only from export_child.

Smooth-shaded faces, crease and silhouette lines instead of the triangle mesh,
soft studio lights with ambient occlusion, a quiet background, and one colour
per printed part. Rendered at twice the size and scaled down for clean lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import vtkmodules.vtkRenderingOpenGL2  # noqa: F401  registers the OpenGL backend
from cadquery import Shape, Workplane
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkFiltersCore import vtkCleanPolyData, vtkFeatureEdges, vtkPolyDataNormals
from vtkmodules.vtkFiltersHybrid import vtkPolyDataSilhouette
from vtkmodules.vtkImagingCore import vtkImageResize
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkLightKit,
    vtkMapper,
    vtkPolyDataMapper,
    vtkRenderer,
    vtkRenderWindow,
    vtkWindowToImageFilter,
)

from fabkit.enclosure_box import EnclosureBuild

_SIZE = (960, 720)
_SUPERSAMPLE = 2
_TOLERANCE = 1e-3
_ANGULAR_TOLERANCE = 0.1
_CREASE_DEG = 35.0


@dataclass(frozen=True)
class Style:
    parts: tuple[tuple[float, float, float], ...]
    background_top: tuple[float, float, float]
    background_bottom: tuple[float, float, float]
    line_shade: float  # crease colour = part colour × this
    line_width: float  # at output size
    key_intensity: float = 0.9
    key_to_fill: float = 3.0  # higher = more contrast between faces
    ambient_occlusion: bool = True


STUDIO = Style(
    # sage, sand, mist blue, clay: soft and distinct when two parts lie side by side
    parts=((0.62, 0.79, 0.73), (0.90, 0.83, 0.69), (0.68, 0.77, 0.89), (0.91, 0.74, 0.68)),
    background_top=(0.985, 0.988, 0.986),
    background_bottom=(0.925, 0.937, 0.932),
    line_shade=0.38,
    line_width=1.1,
)


def render_previews(
    parts: EnclosureBuild,
    dest_dir: Path,
    stem: str,
    *,
    button_face: str | None = None,
) -> dict[str, str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    assembled_png = dest_dir / f"{stem}-assembled.png"
    print_png = dest_dir / f"{stem}-print.png"
    _shot(parts.assembled, assembled_png, camera=_camera_from_plus_x(parts.assembled))
    _shot(
        parts.printable,
        print_png,
        camera=dict(roll=-25.0, elevation=-35.0, azimuth=15.0, zoom=1.28),
    )
    files = {"png_assembled": str(assembled_png), "png_print": str(print_png)}
    if button_face:
        button_png = dest_dir / f"{stem}-button.png"
        _shot(
            parts.assembled,
            button_png,
            camera=_camera_from_face(parts.assembled, button_face),
        )
        files["png_button"] = str(button_png)
    return files


def _look_at(
    wp: Workplane,
    dx: float,
    dy: float,
    dz: float,
    *,
    zoom: float = 1.12,
    fx: float = 0.5,
    fy: float = 0.5,
    fz: float = 0.5,
) -> dict[str, Any]:
    bb = wp.val().BoundingBox()
    cx = bb.xmin + fx * (bb.xmax - bb.xmin)
    cy = bb.ymin + fy * (bb.ymax - bb.ymin)
    cz = bb.zmin + fz * (bb.zmax - bb.zmin)
    span = max(bb.xlen, bb.ylen, bb.zlen, 1.0)
    dist = span * 2.35
    return {
        "position": (cx + dist * dx, cy + dist * dy, cz + dist * dz),
        "focus": (cx, cy, cz),
        "viewup": (0.0, 0.0, 1.0),
        "zoom": zoom,
    }


def _camera_from_plus_x(wp: Workplane) -> dict[str, Any]:
    """Look from +X/+Y/+Z so the USB wall (+X) and lid (+Z) are both readable."""
    return _look_at(wp, 0.98, 0.70, 0.55, zoom=1.3)


def _camera_from_face(wp: Workplane, face: str) -> dict[str, Any]:
    """Hero the flex-tab wall. USB ISO hides −Y."""
    if face == "minus_y":
        return _look_at(wp, 0.16, -1.0, 0.10, zoom=2.12, fx=0.80, fy=0.02, fz=0.46)
    if face == "plus_y":
        return _look_at(wp, 0.16, 1.0, 0.10, zoom=2.12, fx=0.80, fy=0.98, fz=0.46)
    if face == "minus_x":
        return _look_at(wp, -1.0, 0.16, 0.10, zoom=2.12, fx=0.02, fy=0.45, fz=0.46)
    return _look_at(wp, 0.98, 0.70, 0.55, zoom=1.08)


def _solids(wp: Workplane) -> list[Shape]:
    out: list[Shape] = []
    for value in wp.vals():
        if isinstance(value, Shape):
            out.extend(value.Solids() or [value])
    return out


def _surface(shape: Shape) -> vtkPolyData:
    """Triangles with points merged across faces, so normals and creases see one surface."""
    raw = shape.toVtkPolyData(_TOLERANCE, _ANGULAR_TOLERANCE)
    faces = vtkPolyData()
    faces.SetPoints(raw.GetPoints())
    faces.SetPolys(raw.GetPolys())
    clean = vtkCleanPolyData()
    clean.SetInputData(faces)
    clean.SetTolerance(1e-6)
    clean.Update()
    return clean.GetOutput()


def _shaded(surface: vtkPolyData, colour: tuple[float, float, float]) -> vtkActor:
    normals = vtkPolyDataNormals()
    normals.SetInputData(surface)
    normals.SetFeatureAngle(_CREASE_DEG)
    normals.SplittingOn()
    normals.ConsistencyOn()
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*colour)
    prop.SetInterpolationToPhong()
    prop.SetAmbient(0.18)
    prop.SetDiffuse(0.82)
    prop.SetSpecular(0.22)
    prop.SetSpecularPower(36.0)
    prop.SetSpecularColor(1.0, 1.0, 1.0)
    return actor


def _lines(source: Any, colour: tuple[float, float, float], width: float) -> vtkActor:
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(source.GetOutputPort())
    mapper.ScalarVisibilityOff()
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*colour)
    prop.SetLineWidth(width * _SUPERSAMPLE)
    prop.LightingOff()
    prop.RenderLinesAsTubesOn()
    return actor


def _scene(wp: Workplane, style: Style, renderer: vtkRenderer) -> list[vtkPolyDataSilhouette]:
    silhouettes: list[vtkPolyDataSilhouette] = []
    for index, solid in enumerate(_solids(wp)):
        colour = style.parts[index % len(style.parts)]
        line = tuple(channel * style.line_shade for channel in colour)
        surface = _surface(solid)
        renderer.AddActor(_shaded(surface, colour))
        creases = vtkFeatureEdges()
        creases.SetInputData(surface)
        creases.SetFeatureAngle(_CREASE_DEG)
        creases.FeatureEdgesOn()
        creases.BoundaryEdgesOn()
        creases.NonManifoldEdgesOff()
        creases.ManifoldEdgesOff()
        creases.ColoringOff()
        renderer.AddActor(_lines(creases, line, style.line_width))
        outline = vtkPolyDataSilhouette()
        outline.SetInputData(surface)
        outline.SetEnableFeatureAngle(False)
        outline.BorderEdgesOff()
        renderer.AddActor(_lines(outline, line, style.line_width * 1.35))
        silhouettes.append(outline)
    return silhouettes


def _place_camera(renderer: vtkRenderer, camera: dict[str, Any]) -> None:
    """Same order as cadquery.vis.show, so the framing of older stills holds."""
    cam = renderer.GetActiveCamera()
    if "position" in camera:
        cam.SetViewUp(*camera["viewup"])
        cam.SetFocalPoint(*camera["focus"])
        cam.SetPosition(*camera["position"])
    else:
        renderer.ResetCamera()
    cam.Roll(camera.get("roll", 0.0))
    cam.Elevation(camera.get("elevation", 0.0))
    cam.Azimuth(camera.get("azimuth", 0.0))
    cam.OrthogonalizeViewUp()
    cam.Zoom(camera.get("zoom", 1.0))
    renderer.ResetCameraClippingRange()


def _shot(wp: Workplane, dest: Path, *, camera: dict[str, Any], style: Style = STUDIO) -> None:
    vtkMapper.SetResolveCoincidentTopologyToPolygonOffset()
    vtkMapper.SetResolveCoincidentTopologyPolygonOffsetParameters(1.5, 2.0)
    vtkMapper.SetResolveCoincidentTopologyLineOffsetParameters(-1.5, -2.0)

    renderer = vtkRenderer()
    renderer.SetBackground(*style.background_bottom)
    renderer.SetBackground2(*style.background_top)
    renderer.GradientBackgroundOn()
    renderer.AutomaticLightCreationOff()
    lights = vtkLightKit()
    lights.SetKeyLightIntensity(style.key_intensity)
    lights.SetKeyToFillRatio(style.key_to_fill)
    lights.SetKeyLightAzimuth(28.0)
    lights.SetKeyLightElevation(48.0)
    lights.SetKeyLightWarmth(0.56)
    lights.SetFillLightWarmth(0.46)
    lights.AddLightsToRenderer(renderer)

    silhouettes = _scene(wp, style, renderer)
    _place_camera(renderer, camera)
    for outline in silhouettes:
        outline.SetCamera(renderer.GetActiveCamera())

    if style.ambient_occlusion:
        bounds = renderer.ComputeVisiblePropBounds()
        span = max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4], 1.0)
        renderer.UseSSAOOn()
        renderer.SetSSAORadius(span * 0.06)
        renderer.SetSSAOBias(span * 0.002)
        renderer.SetSSAOKernelSize(64)
        renderer.SSAOBlurOn()

    window = vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.AddRenderer(renderer)
    window.SetSize(_SIZE[0] * _SUPERSAMPLE, _SIZE[1] * _SUPERSAMPLE)
    window.Render()

    grab = vtkWindowToImageFilter()
    grab.SetInput(window)
    grab.SetInputBufferTypeToRGB()
    grab.ReadFrontBufferOff()
    shrink = vtkImageResize()
    shrink.SetInputConnection(grab.GetOutputPort())
    shrink.SetOutputDimensions(_SIZE[0], _SIZE[1], 1)
    shrink.InterpolateOn()
    writer = vtkPNGWriter()
    writer.SetFileName(str(dest))
    writer.SetInputConnection(shrink.GetOutputPort())
    writer.Write()
    window.Finalize()
    if not dest.is_file() or dest.stat().st_size < 100:
        raise RuntimeError(f"PNG render produced no file: {dest}")
