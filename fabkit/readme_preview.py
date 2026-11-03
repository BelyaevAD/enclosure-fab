"""Keep a marked image block in a project README (Cursor + Forgejo markdown)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

MARK_START = "<!-- fab-preview:start -->"
MARK_END = "<!-- fab-preview:end -->"


def preview_block(
    *,
    stem: str = "",
    generated_at: datetime | None = None,
    button: bool = False,
) -> str:
    stamp = (generated_at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    extra = f" {stem}" if stem else ""
    button_md = (
        "\n![Грань кнопки](preview-button.png)\n"
        "\n"
        "*Язычок flex-tab: продольная U-щель, CAD-усы срезать после печати. На USB-ISO этой стены не видно.*\n"
        if button
        else ""
    )
    return (
        f"{MARK_START}\n"
        f"<!-- generated {stamp}{extra} -->\n"
        "![Собранный вид](preview.png)\n"
        "\n"
        "*Собранный ISO. Обновляется `fab.py preview`.*\n"
        "\n"
        "![Поза печати](preview-print.png)\n"
        "\n"
        # Generated advice caption; not a promise the 3MF is bed-ready.
        "*Как на стол. Не путать с собранным видом.*\n"
        f"{button_md}"
        f"{MARK_END}\n"
    )


BLOCK = preview_block(generated_at=datetime(1970, 1, 1, tzinfo=timezone.utc))


def upsert_readme_preview(readme: Path, *, stem: str = "", button: bool = False) -> None:
    if not readme.is_file():
        return
    block = preview_block(stem=stem, button=button)
    text = readme.read_text(encoding="utf-8")
    if MARK_START in text and MARK_END in text:
        pre, rest = text.split(MARK_START, 1)
        _, post = rest.split(MARK_END, 1)
        text = pre.rstrip() + "\n\n" + block + "\n" + post.lstrip("\n")
    elif text.startswith("#"):
        first, _, rest = text.partition("\n")
        text = first + "\n\n" + block + "\n" + rest.lstrip("\n")
    else:
        text = block + "\n" + text
    if not text.endswith("\n"):
        text += "\n"
    readme.write_text(text, encoding="utf-8")
