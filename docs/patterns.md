# Patterns

These recipes start from the fixtures in this repo. Copy one and change the numbers. The numbers are not measurements of a real part.

## Rectangular box

`fixtures/demo_rect.yaml`, template `enclosure_box`. A small box with one opening on the +X face. `usb.offset_mm.z` is the connector-shell centre measured from the bottom of the board. The template adds clearance. The opening in the spec is the part size.

## Round pot with a vented lid

`fixtures/demo_round.yaml`, template `enclosure_round`. A cylinder, a separate lid, and round holes through the lid. The preview places the lid beside the pot so both can be sliced. The assembled picture shows the lid on top.

## Device shell

`fixtures/demo_shell.yaml`, template `enclosure_shell`. A shell around a rectangular outline, with a screw lid rather than a snap as the only latch. Measure the real outline before you treat a file as ready to print.

## Tray

`fixtures/demo_tray.yaml`, template `enclosure_tray`. Several pockets and an open bay. The lid is a separate solid. Turn it in the slicer yourself. This file does not decide how the parts lie on the bed.

## Two rings and a channel

`ring_yoke` builds two coplanar C-rings. Mouths open on opposite ends. Sizes come from the spec.

`strip_clip` builds one channel with two teeth and a hole in the top bar. The part lies on its side. Sizes come from the spec. Do not go back to one tooth.

## Preview and print

`preview` is fine while the sizes are still a guess. The file name starts with `PREVIEW-`. `print` waits until the sizes that decide the fit are confirmed. If a keep-out cuts through the part, the print files are removed.
