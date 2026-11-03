# Enclosure primitives

Live geometry is `fabkit/` (CadQuery). This catalog names parts so an agent copies a finished piece instead of inventing a button or a grid, and instead of vendoring OpenSCAD.

The machine reads [`catalog.yaml`](catalog.yaml): MCP `list_primitives` and `fab.py list-primitives`.

## Rule

1. Before a new button, grid, well, or USB window, run `list_primitives`. If `live: true`, copy that pattern.
2. `live: false` means the name exists but the cutter does not, or the part was retired. Do not fake it with windows.
3. Do not git-submodule BOSL2, YAPP_Box, or NopSCADlib, and do not drop `.scad` into a template. One kernel: CadQuery. Pin a URL in [`../upstream/`](../upstream/) and reimplement in `fabkit/`.
4. Another CadQuery enclosure generator is a competing box, not a parts library. Take the idea. Do not replace this wrapper.

## Tongue, pad, and whisker

| Name | YAML / code | What it is |
|------|-------------|------------|
| Tongue | `button.style: flex_tab` | One square U in the standing wall (two slits plus a vertical cap). The hinge is vertical. |
| Pad | `nub_mm` | Pad on the inner face, on the button stem |
| Whisker | `tie_mm` / `flex-tab-ties` | Breakaway ticks across the slits. Snip them after printing. Report field `button_tie_along_mm` |

Do not turn on slicer supports in that gap. They scar the working face.

## Live now

`flex-tab`, `flex-tab-ties`, `grid-45`, `usb-window`, `header-pin-well`, `shed-slot`, `roof-bed-well`, `window-horizontal`, `teardrop-hole`, `gland-bore`, `heat-set-m3`, `hv-partition`, `sma-well`, `open-well`, `mouse-hole`, `floor-mount`, `magnet-cup`, `magnet-corner`, `rest-strip`, `c-ring`.

Names without a cutter: `louver-45`, `honeycomb`, `gable-slot`. Forbidden: `rim-crenel`.
