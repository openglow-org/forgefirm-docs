---
title: The video pipeline
---

# The video pipeline

forgectrl owns both cameras, the one in the lid and the one in the print
head, and serves them over plain HTTP from the control panel port. This
page describes the capture path, what ForgeFIRM sends and why it differs
from what the sensors can do, the privacy gate, the encoders, the lighting,
and how one camera path is shared.

- The sensor hardware, the MIPI switch, and the 8 MP status are
  [The cameras](../machine/cameras.md).
- The operator's view (watching, the endpoints, what you get,
  troubleshooting) is [Cameras](../../usage/cameras.md).
- The daemon itself is [forgectrl](forgectrl.md).

## The camera service

Both cameras (lid and head) are served as MJPEG and H.264 over the mainline
imx-media pipeline:

| Endpoint | Purpose |
|---|---|
| `GET /` | The control panel: stream toggle, head peek, snapshots, status ([The control panel](../../usage/control-panel.md)) |
| `GET /cam/stream?cam=lid\|head` | Multipart MJPEG, half the capture size in each axis (1296x972 on a 5 MP machine) |
| `GET /cam/h264?cam=lid\|head` | The same picture as H.264 in fragmented MP4 |
| `GET /cam/snapshot?cam=lid\|head&res=full\|half&q=1..100` | Single JPEG, default full (2592x1944 on a 5 MP machine) |
| `GET /cam/status` | JSON: running/cam/clients/frames/fps/fps_cap/encoder/buffers, the sensor, the frame sizes, the lid gate, the health counters |
| `GET /?action=stream` / `/?action=snapshot` | mjpg-streamer-compatible aliases (lid) |

The stream demosaics each 2x2 BGGR quad to one pixel straight into planar
YUV420 and encodes on the i.MX6 CODA960 VPU JPEG encoder: 15 fps at
1296x972 on a 5 MP machine, sensor-limited. Snapshots use a bilinear
demosaic and libjpeg, which is also the automatic fallback encoder.

Capture buffers are requested non-coherent (CPU-cached) so the demosaic can
read frames in place. On kernels whose capture queue lacks cache-hint
support the daemon falls back to uncached buffers with a bounce copy;
`/cam/status` reports which as `"buffers"`.

The capture pipeline is held open while clients are active and fully
released after 10 s idle, so one-shot V4L2 users can still grab. The
per-camera illumination LED is raised during capture and restored on idle.

## The privacy gate

**Neither camera captures unless the lid is closed.** The lid camera faces
the room once the lid is raised, and in cloud mode the capture request comes
from a remote service, so the enclosure being shut is the precondition for
any image.

