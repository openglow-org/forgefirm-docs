---
title: Factory firmware
---

# Factory firmware

This page describes how the factory machine works: what the factory firmware
needs from the Glowforge service, the session it runs, the pulse file it plays,
the header every job carries, and the holds around a print. The wire protocol
itself is on [Cloud protocol](cloud-protocol.md); how ForgeFIRM's cloud mode
reproduces the factory experience is on [Cloud mode](../forgefirm/cloud-mode.md).

## The factory machine cannot cut without the service

The factory firmware plans nothing on the machine. Every job arrives from the
Glowforge web service as a precomputed **pulse file**: a byte stream already
resampled to the machine tick, locked to the machine's serial number, and
gzip-compressed. The service commands the job over a WebSocket whose TLS the
factory firmware pins to the server's public key; the machine downloads the
pulse file over HTTPS, writes it into a DMA ring in reserved memory, and clocks
it out with the i.MX6 EPIT timer and SDMA engine into the GPIO register that
drives the steppers and the laser (see [The step engine](step-engine.md)).
Without the service there is no job to play.

The factory validates its own homing by camera: the service takes a lid image,
moves the head, takes another, and computes where the head is. The lens hunt
references Z against the hall sensor in the head. See
[Homing internals](../forgefirm/homing.md).

The factory firmware version the ForgeFIRM cloud client is validated against,
and advertises to the service, is **`2.6.0-2228`**.

## The session

Once a machine is signed in and the WebSocket is open, the service drives it
through a sequence of actions. The machine handles each and replies with the
matching events:

| Action | What the machine does |
|---|---|
| `settings` | Sends the full machine settings report (the ~600 4-character setting codes). |
| `update_check` | Hands off to the updater (below). |
| `hunt` | Downloads the focus-homing pulse file and runs it; emits `hunt:starting` / `hunt:completed`. |
| `lid_image` / `head_image` / `lidar_image` | Captures a JPEG and **uploads it to the presigned storage URL** supplied in the action's `endpoint` field; emits `:capture:*` and `:upload:*` events. |
| `motion` | Downloads and runs the motion pulse file; emits `motion:starting` / `motion:completed`. |
| `print` | Downloads the print pulse file, waits for the button, then runs the warm-up, the cut, the return to home and the completion events. |

The action vocabulary, the envelopes and the events are on
[Cloud protocol](cloud-protocol.md).

### What the three unprompted actions do in the factory

None of the three appears on the wire in any captured session; the descriptions
come from the 2.6.0 binary. All three are hand-offs to programs ForgeFIRM does
not have:

- **`update_check` checks nothing.** The handler writes `'u'` to the runit
  control fifo `/var/run/svs/glowforge-updater/control` and reports
  `:completed`, or `:failed` if that write fails; on a service-sent failure or
  cancel it writes `'d'` to stop the service again. Everything an update means
  happens in that separate daemon. The application carries no update endpoint
  at all, and a cut refuses to start while the updater holds its lock.
- **`factory_reset` replaces the application with a script.** The action posts
  a command to the hardware task, which tells runit not to restart the
  application and then `execl`s `/usr/bin/factory_reset.sh`, passing `reboot`
  when the request's flag asks for one.
- **`head_firmware_update` flashes the laser head.** It takes
  `head_firmware_filename` from the request, reads it out of
  `/glowforge/fw/head/` and runs `/usr/bin/head-update.sh`.

ForgeFIRM refuses two of these and answers the third without the hand-off; the
policy is on [Cloud mode](../forgefirm/cloud-mode.md). The two refusals report
`:failed` rather than `:cancelled` on purpose. In this protocol a cancel is what the service says when it withdraws an action; failure is what a machine says when the thing did not happen, and it is the factory's own report when its reset script cannot be launched. <!-- style: ignore -->

The factory updater itself, and the `.fw` package it applies, are on
[Boot and storage](boot-and-storage.md).

## The pulse (`.puls`) file

Motion, hunt, and print "pulse" files describe a job. Each begins with a small
header: a magic (`GF1`), a header length, and a series of 4-character key/value
tags (machine-setting overrides for the job), followed by a raw, per-tick
step/laser byte stream that clocks the X/Y/Z steppers and the laser. The byte
layout is on [The step engine](step-engine.md).

The body may be gzip-compressed; a compressed body's uncompressed length is in
the gzip ISIZE trailer. The header names the serial number the job is locked to
(`MCsn`) and the pulse-data format (`PDfm`).

The factory uses a 10 kHz machine tick for prints and hunts and 28160 Hz for
travel moves. A print header carries its own step frequency (`STfr`), the
acceleration ramp, and the fan duties for the job.

`gfutilities` carries helpers for the format: `load_motion()` downloads a
pulse file, parses the header (buffering across chunks so headers larger than
one read are handled), writes the body, and returns header data plus computed
motion statistics; `decode_all_steps()` decodes a pulse byte stream into
per-axis step counts and converts them to millimeters and inches;
`generate_linear_puls()` produces a simple trapezoidal-profile linear move.

