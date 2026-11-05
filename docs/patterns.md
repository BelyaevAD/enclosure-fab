# Patterns

These recipes start from the fixtures in this repo. Copy one and change the numbers. The numbers are not measurements of a real part.

## Rectangular box

`fixtures/demo_rect.yaml`, template `enclosure_box`. A small box with one opening on the +X face. `usb.offset_mm.z` is the connector-shell centre measured from the bottom of the board. The template adds clearance. The opening in the spec is the part size.

## Snap-fit case

`fixtures/demo_snap.yaml`, template `enclosure_snap`. A base and a lid that snap together: a groove in the long walls, a bead on the lid skirt, corner posts under the board, a USB window on +X. Roof slots let warm air out; slots on −X let air in. Keep at least three lines (1.26 mm) of wall above the USB window, or the slicer drops it. `press_board: false` leaves the lid without pads, so a tall connector is not pressed.

## Round pot with a vented lid

`fixtures/demo_round.yaml`, template `enclosure_round`. A cylinder, a separate lid, and round holes through the lid. The preview places the lid beside the pot so both can be sliced. The assembled picture shows the lid on top.

## Device shell

`fixtures/demo_shell.yaml`, template `enclosure_shell`. A shell around a rectangular outline, with a screw lid rather than a snap as the only latch. Measure the real outline before you treat a file as ready to print.

## Tray

`fixtures/demo_tray.yaml`, template `enclosure_tray`. Several pockets and an open bay. The lid is a separate solid. Turn it in the slicer yourself. This file does not decide how the parts lie on the bed.

## Magnet box

`fixtures/demo_magnet_box.yaml`, template `enclosure_magnet_box`. A closed box with a full lid. Four corner posts carry disc magnets; the lid has bosses that hang down onto them. The outer size includes the lid. Print the base and the lid separately.

## Two rings in one plate

`fixtures/demo_ring_yoke.yaml`, template `ring_yoke`. Two C-rings lie in one flat plate, so the part prints flat. The mouths open toward −X and +X. The circumference is the pipe you clip onto. If a trial print runs large, shrink the circumference, not the wall.

## Channel clip

`fixtures/demo_strip_clip.yaml`, template `strip_clip`. One channel with two teeth and a hole in the top bar. The 3MF lies on its side, and the hole is a teardrop so it prints without support. The body slides in at an angle under the teeth. Do not go back to one tooth.

## Doll shoe

`fixtures/demo_doll_shoe.yaml`, template `doll_mary_jane`. A shoe shell around a doll's foot, a strap, and a C-clip at the ankle. The preview has a right shoe and a mirrored left shoe. The foot sizes are the doll; the template adds `gap_mm` per side.

## Preview and print

`preview` is fine while the sizes are still a guess. The file name starts with `PREVIEW-`. `print` waits until the sizes that decide the fit are confirmed. If a keep-out cuts through the part, the print files are removed.
