"""Fail if a client skill copy drifts from SKILL.md, or SKILL.ru.md loses a section.

`--write` copies SKILL.md over the client copies first.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "SKILL.md"
RUSSIAN = ROOT / "SKILL.ru.md"
COPIES = (
    ROOT / ".cursor" / "skills" / "enclosure-fab" / "SKILL.md",
    ROOT / ".claude" / "skills" / "enclosure-fab" / "SKILL.md",
    ROOT / ".agents" / "skills" / "enclosure-fab" / "SKILL.md",
    ROOT / "skills" / "enclosure-fab" / "SKILL.md",
)


def sections(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("## "))


def main(argv: list[str]) -> None:
    canon = CANON.read_bytes()
    for path in COPIES:
        if "--write" in argv:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canon)
        if not path.is_file():
            raise SystemExit(f"missing {path.relative_to(ROOT)}")
        if path.read_bytes() != canon:
            raise SystemExit(f"differs from SKILL.md: {path.relative_to(ROOT)}; run with --write")
    if sections(RUSSIAN) != sections(CANON):
        raise SystemExit(f"SKILL.ru.md has {sections(RUSSIAN)} sections, SKILL.md has {sections(CANON)}")
    print("skill copies match")


if __name__ == "__main__":
    main(sys.argv[1:])
