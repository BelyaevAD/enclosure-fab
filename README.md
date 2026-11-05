# enclosure-fab

Version 0.1.1

**Language:** English | [Русский](README.ru.md)

[![Test](https://github.com/BelyaevAD/enclosure-fab/actions/workflows/test.yml/badge.svg)](https://github.com/BelyaevAD/enclosure-fab/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Site](https://img.shields.io/badge/site-belyaevad.github.io-0f8f73.svg)](https://belyaevad.github.io/enclosure-fab/)

A short YAML file describes a printable part: a case for a board, a box, a tray, a pipe clip. This repository turns it into STL, 3MF, STEP, and two preview pictures. You open the 3MF in a slicer. Nothing here talks to a printer.

**Site:** [belyaevad.github.io/enclosure-fab](https://belyaevad.github.io/enclosure-fab/) · [Русский](https://belyaevad.github.io/enclosure-fab/ru/)

## How it works

```text
spec.yaml ─ validate ─ preview (PREVIEW-*, guessed sizes) ─ measure ─ confirm ─ print
```

- The YAML file holds the sizes. A template module in `fabkit/` builds the solid.
- `preview` runs while the sizes are still guesses. Its files start with `PREVIEW-` and are not for the printer.
- `print` writes files only after every fit-critical size is confirmed by a person and the part stays out of every keep-out volume.
- Millimetres in the spec are the part. The template adds the printing clearance.

## Install

CadQuery 2.8 wheels need Python 3.12. If plain `python` on your machine is 3.13, use `py -3.12` or `python3.12`.

```powershell
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

On Linux or macOS, use `python3.12` and `.venv/bin/python` the same way.

The 3MF is under `.work/generated/preview/`. Open it in Bambu Studio or another slicer and import the geometry only. The file has no slicer settings.

Do not run `pip install -U`. VTK, Numba, and NumPy would upgrade together, and the geometry can change.

## Examples

Every template has a fixture. The numbers are made up. Copy a file and put in your own measurements before `print`.

| Fixture | Template | What you get |
|---|---|---|
| `demo_rect` | `enclosure_box` | A box about 25×17×12 mm with one connector opening on +X. |
| `demo_snap` | `enclosure_snap` | A snap-fit case about 31×19×13 mm: USB opening on +X, slots in the roof and on −X. |
| `demo_round` | `enclosure_round` | A 40 mm pot, 18 mm tall, with a 2 mm lid and six 3 mm holes. |
| `demo_shell` | `enclosure_shell` | A shell around a 40×30×16 mm device. The lid is screwed, not snapped. |
| `demo_tray` | `enclosure_tray` | A tray, 100×80×20 mm inside, with pockets, an open bay, and a separate lid. |
| `demo_magnet_box` | `enclosure_magnet_box` | A closed box 90×70×40 mm. The lid sits on Ø6×2 disc magnets in the corner posts. |
| `demo_ring_yoke` | `ring_yoke` | Two C-rings in one flat plate, 12 mm thick. The mouths face opposite ends. |
| `demo_strip_clip` | `strip_clip` | A channel clip with a 40×20 mm pocket, two teeth, and a hole in the top bar. |
| `demo_doll_shoe` | `doll_mary_jane` | A pair of doll shoes about 25 mm long with a strap and an ankle clip. |

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\fab.py list-templates
& $py scripts\fab.py protocol --family ring_yoke
& $py scripts\fab.py validate fixtures\demo_ring_yoke.yaml
& $py scripts\fab.py preview fixtures\demo_ring_yoke.yaml
```

`usb.offset_mm.z` is the centre of the connector shell, measured from the bottom of the board. Recipes for each template: [docs/patterns.md](docs/patterns.md).

## Use with an agent

Clone the repository, create the 3.12 virtualenv, and install `requirements.txt` as in [Install](#install). Open the folder as the project. The skill is already in the paths that Cursor, Claude Code, and Codex read:

- `.cursor/skills/enclosure-fab/SKILL.md`
- `.claude/skills/enclosure-fab/SKILL.md`
- `.agents/skills/enclosure-fab/SKILL.md`
- `skills/enclosure-fab/SKILL.md` for skill catalogs

The text is [SKILL.md](SKILL.md) (Russian: [SKILL.ru.md](SKILL.ru.md)). `python tools/check_skills.py --write` copies it into those paths.

### MCP server

`mcp/server.py` is a stdio MCP server named `fab`. It has the same gates as the CLI. Tools: `list_templates`, `list_boards`, `list_primitives`, `measurement_protocol`, `validate_spec`, `generate_preview`, `generate_print`, `explain_last_gate`. Add it to the client's MCP config with the venv interpreter:

```json
{
  "mcpServers": {
    "fab": {
      "command": "C:/path/to/enclosure-fab/.venv/Scripts/python.exe",
      "args": ["C:/path/to/enclosure-fab/mcp/server.py"]
    }
  }
}
```

On Linux and macOS the command is `/path/to/enclosure-fab/.venv/bin/python`. The server loads `fabkit` once. Restart it after you change `fabkit/`.

## Limits

- The 3MF has no print pose decided for you. Turn the parts in the slicer.
- Nothing measures a part. A photo is a note, not a size.
- Only CPython 3.12 is supported for now.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). The tests compare every fixture with a geometry snapshot in `tests/golden.json`.

## License

MIT. Copyright (c) 2026 BelyaevAD.
