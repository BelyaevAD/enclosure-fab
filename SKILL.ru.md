# enclosure-fab

Русская версия [SKILL.md](SKILL.md). Клиенты читают английский файл. Этот файл для человека, и разделы в нём те же.

Ты правишь YAML-спеку. Модуль шаблона в `fabkit/` строит тело. 3MF открывает человек в слайсере.

## Установка

Пути считаются от корня клона enclosure-fab. Если есть только скилл, сначала склонируй репозиторий:

```text
git clone https://github.com/BelyaevAD/enclosure-fab.git
cd enclosure-fab
py -3.12 -m venv .venv                                    # Linux, macOS: python3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux, macOS: .venv/bin/python
```

CLI запускается так: `.venv/Scripts/python scripts/fab.py` (на Linux и macOS — `.venv/bin/python`). Интерпретатор — только CPython 3.12. Колёса CadQuery собраны под него, и `fabkit/runtime.py` останавливается на другой версии. Не запускай `pip install -U`: VTK, Numba и NumPy поднимутся вместе, и геометрия может измениться.

## Слова

- **Спека** — YAML-файл. Миллиметры в ней — размер детали. Зазор добавляет шаблон.
- **Fit-critical поле** — размер, от которого зависит посадка. `fab.py protocol --family <family>` перечисляет такие поля и говорит, как мерить.
- **confirmed** — `true` только после замера человеком. Ты это поле не ставишь.
- **Keep-out** — объём, в который деталь не должна входить, например компоненты на плате.
- **preview** — работает с предполагаемыми размерами. Имена файлов начинаются с `PREVIEW-`.
- **print** — работает, только когда все fit-critical поля подтверждены и ничего не входит в keep-out.

## Маршрут

1. Выбери шаблон по таблице и скопируй его фикстуру из `fixtures/`.
2. `fab.py protocol --family <family>` — что мерить. Фото — заметка, не миллиметры.
3. `fab.py validate <spec>` — исправь ошибки и прочитай предупреждения.
4. `fab.py preview <spec>` — пишет файлы в `.work/generated/preview/` или в `-o <dir>`.
5. Проверь результат (следующий раздел), прежде чем сказать, что деталь в порядке.
6. `fab.py print <spec>` — только после того, как человек подтвердил fit-critical поля. При пересечении keep-out файла нет.
7. Назови человеку путь к 3MF. В слайсере его открывает он.

| template_id | Фикстура | Fit-critical поля |
|---|---|---|
| `enclosure_box` | `demo_rect` | `board.*`, `usb.offset_mm.*`, `usb.opening_wh_mm.*`, `keepout.board` |
| `enclosure_snap` | `demo_snap` | те же, что у `enclosure_box` |
| `enclosure_round` | `demo_round` | нет; размеры корпуса и есть деталь |
| `enclosure_shell` | `demo_shell` | `device.*`, `keepout.device`, `shell.sma.*` |
| `enclosure_tray` | `demo_tray` | `tray.inner_*`, `pockets.*`, `keepout.tray` |
| `enclosure_magnet_box` | `demo_magnet_box` | `box.outer_*`, `box.magnet_*`, `keepout.box` |
| `ring_yoke` | `demo_ring_yoke` | `rings.band_mm`, оба `circumference_mm` и `mouth_mm`, `keepout.bores` |
| `strip_clip` | `demo_strip_clip` | размеры `clip.*`, `keepout.pocket` |
| `doll_mary_jane` | `demo_doll_shoe` | `shoe.*`, `keepout.foot` |

`usb.offset_mm.z` — центр кожуха разъёма от низа платы.

## Ответ после preview

Первая строка — `NOT_FOR_PRINT`. Дальше блок свежести из вывода `fab.py preview`, путь к 3MF и поля, которые ещё надо измерить:

```text
NOT_FOR_PRINT
generated_at: 2026-11-05T17:08:46Z
3mf: PREVIEW-demo_ring_yoke-ring_yoke.3mf  252174 bytes  2026-11-05T17:08:43Z
stale_siblings: (none)
Measure before print: rings.band_mm, rings.bar.circumference_mm, ...
```

## Проверка

- `generated_at` — из этого запуска, и время 3MF с ним совпадает. Старый файл — остаток, не твой результат.
- Посмотри `*-assembled.png` и `*-print.png`. Картинка печати — подсказка. Человек всё равно разворачивает детали в слайсере, поэтому не называй файл готовым к столу.
- Отверстие проходит стенку насквозь и оставляет над и под собой около трёх линий (1.26 мм).
- Каждая деталь — одно тело. Стенка внутри отверстия в слайсере — остаток грани: правь шаблон и не проси человека чинить меш.
- Читай `warnings` в JSON. Пересказывай те, что влияют на посадку.

## MCP-сервер

`mcp/server.py` — stdio-сервер `fab` с теми же гейтами, что у CLI. Инструменты: `list_templates`, `list_boards`, `list_primitives`, `measurement_protocol`, `validate_spec`, `generate_preview`, `generate_print`, `explain_last_gate`. Сервер загружает `fabkit` один раз. После правки `fabkit/` клиент должен перезапустить сервер, а до тех пор работай через CLI.

## Нельзя

- Писать сырой CadQuery в чат. Меняй спеку или шаблон в `fabkit/`.
- Ставить `confirmed: true` или запускать `fab.py confirm --i-measured`. Это шаг человека после замера.
- Запускать принтер, открывать слайсер, добавлять настройки слайсера.
- Придумывать шаблон, когда есть близкая фикстура. Копируй фикстуру.
- Править файлы в `.work/`. Это вывод.
