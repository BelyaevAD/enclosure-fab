"""Build docs/index.html, docs/ru/index.html, and docs/404.html from one template.

    python tools/build_site.py            # pages only, stdlib
    python tools/build_site.py --images   # also re-render docs/assets/*.webp from the fixtures (venv 3.12)

CI runs the first form and fails if the committed pages differ.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
SITE = "https://belyaevad.github.io/enclosure-fab/"
REPO = "https://github.com/BelyaevAD/enclosure-fab"
CARD_PX = (640, 480)
HERO_PX = (960, 720)
OG_PX = (1200, 630)
HERO_FIXTURE = "demo_snap"
OG_FIXTURES = ("demo_snap", "demo_tray", "demo_ring_yoke")

# (fixture, template, English title, English line, Russian title, Russian line)
FIXTURES = (
    ("demo_rect", "enclosure_box", "Box with a connector opening", "About 25×17×12 mm. One opening on +X.",
     "Коробка с окном под разъём", "Около 25×17×12 мм. Одно окно на +X."),
    ("demo_snap", "enclosure_snap", "Snap-fit case", "Base and lid snap together. USB on +X, slots in the roof.",
     "Корпус на защёлке", "Основание и крышка защёлкиваются. USB на +X, щели в крыше."),
    ("demo_round", "enclosure_round", "Round pot", "Ø40 mm, a lid with six holes.",
     "Круглый горшок", "Ø40 мм, крышка с шестью отверстиями."),
    ("demo_shell", "enclosure_shell", "Device shell", "A shell around a 40×30×16 mm device. Screw lid.",
     "Кожух прибора", "Кожух вокруг прибора 40×30×16 мм. Крышка на винтах."),
    ("demo_tray", "enclosure_tray", "Tray", "Pockets, an open bay, and a separate lid.",
     "Лоток", "Карманы, открытый отсек и отдельная крышка."),
    ("demo_magnet_box", "enclosure_magnet_box", "Magnet box", "90×70×40 mm. The lid sits on disc magnets.",
     "Коробка на магнитах", "90×70×40 мм. Крышка держится на дисковых магнитах."),
    ("demo_ring_yoke", "ring_yoke", "Two rings in one plate", "C-rings for two pipes. Prints flat.",
     "Два кольца в одной пластине", "C-кольца под две трубы. Печатается плашмя."),
    ("demo_strip_clip", "strip_clip", "Channel clip", "Two teeth and a hole in the top bar. Prints on its side.",
     "Скоба", "Два зуба и отверстие в верхней планке. Печатается на боку."),
    ("demo_doll_shoe", "doll_mary_jane", "Doll shoes", "A pair, with a strap and an ankle clip.",
     "Кукольные туфли", "Пара с ремешком и клипсой на щиколотке."),
)

TEXT = {
    "en": {
        "root": "", "url": SITE, "locale": "en_US", "alt_locale": "ru_RU",
        "title": "enclosure-fab — printable parts from YAML",
        "description": "A short YAML file describes a printable part. You get STL, 3MF, STEP, and two pictures. You open the 3MF in a slicer.",
        "nav_examples": "Examples", "nav_agent": "Agents", "nav_patterns": "Patterns", "star": "Star",
        "lead": "A short YAML file describes the part: a case for a board, a box, a tray, a pipe clip. You get STL, 3MF, STEP, and two pictures. Open the 3MF in a slicer yourself. Nothing here talks to a printer.",
        "source": "View source", "install": "Install",
        "meta": ("CPython 3.12", "9 templates", "Draft, not a print", "MIT"),
        "hero_alt": "Snap-fit case with roof slots, assembled", "hero_caption": "fixtures/demo_snap.yaml · assembled",
        "how": "How it works",
        "how_lead": "The shape comes from a template in the repo. Change the numbers in YAML instead of writing a script for each part.",
        "features": (
            ("Draft first", "You can build a file before the sizes are checked. The name starts with <code>PREVIEW-</code>. Do not print that file yet."),
            ("Then print", "<code>print</code> runs only after a person confirmed the sizes that decide the fit. If the part crosses a keep-out, no file is written."),
            ("Then the slicer", "The 3MF is the shape only, with no slicer settings. Turn the parts on the bed yourself."),
        ),
        "examples": "Examples",
        "examples_lead": "Every template has a fixture in <code>fixtures/</code>. The numbers are made up. Copy a file and put in your own measurements.",
        "print_view": "For the slicer",
        "agent": "Use with an agent",
        "agent_lead": "The skill is already in the paths that Cursor, Claude Code, and Codex read. Open the clone as the project. The MCP server <code>fab</code> has the same gates as the CLI.",
        "agent_points": (
            "Skill: <code>.cursor/skills/</code>, <code>.claude/skills/</code>, <code>.agents/skills/</code>",
            "Tools: <code>validate_spec</code>, <code>generate_preview</code>, <code>generate_print</code>, <code>measurement_protocol</code> and four more",
            "The agent never sets <code>confirmed</code>. A person measures.",
        ),
        "skill_link": "Read the skill",
        "install_h": "Install",
        "install_lead": "CadQuery 2.8 needs Python 3.12. Do not run <code>pip install -U</code>: VTK, Numba, and NumPy would move together, and the geometry can change.",
        "install_link": "Full instructions",
        "footer_lang": ("ru/", "ru", "Русский"),
    },
    "ru": {
        "root": "../", "url": SITE + "ru/", "locale": "ru_RU", "alt_locale": "en_US",
        "title": "enclosure-fab — детали для печати из YAML",
        "description": "Короткий YAML описывает деталь для печати. Получаешь STL, 3MF, STEP и две картинки. 3MF открываешь в слайсере.",
        "nav_examples": "Примеры", "nav_agent": "Агенты", "nav_patterns": "Рецепты", "star": "Звезда",
        "lead": "Короткий YAML описывает деталь: корпус под плату, коробку, лоток, зажим на трубу. Получаешь STL, 3MF, STEP и две картинки. 3MF открываешь в слайсере сам. С принтером здесь ничего не связано.",
        "source": "Исходники", "install": "Установка",
        "meta": ("CPython 3.12", "9 шаблонов", "Черновик, не печать", "MIT"),
        "hero_alt": "Корпус на защёлке со щелями в крыше, в сборе", "hero_caption": "fixtures/demo_snap.yaml · в сборе",
        "how": "Как это устроено",
        "how_lead": "Форму строит шаблон из репозитория. Меняешь числа в YAML, а не пишешь скрипт под каждую деталь.",
        "features": (
            ("Сначала черновик", "Файл можно собрать до проверки размеров. Имя начинается с <code>PREVIEW-</code>. Такой файл печатать рано."),
            ("Потом печать", "<code>print</code> работает только после того, как человек подтвердил размеры, от которых зависит посадка. Если деталь заходит в keep-out, файла нет."),
            ("Дальше слайсер", "В 3MF только форма, без настроек слайсера. Детали на столе разворачиваешь сам."),
        ),
        "examples": "Примеры",
        "examples_lead": "У каждого шаблона есть фикстура в <code>fixtures/</code>. Числа выдуманы. Скопируй файл и подставь свои замеры.",
        "print_view": "Для слайсера",
        "agent": "С агентом",
        "agent_lead": "Навык уже лежит там, где его читают Cursor, Claude Code и Codex. Открой клон как проект. MCP-сервер <code>fab</code> проверяет то же, что CLI.",
        "agent_points": (
            "Навык: <code>.cursor/skills/</code>, <code>.claude/skills/</code>, <code>.agents/skills/</code>",
            "Инструменты: <code>validate_spec</code>, <code>generate_preview</code>, <code>generate_print</code>, <code>measurement_protocol</code> и ещё четыре",
            "Агент не ставит <code>confirmed</code>. Мерит человек.",
        ),
        "skill_link": "Текст навыка",
        "install_h": "Установка",
        "install_lead": "CadQuery 2.8 ставится на Python 3.12. Не запускай <code>pip install -U</code>: VTK, Numba и NumPy поднимутся вместе, и геометрия может измениться.",
        "install_link": "Подробная инструкция",
        "footer_lang": ("../", "en", "English"),
    },
}

INSTALL = r"""git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_snap.yaml"""

MCP_CONFIG = """{
  "mcpServers": {
    "fab": {
      "command": "/path/to/enclosure-fab/.venv/bin/python",
      "args": ["/path/to/enclosure-fab/mcp/server.py"]
    }
  }
}"""

CSP = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'none'; base-uri 'none'; form-action 'none'"


def version() -> str:
    match = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    if not match:
        raise SystemExit("CHANGELOG.md has no '## X.Y.Z' heading")
    return match.group(1)


def json_ld(lang: str, t: dict, ver: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareSourceCode",
        "name": "enclosure-fab",
        "description": t["description"],
        "url": t["url"],
        "codeRepository": REPO,
        "programmingLanguage": "Python",
        "runtimePlatform": "CPython 3.12",
        "license": "https://opensource.org/licenses/MIT",
        "version": ver,
        "inLanguage": lang,
        "author": {"@type": "Person", "name": "BelyaevAD", "url": "https://github.com/BelyaevAD"},
        "keywords": "3D printing, CadQuery, enclosure, STL, 3MF, STEP, YAML, MCP, agent skill",
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def card(row: tuple, lang: str, t: dict) -> str:
    name, template, en_title, en_line, ru_title, ru_line = row
    title, line = (en_title, en_line) if lang == "en" else (ru_title, ru_line)
    root = t["root"]
    return f"""          <figure class="shot-card">
            <img src="{root}assets/{name}.webp" alt="{html.escape(title)}" width="{CARD_PX[0]}" height="{CARD_PX[1]}" loading="lazy" decoding="async">
            <figcaption>
              <strong>{html.escape(title)}</strong>
              <span>{html.escape(line)}</span>
              <span class="shot-meta"><code>{name}</code> · <code>{template}</code> · <a href="{root}assets/{name}-print.webp">{t["print_view"]}</a></span>
            </figcaption>
          </figure>"""


def page(lang: str) -> str:
    t = TEXT[lang]
    ver = version()
    root = t["root"]
    features = "\n".join(
        f'          <article class="feature">\n            <h3>{h}</h3>\n            <p>{p}</p>\n          </article>'
        for h, p in t["features"]
    )
    cards = "\n".join(card(row, lang, t) for row in FIXTURES)
    meta = "\n".join(f"            <span>{item}</span>" for item in t["meta"])
    points = "\n".join(f"            <li>{item}</li>" for item in t["agent_points"])
    en_current = ' aria-current="page"' if lang == "en" else ""
    ru_current = ' aria-current="page"' if lang == "ru" else ""
    lang_href, lang_code, lang_label = t["footer_lang"]
    readme = f"{REPO}/blob/main/{'README.ru.md' if lang == 'ru' else 'README.md'}"
    install_anchor = "#установка" if lang == "ru" else "#install"
    skill = f"{REPO}/blob/main/{'SKILL.ru.md' if lang == 'ru' else 'SKILL.md'}"
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy" content="{CSP}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(t["title"])}</title>
  <meta name="description" content="{html.escape(t["description"])}">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <meta name="author" content="BelyaevAD">
  <meta name="theme-color" content="#0e221d">
  <link rel="canonical" href="{t["url"]}">
  <link rel="alternate" hreflang="en" href="{SITE}">
  <link rel="alternate" hreflang="ru" href="{SITE}ru/">
  <link rel="alternate" hreflang="x-default" href="{SITE}">
  <link rel="sitemap" type="application/xml" href="{SITE}sitemap.xml">
  <link rel="icon" type="image/svg+xml" href="{root}assets/brand-mark.svg">
  <link rel="preload" as="image" href="{root}assets/{HERO_FIXTURE}-hero.webp" type="image/webp">
  <link rel="stylesheet" href="{root}assets/site.css">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="{t["locale"]}">
  <meta property="og:locale:alternate" content="{t["alt_locale"]}">
  <meta property="og:title" content="{html.escape(t["title"])}">
  <meta property="og:description" content="{html.escape(t["description"])}">
  <meta property="og:url" content="{t["url"]}">
  <meta property="og:site_name" content="enclosure-fab">
  <meta property="og:image" content="{SITE}assets/og.jpg">
  <meta property="og:image:width" content="{OG_PX[0]}">
  <meta property="og:image:height" content="{OG_PX[1]}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="enclosure-fab">
  <meta name="twitter:description" content="{html.escape(t["description"])}">
  <meta name="twitter:image" content="{SITE}assets/og.jpg">
  <script type="application/ld+json">
{json_ld(lang, t, ver)}
  </script>
</head>
<body>
  <header class="site-header">
    <nav class="nav shell" aria-label="Primary">
      <a class="brand" href="./">
        <img src="{root}assets/brand-mark.svg" alt="" width="36" height="36">
        <span>enclosure-fab</span>
      </a>
      <div class="nav-right">
        <div class="nav-links">
          <a href="#examples">{t["nav_examples"]}</a>
          <a href="#agent">{t["nav_agent"]}</a>
          <a href="{REPO}/blob/main/docs/patterns.md" rel="noopener">{t["nav_patterns"]}</a>
        </div>
        <a class="nav-star" href="{REPO}" rel="noopener" aria-label="{t["star"]}: BelyaevAD/enclosure-fab on GitHub">★ {t["star"]}</a>
        <div class="language-switch" aria-label="Language">
          <a href="{root}" lang="en"{en_current}>EN</a>
          <a href="{root}ru/" lang="ru"{ru_current}>RU</a>
        </div>
      </div>
    </nav>
  </header>
  <main>
    <section class="hero-band">
      <div class="hero-inner shell">
        <div class="hero-copy">
          <p class="eyebrow">Python 3.12 · CadQuery · MCP</p>
          <h1>enclosure-fab</h1>
          <p class="hero-lead">{t["lead"]}</p>
          <div class="hero-actions">
            <a class="button" href="{REPO}" rel="noopener">{t["source"]}</a>
            <a class="button secondary" href="#install">{t["install"]}</a>
          </div>
          <div class="hero-meta">
{meta}
          </div>
        </div>
        <figure class="hero-visual">
          <div class="hero-frame">
            <img src="{root}assets/{HERO_FIXTURE}-hero.webp" alt="{html.escape(t["hero_alt"])}" width="{HERO_PX[0]}" height="{HERO_PX[1]}" fetchpriority="high">
          </div>
          <figcaption>{t["hero_caption"]}</figcaption>
        </figure>
      </div>
    </section>
    <section class="section">
      <div class="shell">
        <div class="section-heading">
          <h2>{t["how"]}</h2>
          <p>{t["how_lead"]}</p>
        </div>
        <div class="feature-grid">
{features}
        </div>
      </div>
    </section>
    <section class="section white" id="examples">
      <div class="shell">
        <div class="section-heading">
          <h2>{t["examples"]}</h2>
          <p>{t["examples_lead"]}</p>
        </div>
        <div class="shot-gallery">
{cards}
        </div>
      </div>
    </section>
    <section class="section" id="agent">
      <div class="quick-start shell">
        <div class="quick-copy">
          <h2>{t["agent"]}</h2>
          <p>{t["agent_lead"]}</p>
          <ul class="agent-list">
{points}
          </ul>
          <a class="button" href="{skill}" rel="noopener">{t["skill_link"]}</a>
        </div>
        <div class="code-window" aria-label="MCP config">
          <div class="code-toolbar">
            <span class="window-dot"></span>
            <span class="window-dot yellow"></span>
            <span class="window-dot green"></span>
            <span>mcp.json</span>
          </div>
          <pre><code>{html.escape(MCP_CONFIG)}</code></pre>
        </div>
      </div>
    </section>
    <section class="section dark" id="install">
      <div class="quick-start shell">
        <div class="quick-copy">
          <h2>{t["install_h"]}</h2>
          <p>{t["install_lead"]}</p>
          <a class="button secondary" href="{readme}{install_anchor}" rel="noopener">{t["install_link"]}</a>
        </div>
        <div class="code-window" aria-label="Install commands">
          <div class="code-toolbar">
            <span class="window-dot"></span>
            <span class="window-dot yellow"></span>
            <span class="window-dot green"></span>
            <span>powershell</span>
          </div>
          <pre><code>{html.escape(INSTALL)}</code></pre>
        </div>
      </div>
    </section>
  </main>
  <footer class="site-footer">
    <div class="footer-inner shell">
      <p>enclosure-fab · {ver} · MIT</p>
      <div class="footer-links">
        <a href="{REPO}" rel="noopener">GitHub</a>
        <a href="{REPO}/releases" rel="noopener">Releases</a>
        <a href="{REPO}/blob/main/LICENSE" rel="noopener">License</a>
        <a href="{lang_href}" lang="{lang_code}">{lang_label}</a>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def not_found() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy" content="{CSP}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <title>Not found — enclosure-fab</title>
  <link rel="icon" type="image/svg+xml" href="/enclosure-fab/assets/brand-mark.svg">
  <link rel="stylesheet" href="/enclosure-fab/assets/site.css">
</head>
<body>
  <main class="section">
    <div class="shell section-heading">
      <h1>404</h1>
      <p>This page does not exist. <a href="/enclosure-fab/">Home</a> · <a href="/enclosure-fab/ru/" lang="ru">Главная</a></p>
    </div>
  </main>
</body>
</html>
"""


