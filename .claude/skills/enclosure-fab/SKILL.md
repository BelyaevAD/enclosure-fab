---
name: enclosure-fab
description: CadQuery YAML enclosure wrapper. Preview and print gates. Not a printer client.
---

# enclosure-fab

Edit a YAML spec and a committed template. The operator opens the 3MF in a slicer.

## Read first

1. [AGENTS.md](AGENTS.md) to install the 3.12 venv
2. [README.md](README.md)
3. [docs/patterns.md](docs/patterns.md)
4. `fixtures/` for a starting spec

## Rules

- Spec millimetres are the part. The template adds clearance.
- `preview` may run while fields are unconfirmed. The first line of the answer is `NOT_FOR_PRINT`. The file name starts with `PREVIEW-`.
- `print` only after fit-critical fields are confirmed. A keep-out intersection means no file.
- `usb.offset_mm.z` is the connector-shell centre from the bottom of the board.
- Copy a fixture (`demo_rect`, `demo_round`, `demo_shell`, `demo_tray`) instead of inventing a template.
- Do not write raw CadQuery in the chat. Do not start a print. Do not open the slicer.
- The interpreter is CPython 3.12. Do not recreate the venv with a bare `python` that is 3.13.
- Do not run `pip install -U`.
