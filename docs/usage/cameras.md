---
title: Cameras
---

# Cameras

The machine has two cameras, one in the lid and one in the print head
([The cameras](../technical/machine/cameras.md)). ForgeFIRM serves both over
plain HTTP from the web control panel: **MJPEG** for anything that can read a
stream of JPEGs, and an **H.264** live stream for clients that decode video
(the panel uses it when the browser can). There is no app, no cloud relay, and
no proprietary protocol. This page tells you the one rule that governs the
cameras, how to watch them, and what you get.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

The sensors, what they can do, and the 8 MP status are in
[The cameras](../technical/machine/cameras.md). The pipeline, the lighting, the
camera-path sharing, and why the image looks the way it does are in
[The video pipeline](../technical/forgefirm/video-pipeline.md).

## The cameras only work with the lid closed

**Neither camera captures anything while the lid is open.** Not the live view,
not a snapshot, and not an image requested in cloud mode. Close the lid and
everything works; open it and the sensors stop. The lid camera is mounted in
the lid, so raising it swings the camera up to face the room; the enclosure
being shut is the condition for an image to exist at all.

The rule covers both cameras and every way in: the panel, `/cam/stream`,
`/cam/snapshot`, the mjpg-streamer aliases, LightBurn, and cloud mode's image
actions. A stream already running ends within about a frame. A refused capture
never raises the lamps.

| Situation | What happens |
|---|---|
| Snapshot or stream requested with the lid open | `409` naming the lid; no image data |
| Lid opened while a stream is running | the stream ends cleanly and the pipeline is torn down |
| Lid state unreadable | treated as open: capture refused |
| Cloud service asks for an image with the lid open | refused, and reported back as a failed action rather than left hanging |
| Lid closed again | everything works immediately; nothing to restart |

`GET /cam/status` reports it: **`capture_allowed`** is false whenever the lid is
open, and **`stopped_by_lid`** records that the last capture ended because the
lid opened rather than going idle. The panel's Status tab says *lid open, the
cameras are off* rather than showing a stream error.

The lid signal is the same one the hardware safety chain uses to gate the beam,
the series combination of both lid switches, and the check **fails closed**: if
the lid state cannot be read, the cameras stay dark.

It is a rule enforced by the two programs that own the sensors, not a hardware
cut-off - the sensor rails stay powered, and root on the machine can bypass it.
There is deliberately no setting to turn it off.

## Watching it

**In the panel.** Open `https://<machine-ip>/`
and go to the **Status** tab.
The *Lid camera* card shows a still by default with **Live** and **Refresh**
buttons; **Live** switches the same frame to the running stream (H.264 when the
browser supports it, MJPEG otherwise), and **Stop** returns to the snapshot.

**From another program.** The endpoints are:

| URL | What it returns |
|---|---|
| `/cam/stream?cam=lid` | continuous MJPEG (`multipart/x-mixed-replace`) |
| `/cam/stream?cam=head` | the same, from the head camera |
| `/cam/h264?cam=lid` | continuous H.264 as fragmented MP4: the same picture in a fraction of the bytes, for clients that decode video |
| `/cam/snapshot?cam=lid` | one full-resolution JPEG |
| `/cam/snapshot?cam=lid&res=half` | one half-resolution JPEG (much faster) |
| `/cam/snapshot?cam=lid&background=1` | the same, but refused with 409 while somebody is watching a camera |
| `/cam/snapshot?cam=lid&q=1..100` | a JPEG at the given quality |
| `/cam/status` | JSON: which sensor, which camera, frame rate, frame sizes, whether the lid currently permits capture |
| `/?action=stream` | the lid stream again, under the name mjpg-streamer clients expect |
| `/?action=snapshot` | one full-resolution lid JPEG, same aliasing |

The `?action=` pair exists because a lot of software (print-server dashboards,
camera widgets, anything written against mjpg-streamer) assumes those exact
URLs. Point such a client at `http://<machine-ip>/` and it works.

Every one of them answers **`409`** with the lid open, so a client that checks
status codes can tell "close the lid" apart from "the camera is broken".