def _webp(source: Path, dest: Path, size: tuple[int, int]) -> None:
    from PIL import Image

    with Image.open(source) as image:
        image.convert("RGB").resize(size, Image.Resampling.LANCZOS).save(dest, "WEBP", quality=80, method=6)


def _og_image(sources: list[Path]) -> None:
    from PIL import Image

    canvas = Image.new("RGB", OG_PX, (14, 34, 29))
    tile_w = OG_PX[0] // len(sources)
    for index, source in enumerate(sources):
        with Image.open(source) as opened:
            tile = opened.convert("RGB")
        tile.thumbnail((tile_w - 24, OG_PX[1] - 24))
        canvas.paste(tile, (index * tile_w + (tile_w - tile.width) // 2, (OG_PX[1] - tile.height) // 2))
    canvas.save(ASSETS / "og.jpg", "JPEG", quality=85, optimize=True, progressive=True)


def render_images() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        for name, *_ in FIXTURES:
            out = Path(tmp) / name
            # Windows VTK may crash the child at exit after writing; trust the files, not the exit code.
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "fab.py"), "preview", str(ROOT / "fixtures" / f"{name}.yaml"), "-o", str(out)],
                capture_output=True,
                check=False,
            )
            assembled = next(out.glob("*-assembled.png"), None)
            printed = next(out.glob("*-print.png"), None)
            if assembled is None or printed is None:
                raise SystemExit(f"preview of {name} wrote no pictures")
            _webp(assembled, ASSETS / f"{name}.webp", CARD_PX)
            _webp(printed, ASSETS / f"{name}-print.webp", CARD_PX)
            if name == HERO_FIXTURE:
                _webp(assembled, ASSETS / f"{name}-hero.webp", HERO_PX)
    _og_image([ASSETS / f"{name}.webp" for name in OG_FIXTURES])


def main(argv: list[str]) -> None:
    if "--images" in argv:
        render_images()
    (DOCS / "index.html").write_text(page("en"), encoding="utf-8", newline="\n")
    (DOCS / "ru" / "index.html").write_text(page("ru"), encoding="utf-8", newline="\n")
    (DOCS / "404.html").write_text(not_found(), encoding="utf-8", newline="\n")
    missing = [row[0] for row in FIXTURES if not (ASSETS / f"{row[0]}.webp").is_file()]
    if missing:
        raise SystemExit("missing pictures (run with --images): " + ", ".join(missing))
    print("site pages written")


if __name__ == "__main__":
    main(sys.argv[1:])
