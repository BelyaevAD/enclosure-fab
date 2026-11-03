# Примитивы корпуса

Канон **живой геометрии** — `fabkit/` (CadQuery). Этот каталог **называет** детали, чтобы агент копировал готовое, а не выдумывал язычок/сетку и не тащил OpenSCAD в git.

Машина читает [`catalog.yaml`](catalog.yaml): MCP **`list_primitives`** / CLI `fab.py list-primitives`.

## Правило

1. Перед новой кнопкой, сеткой, колодцем, окном USB — `list_primitives`. Есть `live: true` — копировать эталон и паттерн.
2. `live: false` — имя есть, резак ещё не режет, запрещён, или снят живым эталоном. Не подменять окнами.
3. **Не** git-submodule BOSL2 / YAPP_Box / NopSCADlib и не класть `.scad` в шаблон. ADR 047: одно ядро CadQuery. Рецепт — pin в [`../upstream/`](../upstream/), реализация — `fabkit/`.
4. Чужой CadQuery-генератор (`cq_enclosure_builder`, Shellforge) — конкурирующая коробка, не библиотека деталей для `enclosure_snap`. Украсть приём, не подменять обвязку.

## Язычок vs бобышка vs перемычка

| Имя | YAML / код | Что это |
|-----|------------|---------|
| Язычок | `button.style: flex_tab` | Один квадратный U в стоячей стенке (две щели + вертикаль 0.8), шарнир вертикальный |
| Бобышка | `nub_mm` | Площадка **внутрь** на шток кнопки |
| Усы | `tie_mm` / `flex-tab-ties` | Перемычки **в щели** на печать; оператор срезает. Отчёт `button_tie_along_mm` |

Слайсерные поддержки в щели язычка не ставить: шрам на рабочей грани (Sovol print-in-place).

## Живые сейчас

`flex-tab`, `flex-tab-ties`, `grid-45`, `usb-window`, `header-pin-well`, `shed-slot`, `roof-bed-well`, `window-horizontal`, `teardrop-hole`, `gland-bore`, `heat-set-m3`, `hv-partition`, `sma-well`, `open-well`, `mouse-hole`, `floor-mount`, `magnet-cup`, `magnet-corner`, `rest-strip`, `c-ring`.

Имена без резака: `louver-45`, `honeycomb`, `gable-slot`. Запрет: `rim-crenel`. Ромб-кнопка (dec-006) снята.
