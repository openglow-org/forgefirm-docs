---
title: Cameras
---

# Cameras

This page describes the two cameras as hardware: where they are, how they share
one path into the board, which sensor a machine carries, and what each sensor
can do. What ForgeFIRM actually sends (the stream choices, the encoding, how
one camera path is shared) is on
[the video pipeline](../forgefirm/video-pipeline.md); how to watch the cameras,
and the lid rule that governs every capture, is on
[Cameras](../../usage/cameras.md).

## What the hardware is

The machine has two cameras: one in the lid looking down at the bed, one in
the print head looking at the material under the lens. The two cameras carry
the same kind of sensor and feed one shared path into the board. A **hardware
MIPI switch** (the factory `CAM_SEL` line) selects which of them reaches the
board's single camera receiver, so **exactly one camera can be capturing at any
moment**. That is a property of the board, not a software limit: there is no
configuration in which both stream at once. The switch's output enable is
exposed as an LED-class device (`/sys/class/leds/camera_mux_oe`; see
[the kernel module](../forgefirm/kernel-module.md)).

| | Lid camera | Head camera |
|---|---|---|
| Sees | the whole bed, from above | the material directly under the lens |
| Its lamp | the lid LED strip | the white LED in the print head |
| Used for | bed view, camera-referenced homing, LightBurn's camera overlay | focus and material inspection (cloud mode's distance measurement) |

The lid lens is a wide fisheye.

Which sensor is fitted depends on the machine. Standard machines carry a **5 MP
OV5648**; "HD" machines carry an **8 MP OV8856**. Both sensors share one
device-tree node (see [Buses](buses.md)). ForgeFIRM reads which one bound and
configures itself accordingly (one firmware image covers both) and reports it
in `/cam/status` and on the panel's Status tab.

The cameras only capture with the lid closed. That rule, and every way it is
enforced, is on [Cameras](../../usage/cameras.md).

## What the sensors can do

This section is what the parts can do. What ForgeFIRM asks of them, and why
it asks for less, is on
[the video pipeline](../forgefirm/video-pipeline.md#what-forgefirm-sends-and-why-it-is-less-than-the-sensor-can-do).

| | The sensor can |
|---|---|
| Live resolution | its full frame |
| Frame rate (5 MP) | 30 fps in its reduced modes, 15 fps at full field |
| Resolution (8 MP) | 3280 × 2464 |
| Bit depth | 10 bits per pixel |
| Exposure and color | auto exposure and auto white balance |
| Mirroring | a mirror register |

Three of those the board takes away rather than ForgeFIRM: the receiver
cannot take the 8 MP sensor's widest frame at 10 bits, the mirror register
breaks capture, and only one camera can be capturing at a time. Those are
below.

### Resolution and frame rate on a 5 MP machine

The OV5648 offers several modes, and they are not simply "the same picture,
smaller":

| Mode | Rate | Field of view |
|---|---|---|
| 2592 × 1944 | 15 fps | the whole sensor |
| 1920 × 1080 | 15 fps | a crop from the middle |
| 1600 × 1200 | 15 fps | a crop from the middle |
| 1280 × 960 | 30 fps | the whole sensor, every other pixel |
| 1280 × 720 | 30 fps | a crop, every other pixel |
| 640 × 480 | 30 fps | the whole sensor, every fourth pixel |

The cropped modes are unusable for a bed camera: they would show the middle of
the bed and cut off the corners. That leaves a real choice of two, the
full-frame mode at 15 fps or the skipped 1280 × 960 mode at 30 fps, and
ForgeFIRM takes the first
([the video pipeline](../forgefirm/video-pipeline.md#what-forgefirm-sends-and-why-it-is-less-than-the-sensor-can-do)).

### 8 MP ("HD") machines: a few rows short of the full array

The OV8856's largest frame is 3280 × 2464. ForgeFIRM captures **3264 × 2448**,
which is 16 columns and 16 rows less: the whole field of view, edge to edge,
just without the last few pixels of margin.

Getting there is not free. The sensor can send its full frame over the two data
lanes this board wires, but at 10 bits per pixel that means running the link at
**1.44 Gbit/s per lane**, and the i.MX6's camera receiver tops out at
**1 Gbit/s per lane**: it has no timing setting for anything faster, so it
refuses the mode outright. Asking the sensor for 8-bit pixels instead cuts a
fifth off every sample and lets the same frame travel at half the rate, which
the receiver takes comfortably. That is how an HD machine gets its full
resolution, and it costs nothing, because the delivered JPEG was going to be
8-bit anyway.

The result is about 15 frames per second off the sensor, and roughly the same
bytes per second across the bus as a 5 MP machine at its own full frame.

### The mirror register breaks capture

Both sensors carry a mirror register that would flip the image horizontally
for free. **Setting it breaks the board's capture path**: frames stop
completing altogether. The flip is done in software instead, while the image
is being demosaiced, at a negligible cost and with an identical result.

### One consequence for 8 MP color

The OV8856's driver publishes no red or blue balance controls at all, so an
8 MP machine's images are less color-correct than a 5 MP machine's. Its
exposure and gain values are untested on real hardware.

## Status of 8 MP ("HD") machines

Everything an 8 MP machine needs is in the firmware: the kernel patches for the
OV8856, including the 8-bit full-resolution mode described above, the
device-tree entries, and a capture path that picks its geometry and sensor
controls from whichever sensor bound.

**None of it has run on an 8 MP machine.** No such unit has been available to
test against, so treat 8 MP support as untested rather than working: whether
the receiver locks onto the full-resolution mode, and what exposure and gain
the sensor actually wants, can only be settled on that hardware. The frame-rate
and CPU figures on [Cameras](../../usage/cameras.md) are from a 5 MP machine
and do not carry over: an HD machine demosaics 60 % more pixels per frame.
Reports from anyone with an HD machine are welcome.

The 5 MP path is hardware-validated and in daily use.
