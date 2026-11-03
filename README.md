# enclosure-fab

**Language:** English | [Русский](README.ru.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Site](https://img.shields.io/badge/site-belyaevad.github.io-0f8f73.svg)](https://belyaevad.github.io/enclosure-fab/)

YAML in, a printable mesh out. This repository is a CadQuery wrapper that turns a small spec into STL, 3MF, and STEP, plus a preview image. You open the 3MF in your slicer. The tool does not start a printer.

**Site:** [belyaevad.github.io/enclosure-fab](https://belyaevad.github.io/enclosure-fab/) · [Русский](https://belyaevad.github.io/enclosure-fab/ru/)

## What you get

- A spec file describes the part. A committed template builds the solid. There is no "run this script" tool.
- `preview` writes `PREVIEW-*` files and is not a print release.
- `print` writes a mesh only when the fit-critical fields are confirmed and the keep-out check passes.
- A round pot with a vented lid, a rectangular box, a device shell, and a tray are included as synthetic fixtures. They are examples, not measured products.

## Install

CadQuery 2.8 wheels target CPython 3.12. Do not use a bare `python` if that command is 3.13 on your machine.

```powershell
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

On Linux or macOS, use `python3.12` the same way.

The 3MF is under `.work/generated/preview/`. Open it in Bambu Studio or another slicer and load geometry only. CadQuery does not write Bambu project metadata.

Do not run `pip install -U` on this environment. Unpinned packages under CadQuery (VTK, Numba, NumPy) move together and can change the preview.

## Examples

Each command writes under `.work/generated/preview/`. The name starts with `PREVIEW-`. Open the `.3mf` in the slicer.

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\fab.py preview fixtures\demo_rect.yaml
& $py scripts\fab.py preview fixtures\demo_round.yaml
& $py scripts\fab.py preview fixtures\demo_shell.yaml
& $py scripts\fab.py preview fixtures\demo_tray.yaml
```

| Fixture | Template | What you should see |
|---|---|---|
| `fixtures/demo_rect.yaml` | `enclosure_box` | A small box, about 25×17×12 mm, with one opening on the +X face. The opening is the USB-sized window plus clearance. |
| `fixtures/demo_round.yaml` | `enclosure_round` | A 40 mm cylinder, 18 mm tall, and a 2 mm lid with six 3 mm holes. Assembled view: lid on top. Print view: cup and lid side by side. |
| `fixtures/demo_shell.yaml` | `enclosure_shell` | A shell around a 40×30×16 mm envelope. The lid is screwed, not snapped. |
| `fixtures/demo_tray.yaml` | `enclosure_tray` | A tray with an inner size of 100×80×20 mm, pockets, an open well, and a separate lid. Rotate the lid in the slicer. |

`usb.offset_mm.z` on the rectangular box is the connector-shell centre measured from the bottom of the board. The numbers in these files are invented. Copy a fixture and replace them with your own measurement before `print`.

Recipes: [docs/patterns.md](docs/patterns.md).

## Agent setup

Clone the repository, create the 3.12 venv, and install `requirements.txt` as in [Install](#install). Then read [SKILL.md](SKILL.md) before editing a spec. Do not run `pip install -U`. Do not start a printer.

On Linux or macOS the same steps use `python3.12` and `.venv/bin/python`.

This checkout already contains the skill for Cursor, Claude Code, and Codex:

- `.cursor/skills/enclosure-fab/SKILL.md`
- `.claude/skills/enclosure-fab/SKILL.md`
- `.agents/skills/enclosure-fab/SKILL.md`

Open the checkout as the workspace so the client loads that skill. `python tools/check_skills.py` checks that the three copies match `SKILL.md`.

## Agent skill

- [SKILL.md](SKILL.md)
- [SKILL.ru.md](SKILL.ru.md)

## License

MIT. Copyright (c) 2026 BelyaevAD.
