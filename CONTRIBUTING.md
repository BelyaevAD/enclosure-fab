# Contributing

1. Use CPython 3.12 and `pip install -r requirements.txt`. Do not upgrade the CadQuery stack with `pip install -U`.
2. Add a fixture under `fixtures/` when you add a template or a behavior. Do not commit a measured private part.
3. Geometry belongs in `fabkit/`. `templates/<id>/README.md` describes the template. Do not patch files under `.work/`.
4. Run the checks that CI runs:

   ```text
   python -m pytest tests -q
   ruff check .
   python tools/check_public.py
   python tools/check_skills.py
   ```

5. `tests/golden.json` holds the volume and size of every fixture. After an intended geometry change, refresh it with `FAB_UPDATE_GOLDEN=1 python -m pytest tests/test_geometry.py` and explain the change in the pull request.
6. If you edit `SKILL.md`, run `python tools/check_skills.py --write` to copy it into the client paths. Keep the same sections in `SKILL.ru.md`.
7. On Windows, VTK can crash the interpreter at exit after a clean run. `tests/conftest.py` keeps pytest's own exit code. CI runs on Ubuntu.

Pull requests are welcome. Keep a change small enough to review.
