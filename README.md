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
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

On Linux or macOS, use `python3.12` the same way.

The 3MF is under `.work/generated/preview/`. Open it in Bambu Studio or another slicer and load geometry only. CadQuery does not write Bambu project metadata.

Do not run `pip install -U` on this environment. Unpinned packages under CadQuery (VTK, Numba, NumPy) move together and can change the preview.

## Examples

| Fixture | What it shows |
|---|---|
| `fixtures/demo_rect.yaml` | Small rectangular box with a USB-sized opening |
| `fixtures/demo_round.yaml` | Round pot, separate lid, six holes in the lid |
| `fixtures/demo_shell.yaml` | Shell around a device envelope |
| `fixtures/demo_tray.yaml` | Tray with an open well and a separate lid |

Recipes: [docs/patterns.md](docs/patterns.md).

## Agent skill

Cursor, Claude Code, and Codex read the English skill. The Russian text is an extra file and is not loaded automatically.

- [SKILL.md](SKILL.md)
- [SKILL.ru.md](SKILL.ru.md)

## License

MIT. Copyright (c) 2026 BelyaevAD.
