# enclosure-fab

Версия 0.1.1

**Язык:** [English](README.md) | Русский

Короткий YAML описывает деталь для печати: корпус под плату, коробку, лоток, зажим на трубу. Репозиторий делает из него STL, 3MF, STEP и две картинки. 3MF открываешь в слайсере сам. С принтером здесь ничего не связано.

**Сайт:** [английская страница](https://belyaevad.github.io/enclosure-fab/) · [русская страница](https://belyaevad.github.io/enclosure-fab/ru/)

## Как это устроено

```text
spec.yaml ─ validate ─ preview (PREVIEW-*, размеры на глаз) ─ замер ─ confirm ─ print
```

- Размеры лежат в YAML. Тело строит модуль шаблона в `fabkit/`.
- `preview` работает, пока размеры — догадка. Имена файлов начинаются с `PREVIEW-`, такие файлы не для принтера.
- `print` пишет файлы только когда человек подтвердил все fit-critical размеры и деталь не заходит в keep-out.
- Миллиметры в спеке — сама деталь. Зазор под печать добавляет шаблон.

## Установка

Колёса CadQuery 2.8 ставятся на Python 3.12. Если обычный `python` у тебя 3.13, бери `py -3.12` или `python3.12`.

```powershell
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

На Linux и macOS те же шаги через `python3.12` и `.venv/bin/python`.

3MF лежит в `.work/generated/preview/`. Открывай его в Bambu Studio или другом слайсере как геометрию. Настроек слайсера в файле нет.

Не запускай `pip install -U`. VTK, Numba и NumPy обновятся вместе, и геометрия может измениться.

## Примеры

У каждого шаблона есть фикстура. Числа в них выдуманы. Скопируй файл и подставь свои размеры до `print`.

| Фикстура | Шаблон | Что получится |
|---|---|---|
| `demo_rect` | `enclosure_box` | Коробка около 25×17×12 мм с одним окном под разъём на +X. |
| `demo_snap` | `enclosure_snap` | Корпус на защёлке около 31×19×13 мм: окно USB на +X, щели в крыше и на −X. |
| `demo_round` | `enclosure_round` | Горшок Ø40 мм, высота 18 мм, крышка 2 мм с шестью отверстиями Ø3 мм. |
| `demo_shell` | `enclosure_shell` | Кожух вокруг прибора 40×30×16 мм. Крышка на винтах, не на защёлке. |
| `demo_tray` | `enclosure_tray` | Лоток 100×80×20 мм внутри: карманы, открытый отсек, отдельная крышка. |
| `demo_magnet_box` | `enclosure_magnet_box` | Закрытая коробка 90×70×40 мм. Крышка держится на дисковых магнитах Ø6×2 в угловых стойках. |
| `demo_ring_yoke` | `ring_yoke` | Два C-кольца в одной плоской пластине толщиной 12 мм. Зевы смотрят в разные стороны. |
| `demo_strip_clip` | `strip_clip` | Скоба с карманом 40×20 мм, двумя зубьями и отверстием в верхней планке. |

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\fab.py list-templates
& $py scripts\fab.py protocol --family ring_yoke
& $py scripts\fab.py validate fixtures\demo_ring_yoke.yaml
& $py scripts\fab.py preview fixtures\demo_ring_yoke.yaml
```

`usb.offset_mm.z` — центр кожуха разъёма от низа платы. Рецепты по шаблонам: [docs/patterns.md](docs/patterns.md).

## С агентом

Склонируй репозиторий, создай окружение на 3.12 и поставь `requirements.txt`, как в разделе [Установка](#установка). Открой папку как проект. Навык уже лежит там, где его читают Cursor, Claude Code и Codex:

- `.cursor/skills/enclosure-fab/SKILL.md`
- `.claude/skills/enclosure-fab/SKILL.md`
- `.agents/skills/enclosure-fab/SKILL.md`
- `skills/enclosure-fab/SKILL.md` для каталогов навыков

Текст навыка — [SKILL.md](SKILL.md) (по-русски — [SKILL.ru.md](SKILL.ru.md)). `python tools/check_skills.py --write` раскладывает его по этим путям.

### MCP-сервер

`mcp/server.py` — stdio MCP-сервер `fab` с теми же гейтами, что у CLI. Инструменты: `list_templates`, `list_boards`, `list_primitives`, `measurement_protocol`, `validate_spec`, `generate_preview`, `generate_print`, `explain_last_gate`. Добавь его в конфиг MCP клиента с интерпретатором из venv:

```json
{
  "mcpServers": {
    "fab": {
      "command": "C:/path/to/enclosure-fab/.venv/Scripts/python.exe",
      "args": ["C:/path/to/enclosure-fab/mcp/server.py"]
    }
  }
}
```

На Linux и macOS команда — `/path/to/enclosure-fab/.venv/bin/python`. Сервер загружает `fabkit` один раз. После правки `fabkit/` перезапусти его.

## Ограничения

- Позу печати 3MF за тебя не выбирает. Разворачивай детали в слайсере.
- Ничего не измеряет деталь. Фото — заметка, не размер.
- Пока поддерживается только CPython 3.12.

## Разработка

См. [CONTRIBUTING.md](CONTRIBUTING.md). Тесты сравнивают каждую фикстуру с эталоном геометрии в `tests/golden.json`.

## Лицензия

MIT. Copyright (c) 2026 BelyaevAD.
