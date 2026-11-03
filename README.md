# enclosure-fab

Version 0.1.0

**Language:** English | [Русский](README.ru.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Site](https://img.shields.io/badge/site-belyaevad.github.io-0f8f73.svg)](https://belyaevad.github.io/enclosure-fab/)

A short YAML file describes an enclosure. This repository turns it into STL, 3MF, STEP, and a preview picture. You open the 3MF in a slicer. It does not start a printer.

**Site:** [belyaevad.github.io/enclosure-fab](https://belyaevad.github.io/enclosure-fab/) · [Русский](https://belyaevad.github.io/enclosure-fab/ru/)

## What you get

- The YAML file describes the part. A template in the repo builds the solid.
- `preview` writes `PREVIEW-*` while the sizes may still be guesses. That file is not for the printer.
- `print` writes a mesh only after the fit sizes are confirmed and the part does not cross a keep-out.
- The examples are a round body, a box, a shell, and a tray. The numbers are made up.

## Install

CadQuery 2.8 needs Python 3.12. If plain `python` on your machine is 3.13, use `py -3.12` or `python3.12`.

```powershell
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

On Linux or macOS, use `python3.12` the same way.

The 3MF is under `.work/generated/preview/`. Open it in Bambu Studio or another slicer and import the mesh only. The file has no slicer project settings.

Do not run `pip install -U`. VTK, Numba, and NumPy would upgrade together, and the preview can change.

## Examples

Each command writes under `.work/generated/preview/`. The name starts with `PREVIEW-`. Open the `.3mf` in the slicer.

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\fab.py preview fixtures\demo_rect.yaml
& $py scripts\fab.py preview fixtures\demo_round.yaml
& $py scripts\fab.py preview fixtures\demo_shell.yaml
& $py scripts\fab.py preview fixtures\demo_tray.yaml
```

| Fixture | Template | What you get |
|---|---|---|
| `fixtures/demo_rect.yaml` | `enclosure_box` | A small box, about 25×17×12 mm, with one opening on the +X face. The opening is the connector window plus clearance. |
| `fixtures/demo_round.yaml` | `enclosure_round` | A 40 mm cylinder, 18 mm tall, and a 2 mm lid with six 3 mm holes. One picture has the lid on. The other has the body and lid side by side. |
| `fixtures/demo_shell.yaml` | `enclosure_shell` | A shell around a 40×30×16 mm outline. The lid is screwed, not snapped. |
| `fixtures/demo_tray.yaml` | `enclosure_tray` | A tray, 100×80×20 mm inside, with pockets, an open bay, and a separate lid. Turn the lid in the slicer. |

`usb.offset_mm.z` on the rectangular box is the centre of the connector shell, measured from the bottom of the board. The numbers in these files are examples. Copy one and replace them with your own measurements before `print`.

Recipes: [docs/patterns.md](docs/patterns.md).

## Agent setup

Clone the repository, create the 3.12 virtualenv, and install `requirements.txt` as in [Install](#install). Then read [SKILL.md](SKILL.md) before changing a spec. Do not run `pip install -U`. Do not start a printer.

On Linux or macOS the same steps use `python3.12` and `.venv/bin/python`.

This checkout already contains the skill for Cursor, Claude Code, and Codex:

- `.cursor/skills/enclosure-fab/SKILL.md`
- `.claude/skills/enclosure-fab/SKILL.md`
- `.agents/skills/enclosure-fab/SKILL.md`

Open this folder as the project so the client picks up the skill. `python tools/check_skills.py` checks that the three copies match `SKILL.md`.

## Agent skill

- [SKILL.md](SKILL.md)
- [SKILL.ru.md](SKILL.ru.md)

## License

MIT. Copyright (c) 2026 BelyaevAD.