## The pulse header

Every pulse file opens with a header: a length, then a flat list of 4-character
tags each carrying a 32-bit little-endian value. It is the job's operating
envelope, and the factory firmware treats a well-formed one as a precondition
for cutting at all. Of the tags it knows, 346 are accepted in a header and 29
are mandatory; a header missing any one of the 29 is refused outright, and a
known tag that is not header-legal is refused too. An unrecognized tag is only
logged and skipped, which is why a newer service can talk to an older machine.

The header is not a set of echoes. Roughly two thirds of the fields come back
holding whatever the machine last reported, but the service substitutes real
operating values for the ones that matter: fan duties, per-sensor temperature
ceilings, lid IR flame thresholds, head accelerometer limits and a high-voltage
current cap all arrive filled in per job.

Every tag the service fills in has a disposition in ForgeFIRM, and the job log
says which: each job names its lifecycle keys, counts the keys with no applier,
and splits that count into *declared ignored* (a decision with a reason, listed
below) and *undecided* (`N of M header keys have no applier here (D declared
ignored, U undecided)`, the undecided ones named at debug level). The undecided
count is the one that should be zero.

| Tags | Disposition |
|---|---|
| `AArd`, `EFrd`, `IFrd` | **Applied**: the run-phase fan duties, handed to the forgectrl cooling engine as the per-job profile on the scale the service uses (air assist 0 to 1023, exhaust and intake 0 to 65535). While the laser is armed the engine raises any of them to its configured run duty (the airflow floors were measured there), so a print's fans never run slower than the cut profile, while a hunt's `0` duties stand and the hunt is measured, not judged. |
| `STfr` | **Applied**: step frequency. |
| `XSrc`, `YSrc` / `XShc`, `YShc` | **Applied**: stepper current while running / idle. |
| `XSdm`, `YSdm` | **Applied**: decay mode. |
| `XSmm`, `YSmm` | **Applied, and refused on** anything but 8: every header the service has sent carries 8, the factory's own analog config, and 8 is the only mode a cloud job runs at on this machine (the `xy_microsteps` setting is GRBL mode's). Any other value is `refusing the job:` in the log and `:cancelled` to the service, before a byte reaches the ring; such a report is what starts the work on finer modes in cloud mode. <!-- style: ignore --> |
| `ZSmd` | **Applied**: Z microstep mode; 0 is full-step, and every capture carries 0, so the service's Z counts are full steps (15 for 0.5 in of material, 4 for 0.1 in, from the service's zero, 4 full steps below the hall edge, where its hunt parks the lens: [The motion hardware](motion-hardware.md#the-lens-and-its-travel)). |
| `CMrx`, `CMrn` | **Passed through** as the job's coolant window (millidegrees, sent as degrees) on every `POST /cool/state` while the job is loaded. The engine applies each only where it is stricter than its configured value, never looser, never to a gate the operator turned off; the coolant ceiling is the consumer. |
| `EFrx`, `IFrx`, `AArx` | **Passed through** as the tach floors (the maximum periods, sent as the minimum speed each means in the kernel's units); the airflow gates are the consumers, and a header can only raise a floor for its job. A sentinel (0, 1023, the signed extremes, the unsigned rail) or an absurd value is dropped. |
| `AArn`, `EFrn`, `IFrn` | **Read, inert**: the tach minimum periods are maximum speeds, which nothing gates on. |
| `MCsn`, `PDfm` | **Refused on**: the serial the job is locked to and the pulse-data format, both checked before a byte reaches the ring; a mismatch is `refusing the job:` in the log and `:cancelled` to the service. <!-- style: ignore --> |
| `CFrh`, `CCwp`, `CCrp`, `CCup` | **Logged**: the lifecycle keys, named in every job's log and driving nothing, which is what the factory does with them (below, "A print's warm-up and its rest"). |
| `AAw?`, `EFw?`, `IFw?` | **Declared ignored**: the warm-up phase fan profile. The run profile covers the warm-up hold, and every captured header sets the warm-up values equal to the run values. |
| `PTmn`, `PTmx` | **Declared ignored**: the supply temperature window. The service sends the whole ADC range (a window that cannot trip) and the factory binds the pair to nothing; the supply's raw reading is watched per job by the engine instead. |
| `BT??`, `HT??`, `LT??`, `IT??`, `FT??` | **Declared ignored**: the board, head, lid, interconnect and fused temperature ceilings, sent in a unit that is not millidegrees and not established. The chassis (board) sensor is watched per job; the other four locations have no sensor on this platform. |
| `CTrn`, `CTrx` | **Declared ignored**: the coolant window in raw counts, older files only; `CMrn`/`CMrx` carry the same window. |
| `HA??` | **Declared ignored**: the head accelerometer thresholds. They are LIS2HH12 interrupt-generator register values, and forgectrl's crash watch runs the same mechanism on its own local knobs (the header defaults are the seeded values), so the per-job copies add nothing. |
| `IR??` | **Declared ignored**: the lid IR flame thresholds. The lid IR channels read the lid lamp, so these absolute numbers are the prior for the lamp-aware fire watch (see [the cooling engine](../forgefirm/cooling-engine.md)), not a gate. |
| `HIix`, `HIrx` | **Declared ignored**: the HV current caps. The sampled `LASER_ON` witness covers the idle case, and HV current is ranged in every job's log line. |
| `TRuc` | **Declared ignored**: thermal report upload conditions, a knob for the factory's telemetry, which is out of scope. |
| `WPon` | **Declared ignored**: the pump is held on as part of the engine's idle posture; per-job pump control would belong in its per-job profile. |
| everything else | **Undecided**: counted and named at debug level by every job. Of the 346 header-legal tags, the factory binds 283 to a source; 20 configure the client's own network backoff, 39 belong to the three fans of an air filter, the camera families are exposure and gain values the mainline driver's units do not take, and most of the rest are per-phase idle variants of the limits above. A hunt header from the live service leaves 49 undecided. |

Thermal policy is the cooling engine's, on purpose: it runs its own coolant
ceiling and critical line, flow verification, airflow gates, emission witness
and silence timeout, and a remote service can tighten those limits for a job
and never loosen them. The factory's own policy, decoded from its firmware, is
in the hardware facts bank of
[BRINGUP.md](https://github.com/openglow-org/forgefirm/blob/master/docs/BRINGUP.md)
("The factory's envelope").

The service pushes very little outside the header. Across every captured
session, counting every action type, the service has pushed seven keys through
per-action settings: `IMct`, `NRic`, `HCil`, `HCae`, `HCex`, `HCag` and
`HCga`. The opening `settings` action on its own carries one, `NRic`. Nothing
thermal, nothing about fans, nothing that bounds the machine arrives that way.
The operating envelope reaches the machine only in the pulse header, per job.

## A print's warm-up and its rest

The factory holds twice around a print, and so does ForgeFIRM. Measured on a
factory slot: **3.05 s** between configuring the run and starting it, and about
**10.35 s** of rest after the park before the machine goes idle. A motion or a
hunt gets neither.

Both are equipment protection rather than ceremony. The warm-up is what gets
air and coolant moving before the first fire; the rest is what purges the
enclosure and the tube after the last one. The service assumes both have
happened, so a machine that skips them is running hardware nobody looked after.

In ForgeFIRM, `MOTION.WARM_UP_DELAY` and `MOTION.COOL_DOWN_DELAY` carry the
seconds and default to the factory's measurements. 0 skips either, deliberately,
and a skipped period says so in the log rather than passing in silence: a
config that carries explicit zeros keeps them until someone changes them. The
configuration file is described on [Cloud mode](../forgefirm/cloud-mode.md).

The pulse header looks like the source of these periods and is not. Every
captured print header carries `CCwp` 5000 and `CCrp` 10000, with `CFrh` for
the park, and a motion or a hunt carries none of them; the correlation is real
and the causation is not. In the 2.6.0 application all four lifecycle keys
(`CCrp`, `CCup`, `CCwp`, `CFrh`) are parsed, stored, copied into the settings
batch and acted on by nothing: a tag reaches behavior either through a
peripheral that registers it against a source or through an inlined lookup by
index, and these four have neither. The factory's warm-up and rest come from
somewhere other than the job, so configured periods defaulted to what the
factory was measured doing are the right model rather than a placeholder. The
keys stay in the per-job log line as a record of what the service sends.

## Pause, cancel and park in the factory

- **The button pauses and resumes a print.** A press stops motion under
  control and then backs the stream up 2000 ticks with the laser off; the next
  press runs forward and re-enables the laser after a 1950-tick lead, so the
  resumed cut overlaps the material already burned instead of starting cold.
  ForgeFIRM carries both counts as settings (see
  [Cloud mode](../forgefirm/cloud-mode.md)).
- **A lid or interlock open during a job cancels it.** The head returns to the
  position the job started from with the lid still open. The service
  dead-reckons machine position, so the park after every print, finished or
  aborted, matters: a park cut short would offset every subsequent motion
  until the next camera re-home.
- **The factory runs a focus hunt with the lid open**, and a hunt includes a
  head capture. ForgeFIRM's cameras capture only with the lid closed, so under
  ForgeFIRM a hunt needs the lid shut (see [Cameras](../../usage/cameras.md)).
- **The factory streams continuous telemetry**: the binary sensor firehose
  (`POST /api/sensor`), in-band advisory logs (WSS `type:"log"`), and the
  `fault:*` / `estop:*` / `interlock:*` reporting namespace. ForgeFIRM's scope
  decision on these channels is on [Cloud mode](../forgefirm/cloud-mode.md).
- **The factory live-appends to its ring.** In a captured print the progress
  frame's `total` grew in steps of 262,144 bytes (256 KiB) per interval: the
  factory topping its ring up on the wire (see
  [Cloud protocol](cloud-protocol.md)).
