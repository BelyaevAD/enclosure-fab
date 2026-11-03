"""Fail if a client skill copy drifts from SKILL.md."""

from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "SKILL.md"
COPIES = (
    ROOT / ".cursor" / "skills" / "enclosure-fab" / "SKILL.md",
    ROOT / ".claude" / "skills" / "enclosure-fab" / "SKILL.md",
    ROOT / ".agents" / "skills" / "enclosure-fab" / "SKILL.md",
    ROOT / "skills" / "enclosure-fab" / "SKILL.md",
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    origin = digest(CANON)
    for path in COPIES:
        if not path.is_file():
            raise SystemExit(f"missing {path.relative_to(ROOT)}")
        if digest(path) != origin:
            raise SystemExit(f"differs from SKILL.md: {path.relative_to(ROOT)}")
    print("skill copies match")


if __name__ == "__main__":
    main()
