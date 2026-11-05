"""Fail if the public tree carries a private address, a local path, or untranslated engine text."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = (
    ("private IPv4", re.compile(r"\b(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b192\.168\.\d{1,3}\.\d{1,3}\b|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b")),
    ("local absolute path", re.compile(r"\b[A-Za-z]:[\/](?:Users|workspace)\b|/home/[a-z]")),
    ("monorepo path", re.compile(r"\bplatforms/[a-z0-9-]+/")),
)
# Engine text is English; Russian lives in README.ru, SKILL.ru, docs/ru and the site builder.
ENGLISH_ONLY = ("fabkit/", "mcp/", "scripts/", "schema/", "library/", "fixtures/", "templates/")
CYRILLIC = re.compile("[\u0400-\u04ff]")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if not line.endswith((".png", ".webp", ".jpg", ".svg"))]


def problems() -> list[str]:
    found: list[str] = []
    for rel in tracked_files():
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for label, pattern in RULES:
                if pattern.search(line):
                    found.append(f"{rel}:{number}: {label}")
            if rel.startswith(ENGLISH_ONLY) and CYRILLIC.search(line):
                found.append(f"{rel}:{number}: Cyrillic in English-only engine text")
    return found


def main() -> None:
    found = problems()
    if found:
        raise SystemExit("\n".join(found))
    print("public tree is clean")


if __name__ == "__main__":
    main()
