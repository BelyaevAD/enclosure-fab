"""ISO 3MF for Bambu Studio: one plate object per solid, no component assembly.

CadQuery's ThreeMFWriter wraps every export in a single <object> of type
component and one <build><item>. Studio 'load geometry data only' then
flattens the assembly; wall-slot holes close on some layers. STEP (B-rep)
does not. Put each solid on the build plate as its own item.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from cadquery.occ_impl.shapes import Shape

from fabkit.paths import STL_ANGULAR_TOLERANCE, STL_TOLERANCE

NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
MODEL_REL = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"


def write_solids_3mf(
    solids: Sequence[Shape],
    dest: Path,
    *,
    tolerance: float = STL_TOLERANCE,
    angular_tolerance: float = STL_ANGULAR_TOLERANCE,
) -> None:
    meshes = []
    for solid in solids:
        verts, tris = solid.tessellate(tolerance, angular_tolerance)
        if not verts or not tris:
            continue
        meshes.append((verts, tris))
    if not meshes:
        raise ValueError(f"write_solids_3mf: nothing tessellated for {dest.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    xml = _model_xml(meshes)
    with ZipFile(dest, "w", ZIP_DEFLATED) as zf:
        zf.writestr("_rels/.rels", _relationships())
        zf.writestr("[Content_Types].xml", _content_types())
        zf.writestr("3D/3dmodel.model", xml)


def _model_xml(meshes: list[tuple[list, list]]) -> bytes:
    model = ET.Element(
        "model",
        {"xml:lang": "en-US", "xmlns": NS, "unit": "millimeter"},
    )
    ET.SubElement(model, "metadata", name="Application").text = "enclosure-fab"
    ET.SubElement(model, "metadata", name="CreationDate").text = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    resources = ET.SubElement(model, "resources")
    build = ET.SubElement(model, "build")
    for i, (verts, tris) in enumerate(meshes, start=1):
        obj = ET.SubElement(
            resources,
            "object",
            id=str(i),
            name=f"solid-{i}",
            type="model",
        )
        mesh = ET.SubElement(obj, "mesh")
        vertices = ET.SubElement(mesh, "vertices")
        for v in verts:
            ET.SubElement(
                vertices,
                "vertex",
                x=f"{float(v.x):.6f}",
                y=f"{float(v.y):.6f}",
                z=f"{float(v.z):.6f}",
            )
        triangles = ET.SubElement(mesh, "triangles")
        for t in tris:
            ET.SubElement(
                triangles,
                "triangle",
                v1=str(t[0]),
                v2=str(t[1]),
                v3=str(t[2]),
            )
        ET.SubElement(build, "item", objectid=str(i))
    return ET.tostring(model, xml_declaration=True, encoding="utf-8")


def _content_types() -> bytes:
    root = ET.Element("Types", xmlns=CT_NS)
    ET.SubElement(
        root,
        "Override",
        PartName="/3D/3dmodel.model",
        ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
    )
    ET.SubElement(
        root,
        "Override",
        PartName="/_rels/.rels",
        ContentType="application/vnd.openxmlformats-package.relationships+xml",
    )
    return ET.tostring(root, xml_declaration=True, encoding="utf-8")


def _relationships() -> bytes:
    root = ET.Element("Relationships", xmlns=REL_NS)
    ET.SubElement(
        root,
        "Relationship",
        Target="/3D/3dmodel.model",
        Id="rel-1",
        Type=MODEL_REL,
        TargetMode="Internal",
    )
    return ET.tostring(root, xml_declaration=True, encoding="utf-8")
