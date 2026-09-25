---
title: Visual alignment
---

# Visual alignment

Visual alignment is an official extension package (`org.openglow.alignment`).
It adds a page to the panel with the head camera's view, a crosshair at the
center of that view, and a jog pad beside it. You jog the head until the
crosshair is on the spot where the job must start, and one button then moves
the beam to that spot. In LightBurn you start the job from **Current
Position**.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../../safety/index.md)
    before you run a job.

It is a package like any other ([Extensions](index.md)): it runs in the
panel's sandboxed frame and reaches the machine only through the panel. It
does not run on the machine at all.

## Installing it

Get it from the [catalog](index.md#the-catalog) on the **Extension
packages** card. You can also upload `org.openglow.alignment-<version>.ffx`
from the releases of its repository,
[openglow-org/forgefirm-extension-alignment](https://github.com/openglow-org/forgefirm-extension-alignment/releases).
Either way it reads as **Official**. It asks to:

| Capability | For |
|---|---|
| Read the machine's status | the position and the state above the view |
| Take pictures with the head camera | the view |
| Jog the head, laser off | the jog pad and the move to the crosshair |
| Keep settings of its own | its calibration and your choices (below) |
| Run a program as the machine's one sender | the calibration mark only. Tick it if you calibrate on this machine |

Then press **Open** beside the package in the card.

## Using it

1. Close the lid. The cameras do not take a picture while the lid is open.
2. Press **New picture**, or tick **Live** for a new picture every few
   seconds.
3. Jog with the pad or the arrow keys until the red crosshair is on the
   spot where the job starts. Up is toward the back of the machine, as in
   the picture. The step is 0.1, 1, 5, or 10 mm.
4. Press **Move the beam to the crosshair**. The head moves by the
   camera-to-beam offset, and the beam is now over that spot.
5. In LightBurn, start the job from **Current Position**.

LightBurn can stay connected while you look and jog. A line that LightBurn
sends ends a jog of this page at once, because the sender always has
priority. The jog never fires the laser. **It is still motion: keep your
hands out of the machine while the page is open.**

**Light** sets the head's own light for each picture, from 0 to 1023. On
the bench reference, about 60 shows the grain of light wood and 1023 turns
it white. The level you set is kept.

## The crosshair

The picture is what the camera sees. Nothing in it is corrected, stretched,
or moved: only the crosshair is drawn over it. The crosshair has a tick at
each millimeter to 5 mm and a ring at 10 mm. The ticks and the ring follow
the **material height** that you type, because the camera sees a surface
closer to it as larger. The height changes nothing else: the crosshair's
center is correct at any height.

## Calibration

The camera is beside the beam, not over it. On the bench reference the beam
lands about 24.6 mm to the right of the picture's center, and at the same
distance at every surface height. The page starts with that value, and a
calibration measures it on your machine. Calibrate once, and again after the
head is removed or replaced.

The calibration burns a small mark, so it is a laser job and every gate of
a job applies.

1. Put scrap material under the head and close the lid. Disconnect
   LightBurn: a job cannot start while a sender is connected.
2. Press **Burn the mark**, and press the button on the machine when it
   lights. The mark is a plus sign 3 mm wide, burned where the head stands.
3. Press **Show the mark**. The head moves by the offset the page knows, so
   the mark comes into the picture.
4. Drag the blue crosshair onto the center of the burned plus, then nudge it
   by one or ten pixels.
5. Press **Jog to the blue crosshair**. A new picture follows. Repeat 4 and
   5 until the burned plus sits under the red crosshair.
6. Press **It lines up: save**.

What is kept is the difference between two positions of the head: where it
stood when the mark was burned, and where it stands when the mark is under
the crosshair. Nothing is kept in pixels. A wrong material height costs one
more pass, never accuracy, because the calibration ends on what the camera
shows at its center.

If the arms of the burned plus are not parallel to the crosshair's, the
camera is turned a little in the head. The alignment is still correct at the
crosshair's center, and the page does not try to correct the picture.

## Its settings

The page keeps these as its own settings, and they stay across an update of
the package.

| Setting | Default | What it is |
|---|---|---|
| `offset_x_mm`, `offset_y_mm` | 24.6, 0 | The camera-to-beam offset, from the calibration |
| `calibrated` | false | Whether the offset was calibrated on this machine |
| `lamp` | 60 | The head light for a picture, 0 to 1023 |
| `height_mm` | 3 | The material height, for the crosshair's scale only |
| `burn_power` | 20 | The calibration mark's power, in percent |
| `burn_feed` | 600 | The calibration mark's speed, in mm/min |
| `jog_feed` | 3000 | The speed of every jog, in mm/min |

How the page reaches the machine through the panel is in
[A package's own page](../../technical/forgefirm/extensions.md#a-packages-own-page).
