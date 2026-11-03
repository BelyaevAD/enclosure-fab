# Patterns

These recipes use the fixtures in this repository. Copy a fixture and change the numbers. Do not treat a fixture as a measured part.

## Rectangular box

`fixtures/demo_rect.yaml`, template `enclosure_box`. A small box with one opening on the +X face. `usb.offset_mm.z` is the connector-shell centre measured from the bottom of the board. The template adds clearance. The opening in the spec is the part size.

## Round pot with a vented lid

`fixtures/demo_round.yaml`, template `enclosure_round`. A cylinder, a separate lid, and round holes through the lid. The preview places the lid beside the pot so both can be sliced. The assembled picture shows the lid on top.

## Device shell

`fixtures/demo_shell.yaml`, template `enclosure_shell`. A shell around a rectangular device envelope, with a screw lid rather than a snap as the only latch. Measure the real envelope before you call a file ready to print.

## Tray

`fixtures/demo_tray.yaml`, template `enclosure_tray`. Several pockets and an open well. The lid is a separate solid. Turn it in the slicer yourself. This file does not set a print pose for you.

## Preview and print

`preview` is allowed while millimetres are still assumed. The file name starts with `PREVIEW-`. `print` refuses until fit-critical fields are confirmed. A keep-out solid that intersects the part deletes the print files.
