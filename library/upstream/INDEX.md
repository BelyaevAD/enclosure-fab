# Upstream — рецепты, не vendor

Чужие репозитории **не** клонируем в зону. Здесь pin: URL, лицензия, `last-checked`, что украсть, почему не submodule.

Машина: [`pins.yaml`](pins.yaml) (поле `upstream` в `list_primitives`). Агент: этот файл + [`SOURCES.md`](../../SOURCES.md).

## Как обновлять

1. Трогаешь примитив (кнопка, сетка, колодец) — открыть pin и **реально** глянуть URL, обновить `last_checked`.
2. Полезный приём, которого нет в `fabkit/` — строка в [`../primitives/catalog.yaml`](../primitives/catalog.yaml) (`live: false` пока нет резака) **и** рецепт в CadQuery в том же ходе, если оператор просил геометрию.
3. Не `git submodule add` OpenSCAD. Не `pip install cq_enclosure_builder` в venv зоны «вместо» `fabkit`.

## Почему не качаем целиком

| Репо | Почему смотреть | Почему не vendor |
|------|-----------------|------------------|
| [cq_enclosure_builder](https://github.com/raphael-isvelin/cq_enclosure_builder) | CadQuery parts: PBS-кнопки, `air_vent`, layout grid | Другой генератор коробок; кнопки — вырез панели, не язычок в стенке |
| [Parametric_Enclosure](https://github.com/CadQuery/cadquery-contrib/blob/master/examples/Parametric_Enclosure.py) | Разъём коробки на винтах / стойки | Пример, не живой SKU; `device-shell` — `fabkit/enclosure_shell.py` |
| [YAPP_Box](https://github.com/mrWheel/YAPP_Box) | PCB box, маски сот, cutout arrays | OpenSCAD |
| [BOSL2](https://github.com/BelfrySCAD/BOSL2) | Маски, сетки, примитивы | OpenSCAD, огромный |
| [NopSCADlib](https://github.com/nophead/NopSCADlib) | `vitamins/button.scad` | Модели **такт**, не wall flex-tab; OpenSCAD |
| Printables PIP button / Malolos Pi flexure | Tear-away и щель 0.8 на 0.4 | STL, не CQ; их щель часто на столе |

Канон зоны: [ADR 047](../../../../docs/adr/adr-047-3d-fabrication-platform.md) — CadQuery only, no OpenSCAD fallback.
