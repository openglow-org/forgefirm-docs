---
title: Visual alignment
---

# Visual alignment

Visual alignment is an official extension package (`org.openglow.alignment`).
It shows the head camera's live video with a crosshair on the spot where the
laser will hit. You put the crosshair on the spot where your job starts, by
jogging the head or by sliding the material, and press **Done**. The laser is
then on that spot, and you start the job from the current position in your
Grbl sender.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../../safety/index.md)
    before you run a job.

It is a package like any other ([Extensions](index.md)): a page on the
panel's **Extensions** tab, and a service on the machine that does the work.

## Installing it

Get it from the [catalog](index.md#the-catalog) on the **Extension
packages** card. You can also upload `org.openglow.alignment-<version>.ffx`
from the releases of its repository,
[openglow-org/forgefirm-extension-alignment](https://github.com/openglow-org/forgefirm-extension-alignment/releases).
Either way it reads as **Official**. It asks to:

| Capability | For |
|---|---|
| Read the machine's status | the position and the state above the video |
| Use the head camera | the video |
| Jog the head, laser off | the tool's moves and the jog pad |
| Keep settings of its own | its calibration and your choices (below) |
| Keep the Grbl sender out | the time the tool is in use (below) |
| Run a program as the machine's one sender | the calibration mark only |

The last two are yours to grant: tick both when you install it, or the
install is refused.

## Using it

1. Open the **Extensions** tab and press **Use the alignment tool**. The
   machine must be idle.
2. The head moves about 25 mm, slowly, so the camera is over the spot where
   the laser will hit. The video starts.
3. Put the red crosshair on the spot where the job starts. Jog with the pad
   or the arrow keys, or open the lid and slide the material. Up is toward
   the back of the machine, as in the video. The step is 0.1, 1, 5, or
   10 mm.
4. Press **Done: put the laser on the crosshair**. The head moves back by
   the same distance, and the laser is on the spot.
5. In your Grbl sender, connect again and start the job from the current
   position. In LightBurn, that is **Start From: Current Position**.

**Light** sets the head's own light for the video, from 0 to 1023. On the
bench reference, about 60 shows the grain of light wood and 1023 turns it
white. The level you set is kept.

The head camera works with the lid open, so you can watch while you place
the material. It looks straight down at the bed, and it is the only camera
that does; the lid camera still stays off with the lid open
([Cameras](../cameras.md)).

### Your Grbl sender is disconnected while you use it

While the tool is in use, the head stands about 25 mm from where the laser
will hit. A job started then would land in the wrong place. So the machine
disconnects your Grbl sender when you press **Use the alignment tool**, and
it refuses to let a sender connect until you press **Done**. Your sender
shows the message *The machine is in use: senders are kept out for now*.
Connect again after **Done**.

The tool starts only when the machine is idle and the sender is not
sending. If a job is running, or the sender just sent something, wait and
try again.

The panel shows a banner while the tool keeps the sender out. **Let the
sender back in** ends it at once. The tool then moves the head back, as
**Done** does; wait for that before you start a job.

### If the page closes

The tool runs on the machine, not in your browser. If the page closes, the
browser crashes, or you switch the panel to another tab, the tool waits about 10
seconds and then finishes by itself: **the head moves back** so the laser is
on the spot the crosshair marked, and the sender is let back in. A browser tab
left in the background for several minutes counts too, because the browser
then slows the page down. **Keep your hands out of the machine while the tool
is in use**, since the head can move when you are not pressing anything.

If the tool itself stops while it is in use (for example, you turn the
package off), the head does not move. The panel then shows a notice that
names the package. Check where the laser is before you start a job. If the
tool starts again within two minutes, it finishes the use: the head moves
back and the notice goes away.

The jogs and the tool's own moves never fire the laser. The tool's own
moves run at 10 mm/s.

## The crosshair

The video is what the camera sees. Nothing in it is corrected, stretched,
or moved: only the crosshair is drawn over it. The crosshair has a tick at
each millimeter to 5 mm and a ring at 10 mm. The ticks and the ring follow
the **material height** that you type, because the camera sees a surface
closer to it as larger. The height changes nothing else: the crosshair's
center is correct at any height.

## Calibration

The camera is beside the laser, not over it. On the bench reference the
laser hits about 24.6 mm to the right of the camera's center, at every
material height. The tool starts with that value, and a calibration
measures it on your machine. Calibrate once, and again after the head is
removed or replaced.

The calibration burns a small mark, so it is a laser job and every gate of
a job applies.

1. Put scrap material under the head and close the lid.
2. Open **Calibration** and press **Burn the mark**. Press the button on the
   machine when it lights. The mark is a plus sign 3 mm wide, burned where
   the laser is.
3. The head moves so the camera sees the mark.
4. Drag the blue crosshair onto the center of the burned plus, then nudge
   it by one or ten pixels.
5. Press **Jog to the blue crosshair**. Repeat 4 and 5 until the burned plus
   sits under the red crosshair.
6. Press **It lines up: save**. The tool is then in use as usual, and
   **Done** puts the laser back on the mark.

What is kept is the difference between two positions of the head: where it
stood when the mark was burned, and where it stands when the mark is under
the crosshair. Nothing is kept in pixels. A wrong material height costs one
more pass, never accuracy, because the calibration ends on what the camera
shows at its center.

If the arms of the burned plus are not parallel to the crosshair's, the
camera is turned a little in the head. The alignment is still correct at
the crosshair's center, and the tool does not try to correct the picture.

## Its settings

The tool keeps these as its own settings, and they stay across an update
of the package.

| Setting | Default | What it is |
|---|---|---|
| `offset_x_mm`, `offset_y_mm` | 24.6, 0 | The camera-to-laser offset, from the calibration |
| `calibrated` | false | Whether the offset was calibrated on this machine |
| `lamp` | 60 | The head light for the video, 0 to 1023 |
| `height_mm` | 3 | The material height, for the crosshair's scale only |
| `burn_power` | 20 | The calibration mark's power, in percent |
| `burn_feed` | 600 | The calibration mark's speed, in mm/min |
| `jog_feed` | 3000 | The speed of the jog pad, in mm/min |

How a package keeps the sender out, and how it ends when the package
stops, is in
[A package keeps the Grbl sender out](../../technical/forgefirm/extensions.md#a-package-keeps-the-grbl-sender-out).