The signal is EV_SW bit 3 (`doors`, the series combination both lid switches
feed, the same one the hardware safety chain uses). `machine_lid_closed()` in
[`src/status.c`](https://github.com/openglow-org/forgectrl/blob/main/src/status.c)
reads it and **fails closed**, so an unreadable lid refuses capture. There is
no setting to disable the gate.

It is enforced in two places, because two processes can reach a sensor:

| Owner | Covers | Behavior |
|---|---|---|
| forgectrl [`src/cam.c`](https://github.com/openglow-org/forgectrl/blob/main/src/cam.c) | the panel, `/cam/stream`, `/cam/snapshot`, the mjpg-streamer aliases, LightBurn, and the cloud client's normal path | refuses to start capture, refuses stream and snapshot up front (HTTP 409), and re-checks every frame so a lid opened mid-capture tears the pipeline down |
| `gfhardware.cam.capture()` | the cloud client's direct-V4L2 fallback when forgectrl is unreachable, and the capture utility | raises `gfhardware.cam.LidOpen` before configuring the pipeline or touching a lamp |

Both check before any side effect, so a refused capture leaves the lamps and
the media graph as they were. `/cam/status` reports `capture_allowed` (the
live lid reading) and `stopped_by_lid` (the last capture ended because the
lid opened rather than going idle).

Consequence for cloud mode: the factory runs focus hunts with the lid open,
and a hunt includes a head capture. Those captures are refused, and the
action runner reports the action as failed rather than leaving the service
waiting ([Cloud mode](cloud-mode.md)).

## What the sensor can do versus what ForgeFIRM sends

The sensors are more capable on paper than the video you get. Each
difference below is deliberate and has a reason.

| | The sensor can | ForgeFIRM sends | Why |
|---|---|---|---|
| Live resolution | full frame | half in each axis | CPU and bandwidth |
| Frame rate (5 MP) | 30 fps in reduced modes | 15 fps | the full-field mode runs at 15 fps |
| Resolution (8 MP) | 3280x2464 | 3264x2448 | the widest frame the board's camera receiver can take |
| Bit depth | 10 bits per pixel | 8 bits | JPEG is 8-bit, and 8-bit is what makes the 8 MP frame fit |
| Exposure / color | auto exposure and auto white balance | fixed values | a bed image has to look the same frame to frame |
| Encoding | | MJPEG and H.264, nothing recorded | two hardware encoders, bytes are not free |
| Mirroring | a mirror register | mirrored in software instead | the register breaks capture on this board |

### Resolution and frame rate on a 5 MP machine

The OV5648 offers several modes, and they are not simply "the same picture,
smaller": the full-sensor mode runs at 15 fps, the skipped and cropped modes
at 30 fps ([The cameras](../machine/cameras.md) lists them). ForgeFIRM runs
the **2592x1944** mode. The cropped modes are unusable for a bed camera:
they would show the middle of the bed and cut off the corners. That leaves
the full-frame mode at 15 fps or the skipped 1280x960 mode at 30 fps.

The camera runs **one mode at a time**, and the live stream and the
snapshots come from the same frames. That is what lets a snapshot be
delivered while a stream is running, and it is why the picture does not
stutter or re-expose when you take one. Choosing 1280x960 would double the
frame rate and permanently give up full-resolution stills, and full
resolution is exactly what camera-referenced homing and cloud mode's image
analysis need. Full stills win; 15 fps is the price.

The stream is halved to 1296x972 rather than sent at full size because
demosaicing and encoding 5 megapixels 15 times a second is far beyond this
CPU, and because a 5 MP live view of the bed is of no practical use: it is a
positioning aid, not a photograph. The stream frame is not a resampled copy
of the full frame. Each 2x2 group of sensor pixels becomes exactly one
output pixel, which is why the stream is precisely half the capture in each
axis and why it is cheap enough to run continuously.

### 8 MP ("HD") machines: a few rows short of the full array

The OV8856's largest frame is 3280x2464. ForgeFIRM captures **3264x2448**,
which is 16 columns and 16 rows less: the whole field of view, edge to edge,
without the last few pixels of margin.

The sensor can send its full frame over the two data lanes this board
wires, but at 10 bits per pixel the link runs faster than the i.MX6's
camera receiver accepts, so the receiver refuses the mode outright
([The cameras](../machine/cameras.md) has the link rates). Asking the sensor
for 8-bit pixels instead cuts a fifth off every sample and lets the same
frame travel at half the rate, which the receiver takes comfortably. That is
how an HD machine gets its full resolution, and it costs nothing, because
the delivered JPEG is 8-bit anyway. The result is about 15 frames per second
off the sensor, and roughly the same bytes per second across the bus as a
5 MP machine at its own full frame.

### Ten bits in, eight bits out

Both sensors can emit 10 bits per pixel. ForgeFIRM asks both for 8 instead,
and the delivered image is 8 bits per channel because that is what JPEG is.
Two bits would buy nothing without a tone curve to spend them on, and there
is no tone curve. Asking for 8 halves the data crossing the bus, which is
what keeps the stream cheap on a 5 MP machine and what makes full resolution
reachable at all on an 8 MP one.

### Exposure, gain, and color are fixed

There is no auto-exposure and no auto white balance. Exposure, gain, and the
color balance are set to fixed values when the camera starts, matching what
the factory firmware uses, and they are not adjustable from the panel.

That is deliberate. A bed camera is a measuring instrument: camera-referenced
homing, LightBurn's overlay, and cloud mode's image analysis all compare
images to known geometry, and an image whose brightness and color shift
between frames (as the head moves through the frame, or as the laser
flashes) is worse than a consistently imperfect one.

ForgeFIRM also applies **no gamma, tone curve, sharpening, or noise
reduction**. The JPEG is the sensor's data, demosaiced and encoded. Compared
with a phone photo the result looks flat. That is expected; it is not a
fault, and it does not affect how well the image works for positioning.

One consequence on 8 MP machines: that sensor's driver publishes no color
balance controls at all, so those images are less color-correct than a 5 MP
machine's, and the exposure and gain values for that sensor are untested on
hardware.

### Two streams, one picture: MJPEG and H.264. Nothing is recorded.

The same live picture is served two ways, and **the machine never writes
video to disk**.

**MJPEG** (`/cam/stream`) is the universal one: every frame is a complete
JPEG, so a viewer can join or leave at any moment, a dropped frame costs
nothing, and browsers, LightBurn, and mjpg-streamer clients consume it with
no plugin. It is what anything that cannot decode video should use.

**H.264** (`/cam/h264`) exists because bytes on this machine are not free.
MJPEG re-sends the whole scene fifteen times a second, roughly 9 Mbit/s, and
the WiFi transmit path runs on the machine's single CPU core, where the
measured cost is about 7 % of the core per MB/s sent. A bed camera's scene
barely changes between frames, which is exactly what an inter-frame codec
exploits: the H.264 stream carries the same picture in roughly 1.5 Mbit/s
and gives most of that CPU back. It arrives as fragmented MP4, the form a
browser's Media Source Extensions accept, with the codec named in an
`X-H264-Codec` response header. The panel's **Live** button uses it
automatically where the browser can and falls back to MJPEG where it
cannot. Latency is a beat behind MJPEG (under a second), which is why
LightBurn keeps consuming the MJPEG stream.

Both encoders are hardware: JPEG frames come from the CODA960's JPEG unit
and H.264 from its BIT processor, two independent engines, so serving both
at once does not double any cost that matters. The demosaic that feeds them
runs as fragment shaders on the SoC's GC880 GPU when the image ships the GL
stack (reported as `"convert": "gpu"` in `/cam/status`), reading the sensor
frame and writing the encoder's buffer directly, so a stream frame never
crosses the CPU at all; without the GPU it falls back to the NEON demosaic.
Stills are demosaiced and encoded on the CPU, which is most of why a
full-resolution one takes a couple of seconds.

One more consumer of nothing: with a frame-rate cap set
(`FORGECTRL_STREAM_FPS` of 1 or more), the cap is programmed into the CSI
receiver's frame-skip hardware, and skipped frames are dropped before they
are ever written to memory. `/cam/status` reports `"hw_fps_skip": true` when
that is in effect.

If you want a recording, record the stream on the computer watching it. The
machine stores its firmware, settings, and logs on a small internal flash
device and has no recording feature to fill it with.

### The mirror is applied in software

The image is mirrored horizontally to match the orientation the factory
software produces. The sensors have a mirror register that would do this for
free, but setting it breaks the board's capture path (frames stop completing
altogether), so the flip is done while the image is being demosaiced
instead. The cost is negligible and the result is identical.

## Camera sensors

Two sensors ship on the shared `camera@36` node, and the capture path
follows whichever driver bound rather than assuming one. Clients must take
the frame size from `GET /cam/status` (`sensor`, `snapshot`, `stream`)
instead of hard-coding it.

| Sensor | Machines | Capture mode | Media bus | Capture pixel format | Snapshot | Stream |
|---|---|---|---|---|---|---|
| OV5648 | 5 MP (Basic / Plus / Pro) | 2592x1944 | `SBGGR8_1X8` | `SBGGR8`, 1 byte/sample | 2592x1944 | 1296x972 |
| OV8856 | 8 MP ("HD") | 3264x2448 | `SBGGR8_1X8` | `SBGGR8`, 1 byte/sample | 3264x2448 | 1632x1224 |

Both are read as 8-bit BGGR, so one demosaic and one capture word serve both
and the only thing that changes with the sensor is the geometry. Both widths
are multiples of 32, so both take the NEON superpixel path.

The OV8856's stock RAW10 full-resolution mode is not reachable on this SoC
([The cameras](../machine/cameras.md)). Full resolution comes instead from a
RAW8 mode carried at 360 MHz, added to the driver by the BSP: 8-bit samples
need half the link rate for the same frame, and at 180 Mpx/s the mode runs
15 fps. Its control set differs from the OV5648's: exposure counts whole
lines and is capped by the frame length (2482), gain is `analogue_gain` with
128 = 1x, and it publishes no auto-exposure, auto-gain, or white-balance
controls, so white balance is uncorrected. The exposure and gain defaults
are the OV5648 values translated into those units and are not measured on
8 MP hardware.

### Stream encoding and demosaic

One capture serves every consumer, but the stream conversion has layered
implementations, each probed at runtime and each falling back to the next:

| Stage | First choice | Fallback | Switch |
|---|---|---|---|
| Demosaic (stream) | GC880 GPU fragment shaders ([`src/gpu_debayer.c`](https://github.com/openglow-org/forgectrl/blob/main/src/gpu_debayer.c)): capture dmabuf in, encoder dmabuf out, CPU untouched | NEON superpixel ([`src/debayer.c`](https://github.com/openglow-org/forgectrl/blob/main/src/debayer.c)), then scalar | `FORGECTRL_NO_GPU`, `FORGECTRL_NO_NEON` |
| MJPEG frames | CODA960 JPEG unit ([`src/vpu_jpeg.c`](https://github.com/openglow-org/forgectrl/blob/main/src/vpu_jpeg.c)) | libjpeg | `FORGECTRL_NO_VPU` |
| H.264 stream (`/cam/h264`, fragmented MP4 via [`src/vpu_h264.c`](https://github.com/openglow-org/forgectrl/blob/main/src/vpu_h264.c) + [`src/mp4mux.c`](https://github.com/openglow-org/forgectrl/blob/main/src/mp4mux.c)) | CODA960 BIT processor | none: the endpoint answers 503 and MJPEG remains | `FORGECTRL_NO_H264` |
| fps cap | CSI hardware frame skip (frames dropped before DMA) | software pacing in the worker | `FORGECTRL_NO_HW_SKIP` |

The GPU path loads Mesa with `dlopen` (no build-time GL dependency); an
image without Mesa, a kernel without etnaviv, or any refused probe lands on
the NEON path with the reason logged once. The two CODA engines are
independent, so MJPEG and H.264 clients can be served concurrently; both
encoder OUTPUT buffers are exported as dmabufs, and the GPU renders into
them directly. Snapshots always use the CPU bilinear demosaic. `/cam/status`
reports the active choices (`convert`, `encoder`, `hw_fps_skip`, `h264`).
H.264 viewers count toward engine arbitration and idle exactly like MJPEG
viewers, and a joining H.264 viewer forces an IDR so it can start decoding
immediately.

### Frame health

The capture queue flags a buffer `V4L2_BUF_FLAG_ERROR` when the frame in it
is short, torn, or arrived after the receiver lost CSI-2 sync. Such a frame
is never demosaiced: a snapshot built from one is a corrupt image presented
as a picture of the bed. The engine drops it, and escalates if they persist:
four consecutive errored frames cycle the capture queue (which
re-synchronizes the receiver), and three cycles with no usable frame between
them stop the engine, so clients reconnect and the whole pipeline setup runs
again. The ladder is
[`src/camhealth.c`](https://github.com/openglow-org/forgectrl/blob/main/src/camhealth.c),
covered by a host test.

`GET /cam/status` carries the running totals since the daemon started:

```json
"health": { "captured": 41230, "corrupt": 0, "restarts": 0 }
```

A nonzero `corrupt` on a machine that is otherwise working is a real signal
(a marginal camera ribbon, a mistimed D-PHY), even though those frames never
reached a client.

Two frames are also dropped after every stream start: they were already in
flight while the sensor was being programmed, so they predate its exposure
settling, and a snapshot could otherwise be handed one.

## Lighting

Each camera has its own lamp, and ForgeFIRM drives them around captures:

- **While capturing**, the relevant lamp is raised to a fixed working level
  and restored when the camera goes idle.
- **At rest**, the lid lamp sits at the `lid_lamp_idle` setting (0 to 255,
  default 236), the bed light you normally see. It is asserted when the
  daemon starts, when you change the setting, and whenever a controller
  starts.
- **Per shot**, `/cam/snapshot` accepts `lamp=0..1023` to override the level
  for that one image; a few frames are discarded afterward so the image you
  get was exposed under the light you asked for.

In cloud mode the cloud client drives the lid lamp for as long as it runs
(its `LLvl`), and ForgeFIRM re-asserts your idle level the next time a
controller starts.

## Sharing one camera path

Because only one camera can capture at a time, requests have to be
arbitrated. The rule is **the newest request wins**, on the assumption that
one person is standing at the machine:

- **A new stream preempts the current one.** Existing viewers' streams end
  cleanly (their picture freezes on the last frame) rather than being torn
  mid-frame, and the mux switches.
- **A snapshot of the other camera borrows the path.** The stream pauses,
  the mux switches, one frame is taken, and it switches back; viewers see a
  gap of a second or two. Snapshots do not fail because someone else is
  watching.
- **The camera shuts down after 10 seconds** with nobody watching and no
  snapshot pending, so other software on the machine can use it. It shuts
  down immediately, whoever is watching, if the lid opens.

## Who else uses the cameras

- **Camera-referenced homing** (`$H`) takes a lid image and has the
  Glowforge service work out where the head is. This is the factory homing
  method, so it needs a service session; it is the one part of GRBL mode
  that does ([Homing](homing.md)).
- **Cloud mode** captures both cameras on demand through the same snapshot
  endpoint, so it obeys the same arbitration as everything else
  ([Cloud mode](cloud-mode.md)).
- **LightBurn** consumes the lid stream for its camera overlay while it
  drives motion over the Grbl connection; the two coexist.
