---
title: Cameras
---

# Cameras

The machine has two cameras: one in the lid looking down at the bed, one in the
print head looking at the material under the lens. ForgeFIRM serves both over
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

## Privacy: the cameras only work with the lid closed

**Neither camera captures anything while the lid is open.** Not the live view,
not a snapshot, and not an image requested by the Glowforge service in cloud
mode. Close the lid and everything works; open it and the sensors stop.

The reason is where the lid camera points. It is mounted in the lid, so raising
the lid swings it up to face the room, and in cloud mode the shutter is not
yours to press: the service asks for images on its own schedule, whenever it is
connected. The rule removes the question. The enclosure being shut is the
condition for an image to exist at all.

**What the rule covers**

- **Both cameras.** The head camera is gated too, so this is one rule to
  remember rather than a rule with an exception you have to trust.
- **Every way in:** the panel, `/cam/stream`, `/cam/snapshot`, the
  mjpg-streamer aliases, LightBurn, and cloud mode's image actions.
- **Capture already running.** Opening the lid stops a live stream within
  about a frame and shuts the sensor down; it does not merely block new
  requests.
- **The lamps.** A refused capture never raises them, so an attempt with the
  lid open leaves no trace.

**How it behaves**

| Situation | What happens |
|---|---|
| Snapshot requested with the lid open | `409` and a message naming the lid; no image data |
| Stream requested with the lid open | `409`; the stream never opens |
| Lid opened while a stream is running | the stream ends cleanly and the pipeline is torn down |
| Lid state unreadable | treated as open: capture refused |
| Cloud service asks for an image with the lid open | refused, and reported back to the service as a failed action rather than left hanging |
| Lid closed again | everything works immediately; nothing to restart |

`GET /cam/status` reports it: **`capture_allowed`** is false whenever the lid is
open, and **`stopped_by_lid`** records that the last capture ended because the
lid opened rather than going idle. The panel's Status tab says *lid open, the
cameras are off* rather than showing a stream error.

**Where the check comes from.** The lid signal is the same one the hardware
safety chain uses to gate the beam, the series combination of both lid
switches, not a software flag, and the check **fails closed**: if the lid state
cannot be read at all, the cameras stay dark. A unit test in CI covers that
direction; an acceptance test on real hardware covers the end-to-end behavior.

**One thing it costs.** The factory firmware ran the cloud's focus *hunt* with
the lid open, and part of a hunt is a head capture. Those captures are refused,
so a hunt attempted with the lid open fails instead of completing. Close the
lid before letting the app focus or print ([Cloud mode](cloud-mode.md)).

**What it is not.** This is a rule enforced by the two programs that own the
sensors, not a hardware cut-off: the sensor rails stay powered, and anyone with
root on the machine could bypass it. It protects you from the Glowforge
service, from other software on your network, and from a stream you forgot was
running, not from someone who already controls the board. There is
deliberately no setting to turn it off.

## Watching it

**In the panel.** Open `http://<machine-ip>:8080/` and go to the **Status** tab.
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
| `/cam/snapshot?cam=lid&q=1..100` | a JPEG at the given quality |
| `/cam/status` | JSON: which sensor, which camera, frame rate, frame sizes, whether the lid currently permits capture |
| `/?action=stream` | the lid stream again, under the name mjpg-streamer clients expect |
| `/?action=snapshot` | one full-resolution lid JPEG, same aliasing |

The `?action=` pair exists because a lot of software (print-server dashboards,
camera widgets, anything written against mjpg-streamer) assumes those exact
URLs. Point such a client at `http://<machine-ip>:8080/` and it will work.

Every one of them answers **`409`** with the lid open, so a client that checks
status codes can tell "close the lid" apart from "the camera is broken".

**Access.** Reading the camera needs no token. It does need a request that
addresses the machine by IP address (or `localhost`) and, from a browser, one
that is not cross-site; that is what stops a hostile page in another tab from
reaching into your machine. It is not protection against other people on your
LAN. Anything that *changes* machine state does need the panel's token. In
practice: paste the URL into any local client and it works.

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

The stream frame is not a resampled copy of the full frame. Each 2 × 2 group of
sensor pixels becomes exactly one output pixel, which is why the stream is
precisely half the capture in each axis and why it is cheap enough to run
continuously.

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
