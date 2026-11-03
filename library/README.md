# library/

| Folder | What |
|--------|------|
| [`boards/`](boards/) | Family stubs (`wemos.yaml` and similar). Not a finished part. |
| [`primitives/`](primitives/) | Named parts (`flex-tab`, `shed-slot`, `grid-45`). Geometry lives in `fabkit/`. |
| [`upstream/`](upstream/) | Pins of other people's repositories. Copy the idea, do not vendor the repo. |

Examples are the fixtures in [`fixtures/`](../fixtures/). `fab.py list-boards` lists the stubs. `fab.py list-primitives` lists the named parts.
