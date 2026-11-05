# Agents

Read [SKILL.md](SKILL.md) before you edit a spec or a template. It has the setup, the route, and the rules.

```powershell
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

Linux and macOS: `python3.12 -m venv .venv`, then `.venv/bin/python` for pip and `scripts/fab.py`.

Do not run `pip install -U`. Do not start a printer. Before a pull request, run the checks listed in [CONTRIBUTING.md](CONTRIBUTING.md).
