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

| Фикстура | Что это |
|---|---|
| `fixtures/demo_rect.yaml` | Прямоугольная коробка с окном под USB |
| `fixtures/demo_round.yaml` | Круглая банка, отдельная крышка, шесть отверстий |
| `fixtures/demo_shell.yaml` | Кожух вокруг габарита прибора |
| `fixtures/demo_tray.yaml` | Лоток с открытым колодцем и отдельной крышкой |

Рецепты: [docs/patterns.md](docs/patterns.md).

Навык для агента на английском: [SKILL.md](SKILL.md). Русский перевод, который клиент сам не подключает: [SKILL.ru.md](SKILL.ru.md).

Лицензия MIT. Copyright (c) 2026 BelyaevAD.
