---
name: enclosure-fab
description: Use when someone wants a 3D-printable enclosure, case, box, tray, pipe clip, channel clip, or doll shoe from measurements. Edit a YAML spec, then build STL, 3MF, and STEP with CadQuery through scripts/fab.py or the fab MCP server. Not for slicing, printer control, or measuring a part.
---

# enclosure-fab

You edit a YAML spec. A template module in `fabkit/` builds the solid. A person opens the 3MF in a slicer.

## Setup

Paths in this file are relative to the root of the enclosure-fab checkout. If you only have this skill, clone the repository first:

```text
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv                                    # Linux, macOS: python3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux, macOS: .venv/bin/python
```

Run the CLI as `.venv/Scripts/python scripts/fab.py` (`.venv/bin/python` on Linux and macOS). The interpreter must be CPython 3.12, because the CadQuery wheels are built for it and `fabkit/runtime.py` stops on any other version. Do not run `pip install -U`: VTK, Numba, and NumPy move together and the geometry can change.

## Words

- **Spec**: the YAML file. Its millimetres are the part. The template adds clearance.
- **Fit-critical field**: a size that decides whether the part fits. `fab.py protocol --family <family>` lists them and says how to measure.
- **confirmed**: `true` only after a person measured the field. You never set it.
- **Keep-out**: a volume the part must not enter, such as the components on a board.
- **preview**: runs with guessed sizes. Files start with `PREVIEW-`.
- **print**: runs only when every fit-critical field is confirmed and nothing enters a keep-out.

## Route

1. Pick the template from the table and copy its fixture from `fixtures/`.
2. `fab.py protocol --family <family>`: what to measure. A photo is a note, not millimetres.
3. `fab.py validate <spec>`: fix the errors and read the warnings.
4. `fab.py preview <spec>`: writes the files under `.work/generated/preview/`, or under `-o <dir>`.
5. Inspect the result (next section) before you say the part is fine.
6. `fab.py print <spec>` only after a person confirmed the fit-critical fields. A keep-out hit leaves no file.
7. Give the person the 3MF path. They open it in the slicer.

| template_id | Fixture | Fit-critical fields |
|---|---|---|
| `enclosure_box` | `demo_rect` | `board.*`, `usb.offset_mm.*`, `usb.opening_wh_mm.*`, `keepout.board` |
| `enclosure_snap` | `demo_snap` | the same as `enclosure_box` |
| `enclosure_round` | `demo_round` | none; the case sizes are the part |
| `enclosure_shell` | `demo_shell` | `device.*`, `keepout.device`, `shell.sma.*` |
| `enclosure_tray` | `demo_tray` | `tray.inner_*`, `pockets.*`, `keepout.tray` |
| `enclosure_magnet_box` | `demo_magnet_box` | `box.outer_*`, `box.magnet_*`, `keepout.box` |
| `ring_yoke` | `demo_ring_yoke` | `rings.band_mm`, both `circumference_mm` and `mouth_mm`, `keepout.bores` |
| `strip_clip` | `demo_strip_clip` | `clip.*` sizes, `keepout.pocket` |
| `doll_mary_jane` | `demo_doll_shoe` | `shoe.*`, `keepout.foot` |

`usb.offset_mm.z` is the centre of the connector shell, measured from the bottom of the board.

## Answer after preview

The first line is `NOT_FOR_PRINT`. Copy the freshness block that `fab.py preview` prints, then the 3MF path and the fields that still need a measurement:

```text
NOT_FOR_PRINT
generated_at: 2026-11-05T17:08:46Z
3mf: PREVIEW-demo_ring_yoke-ring_yoke.3mf  252174 bytes  2026-11-05T17:08:43Z
stale_siblings: (none)
Measure before print: rings.band_mm, rings.bar.circumference_mm, ...
```

## Inspect

- `generated_at` is from this run, and the 3MF time matches it. An older file is a leftover, not your result.
- Look at `*-assembled.png` and `*-print.png`. The print picture is a suggestion. The person still turns parts in the slicer, so never call a file bed-ready.
- An opening goes through the wall and leaves about three lines (1.26 mm) of wall above and below it.
- Each part is one solid. A wall inside an opening in the slicer is a leftover face: fix the template, do not ask the person to repair the mesh.
- Read `warnings` in the JSON. Repeat the ones that affect the fit.

## MCP server

`mcp/server.py` is a stdio server named `fab` with the same gates as the CLI. Tools: `list_templates`, `list_boards`, `list_primitives`, `measurement_protocol`, `validate_spec`, `generate_preview`, `generate_print`, `explain_last_gate`. The server loads `fabkit` once. After `fabkit/` changes, the client must restart the server; until then use the CLI.

## Do not

- Write raw CadQuery in the chat. Change the spec, or the template in `fabkit/`.
- Set `confirmed: true` or run `fab.py confirm --i-measured`. That is the person's step after measuring.
- Start a printer, open the slicer, or add slicer settings.
- Invent a template when a fixture is close. Copy the fixture.
- Patch files under `.work/`. They are output.
