Template `enclosure_snap` is implemented in [`fabkit/enclosure_snap.py`](../../fabkit/enclosure_snap.py). Vents: [`fabkit/vents.py`](../../fabkit/vents.py). Pin rows / side button: [`fabkit/headers.py`](../../fabkit/headers.py).

Clamshell: snap groove into the long walls, bead on the outer lid skirt, corner posts under the PCB, USB window on +X, optional U-slot inlet on −X.

`usb.offset_mm.z` is the shell centre from the PCB bottom (`board_oz`). The USB cutter does not punch the roof. Layout numbers live in [`fabkit/snap_geom.py`](../../fabkit/snap_geom.py).

Ready recipes (copy, do not re-derive): [`DESIGN_PATTERNS.md`](../../DESIGN_PATTERNS.md) — `sealed-snap`, `usb-bay-snap`, `chimney-snap`, `header-snap`, `grid-45`, `shed-slot`, `roof-bed-well`. Named parts: MCP `list_primitives` / [`library/primitives/`](../../library/primitives/).

Do not overlay-patch `.work/generated/`.
