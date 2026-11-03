# Claude

Install this repository, then read [SKILL.md](SKILL.md) before editing a spec or a template.

```powershell
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

Linux and macOS: `python3.12 -m venv .venv`, then `.venv/bin/python` for pip and `scripts/fab.py`.

Do not run `pip install -U`. Do not start a printer. Open this checkout as the workspace. The skill is already at `.claude/skills/enclosure-fab/SKILL.md`. `python tools/check_skills.py` checks the skill copies.
