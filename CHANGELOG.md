# Changelog

## Unreleased

- Removed one template that is out of scope for this repository, with its fixture, schema entries, and site card. Eight templates remain.
- Preview pictures use a studio renderer: smooth shading, crease and outline lines instead of the triangle mesh, soft lights with ambient occlusion, a quiet background, and a separate colour for each printed part. The axis marker is gone.

## 0.1.1

- Every template now has a fixture: `demo_snap`, `demo_magnet_box`, `demo_ring_yoke`, and `demo_strip_clip` are new.
- Fixed: specs for `ring_yoke`, `strip_clip`, and `enclosure_magnet_box` failed validation because their families were missing from the schema. Their measurement protocols are back.
- Tests compare every fixture with a geometry snapshot (`tests/golden.json`), check that the preview STL is closed, and cover the print and keep-out gates.
- CI runs ruff, a public-tree check, and the skill check, then builds a preview of every fixture as an artifact. Actions moved to v7.
- The skill works from any copy: setup is inline, links no longer point outside the skill folder, and it now covers terms, the route, all templates, the answer format, and the MCP server.
- README and the site describe all templates and the MCP server.

## 0.1.0

First public release. A YAML file becomes STL, 3MF, STEP, and a preview picture. Example fixtures and the agent skill are included. Python 3.12.
