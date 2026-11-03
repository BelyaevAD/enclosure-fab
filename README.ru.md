# enclosure-fab

**Язык:** [English](README.md) | Русский

Это дополнительный текст. Основной язык репозитория и сайта — английский.

Небольшая обвязка на CadQuery: YAML-спека превращается в STL, 3MF и STEP и в картинку предпросмотра. Печать запускает человек в слайсере. Программа на принтер ничего не отправляет.

**Сайт:** [английская страница](https://belyaevad.github.io/enclosure-fab/) · [русская страница](https://belyaevad.github.io/enclosure-fab/ru/)

## Установка

Колёса CadQuery 2.8 рассчитаны на CPython 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fab.py preview fixtures\demo_round.yaml
```

Файл `PREVIEW-*` — не разрешение на печать. 3MF открывают в Bambu Studio как геометрию. Не запускайте `pip install -U`: незакреплённые VTK, Numba и NumPy уезжают вместе и меняют предпросмотр.

## Примеры

Каждая команда пишет файлы в `.work/generated/preview/`. Имя начинается с `PREVIEW-`. В слайсер открывают `.3mf`.

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\fab.py preview fixtures\demo_rect.yaml
& $py scripts\fab.py preview fixtures\demo_round.yaml
& $py scripts\fab.py preview fixtures\demo_shell.yaml
& $py scripts\fab.py preview fixtures\demo_tray.yaml
```

| Фикстура | Шаблон | Что должно получиться |
|---|---|---|
| `fixtures/demo_rect.yaml` | `enclosure_box` | Небольшая коробка, около 25×17×12 мм, одно окно на грани +X. |
| `fixtures/demo_round.yaml` | `enclosure_round` | Цилиндр Ø40 мм, высота 18 мм, крышка 2 мм с шестью отверстиями Ø3 мм. |
| `fixtures/demo_shell.yaml` | `enclosure_shell` | Кожух вокруг габарита 40×30×16 мм. Крышка на винтах, не на защёлке. |
| `fixtures/demo_tray.yaml` | `enclosure_tray` | Лоток 100×80×20 мм внутри, карманы, открытый колодец, отдельная крышка. |

Числа выдуманы. Перед `print` их заменяют своим обмером. `usb.offset_mm.z` — центр кожуха разъёма от низа платы.

Рецепты: [docs/patterns.md](docs/patterns.md).

Навык для агента на английском: [SKILL.md](SKILL.md). Русский перевод, который клиент сам не подключает: [SKILL.ru.md](SKILL.ru.md).

Лицензия MIT. Copyright (c) 2026 BelyaevAD.
