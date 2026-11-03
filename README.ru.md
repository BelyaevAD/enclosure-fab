# enclosure-fab

**Язык:** [English](README.md) | Русский

Короткий YAML описывает корпус. Репозиторий делает из него STL, 3MF, STEP и картинку. Файл открываешь в слайсере сам. На принтер ничего не уходит.

**Сайт:** [английская страница](https://belyaevad.github.io/enclosure-fab/) · [русская страница](https://belyaevad.github.io/enclosure-fab/ru/)

## Установка

Пакеты CadQuery 2.8 ставятся на Python 3.12. Если обычный `python` у тебя 3.13, бери `py -3.12`.

```powershell
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

Файл `PREVIEW-*` печатать рано. 3MF открывай в Bambu Studio или другом слайсере как модель, без настроек проекта. Не запускай `pip install -U`: VTK, Numba и NumPy обновятся следом, и предпросмотр может измениться.

## Примеры

Команды пишут файлы в `.work/generated/preview/`. Имя начинается с `PREVIEW-`. В слайсер берёшь `.3mf`.

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\fab.py preview fixtures\demo_rect.yaml
& $py scripts\fab.py preview fixtures\demo_round.yaml
& $py scripts\fab.py preview fixtures\demo_shell.yaml
& $py scripts\fab.py preview fixtures\demo_tray.yaml
```

| Файл | Шаблон | Что получится |
|---|---|---|
| `fixtures/demo_rect.yaml` | `enclosure_box` | Небольшая коробка, около 25×17×12 мм, одно окно под разъём на грани +X. |
| `fixtures/demo_round.yaml` | `enclosure_round` | Цилиндр Ø40 мм, высота 18 мм, крышка 2 мм с шестью отверстиями Ø3 мм. |
| `fixtures/demo_shell.yaml` | `enclosure_shell` | Кожух по габариту 40×30×16 мм. Крышка на винтах, не на защёлке. |
| `fixtures/demo_tray.yaml` | `enclosure_tray` | Лоток 100×80×20 мм внутри, карманы, открытый отсек, отдельная крышка. |

Числа в файлах — пример. Перед `print` подставь свои размеры. `usb.offset_mm.z` — центр корпуса разъёма, от низа платы.

Рецепты: [docs/patterns.md](docs/patterns.md).

## Установка для агента

Клонируй репозиторий, создай виртуальное окружение на Python 3.12 и поставь зависимости, как в разделе [Установка](#установка). Потом прочитай [SKILL.md](SKILL.md). Не запускай `pip install -U` и не отправляй файл на принтер.

На Linux и macOS те же шаги через `python3.12` и `.venv/bin/python`.

Навык для Cursor, Claude Code и Codex уже лежит здесь:

- `.cursor/skills/enclosure-fab/SKILL.md`
- `.claude/skills/enclosure-fab/SKILL.md`
- `.agents/skills/enclosure-fab/SKILL.md`

Открой эту папку как проект, чтобы клиент увидел навык. `python tools/check_skills.py` проверяет, что три копии совпадают с `SKILL.md`.

Навык: [SKILL.md](SKILL.md) · [SKILL.ru.md](SKILL.ru.md).

Лицензия MIT. Copyright (c) 2026 BelyaevAD.
