# Contributing

English is the language of this repository. Russian files (`README.ru.md`, `SKILL.ru.md`, `docs/ru/`) are translations. Change the English text first, then the Russian file in the same change.

1. Use CPython 3.12 and `pip install -r requirements.txt`. Do not upgrade the CadQuery stack with `pip install -U`.
2. Add a fixture under `fixtures/` when you add a behavior. Do not commit a measured private part.
3. Geometry belongs in `fabkit/` and `templates/`. Do not patch files under `.work/`.
4. `python -m pytest tests -q` should pass. On Windows the process may exit with a VTK teardown code after the tests have passed. CI runs on Ubuntu.
5. If you edit `SKILL.md`, copy that same text into the three client skill paths. `python tools/check_skills.py` checks the copies.

Pull requests are welcome. Keep a change small enough to review.