**Access.** Reading the camera needs no login by default. The read-only
routes answer any client on your network, over plain HTTP on port 80 or
over HTTPS. A browser request must not be cross-site; that is what stops a
hostile page in another tab from reaching into your machine. The setting
`panel_open_reads=0` closes the reads to logged-in sessions and the machine
itself ([Settings](settings.md)). Anything that *changes* machine state
needs a login ([The control panel](control-panel.md#access)).

**The camera key.** A program with no login, LightBurn or a stream viewer,
reads the cameras with the machine's camera key. Press **Camera URL** on
the Status tab's lid camera card: the panel shows the stream and snapshot
URLs with the key in them, ready to paste. The key is a `key` query
parameter, or the `X-ForgeFIRM-Camera-Key` header, on any read-only route,
over HTTP or HTTPS, with the reads open or closed. It authorizes reads and
nothing else. **New key** on the same card makes a fresh one; every URL that
carried the old key stops working. Treat the URL as a password for the
camera image.

**LightBurn** consumes the lid stream for its camera overlay while it drives
motion over the Grbl connection; the two coexist.

## What you get

| | 5 MP machine (OV5648) | 8 MP machine (OV8856) |
|---|---|---|
| Sensor frame captured | 2592 × 1944 | 3264 × 2448 |
| Live stream | 1296 × 972 | 1632 × 1224 |
| Full snapshot | 2592 × 1944 | 3264 × 2448 |
| Half snapshot | 1296 × 972 | 1632 × 1224 |
| Stream formats | MJPEG (quality 75 by default) and H.264 (about 1.5 Mbit/s by default) | same |
| Frame rate | **15 fps** sustained | not measured; no 8 MP machine has been tested ([The cameras](../technical/machine/cameras.md)) |

Measured on a 5 MP machine: 15.0 fps with a viewer attached, which is the rate
the sensor itself produces in this mode; the machine is not the bottleneck. With
the NEON demosaic feeding the hardware JPEG encoder, the daemon uses about 41 %
of one CPU with one viewer, and LightBurn can watch the stream while jogging
from the same session without disturbing motion. With the GPU demosaic feeding
the H.264 stream, the stream's CPU cost drops to bookkeeping: about 14 % of
the CPU for one viewer. A full-resolution still takes about 2.4 s to produce
(2.7 s if the camera has to be started first), because 5 megapixels of
demosaicing and JPEG encoding happen on the machine's CPU.

The live view is exactly half the capture in each axis because each 2 × 2
group of sensor pixels becomes one output pixel, rather than the frame being
scaled down. That is what makes it cheap enough to run continuously
([The video pipeline](../technical/forgefirm/video-pipeline.md#what-forgefirm-sends-and-why-it-is-less-than-the-sensor-can-do)).

The image is the sensor's data, demosaiced and encoded, with fixed exposure
and no tone curve; compared with a phone photo it looks flat, and that is
expected. Nothing is recorded on the machine: if you want a recording, record
the stream on the computer watching it
([The video pipeline](../technical/forgefirm/video-pipeline.md)).

## When something looks wrong

**No picture at all, and a 409 mentioning the lid.** Working as intended: the
lid is open. Close it. `/cam/status` shows `capture_allowed: false` while that
is the case. If the lid *is* shut and you still see this, one of the two lid
switches is not making, the same condition that would stop the laser firing,
so it is worth investigating rather than working around.

**A black or nearly black picture.** The scene is not lit: the exposure is
fixed, so the camera cannot compensate. Check the `lid_lamp_idle` setting
([Settings](settings.md)), and remember snapshots can carry their own
`lamp=0..1023` level for one image.

**The stream stops on its own.** Either the lid opened (the panel says so), or
someone else (another browser tab, LightBurn, the panel) asked for the other
camera, or for a stream, and preempted yours. Reload; the panel does this
automatically and says which it was.

**"camera switch timed out".** A viewer would not let go within the grace
period. Close the other viewer and retry.

**A snapshot returns 503.** The camera could not start. The usual cause is
another process holding the capture device; the daemon's log names the failing
step ([Logging](logging.md)).

**`/cam/status` reports `"sensor": "unknown"`.** No camera was found on that
bus, or a sensor bound that this firmware has no profile for. On an 8 MP
machine see [The cameras](../technical/machine/cameras.md).
