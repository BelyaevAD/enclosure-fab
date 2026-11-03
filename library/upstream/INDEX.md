# Upstream pins, not vendored source

Other repositories are not cloned into this tree. This folder pins a URL, a license, when it was last checked, what to take, and why it is not a submodule.

The machine reads [`pins.yaml`](pins.yaml).

## How to update

1. When you touch a primitive, open the pin and actually look at the URL. Update `last_checked`.
2. A useful trick that is not in `fabkit/` yet gets a `live: false` row in [`../primitives/catalog.yaml`](../primitives/catalog.yaml) until the cutter exists.
3. Do not `git submodule add` OpenSCAD. Do not `pip install` a competing enclosure generator in place of `fabkit`.

## Why the whole repo stays out

| Repo | Why look | Why not vendor |
|------|----------|----------------|
| [cq_enclosure_builder](https://github.com/raphael-isvelin/cq_enclosure_builder) | CadQuery parts: buttons, air vents, grids | A different box generator. Its buttons are panel cutouts, not a tongue in the wall. |
| [Parametric_Enclosure](https://github.com/CadQuery/cadquery-contrib/blob/master/examples/Parametric_Enclosure.py) | Screw posts | An example, not this wrapper. Device shells are `fabkit/enclosure_shell.py`. |
| [YAPP_Box](https://github.com/mrWheel/YAPP_Box) | PCB box, honeycomb masks | OpenSCAD |
| [BOSL2](https://github.com/BelfrySCAD/BOSL2) | Masks and primitives | OpenSCAD, and large |
| [NopSCADlib](https://github.com/nophead/NopSCADlib) | `vitamins/button.scad` | Tactile-switch models, not a wall flex tab. OpenSCAD |

One kernel: CadQuery. No OpenSCAD fallback.
