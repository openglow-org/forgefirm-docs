---
title: Homing
---

# Homing

The machine has no limit or home switches as it ships. This page describes
how ForgeFIRM establishes an origin in each mode: camera-referenced homing
through the Glowforge service, what the controller assumes when it runs
unhomed, and the planned limit-switch cycle.

- The operator's view (when to home, what the panel shows, the settings) is
  [Homing](../../usage/homing.md).
- The origin, the work area, and the Z reference are
  [The motion hardware](../machine/motion-hardware.md).

## The homing methods

`homing_mode` in `/data/forgefirm.conf` selects what `$H` does. The panel's
Machine tab sets it, and the driver re-reads the file on every `$H`:

- `gfcloud`: camera homing through the Glowforge web service, the same cycle
  the factory machine runs. A cycle takes roughly a minute.
- `switches`: the planned limit-switch cycle, the grblHAL core's own homing
  cycle (`$22` = 0).
- `none`: `$H` is rejected (error 5).

## Camera-referenced homing in GRBL mode

### What the driver does

`glowforge_homing.c` in the grblHAL driver registers a driver `$H` that
shadows the core's homing cycle. Under `gfcloud`:

1. The driver **suspends the stream engine**, and only from a fully idle
   kernel: closing the flock'd pulse-device fd mid-program is an emergency
   stop, so a handover never happens with a run in flight.
2. It **forks the homing runner**, `/usr/sbin/gfhome.py`. The runner
   inherits the brokered pulse device and its environment (`GF_PULSE_FD`),
   so the handover opens and closes no device and never moves the 40 V rail
   ([forgectrl](forgectrl.md)). The runner's configuration is
   `/data/etc/gfhome.conf`, seeded from `/etc/gfhome.conf.sample` on first
   run.
3. While the session runs, the driver **pumps the Grbl protocol**, so the
   sender keeps getting status reports and does not time out. What the service
   does during it is the factory's own camera homing
   ([Factory firmware](../machine/factory-firmware.md)).
4. On completion it **reacquires the device** and re-applies the analog
   configuration and `step_freq`, then writes the homing anchor,
   `/run/grblhal.homed`, which forgectrl uses to serve position.

`^X` aborts the session (SIGTERM, then SIGKILL). A failure or a timeout
queues `ALARM:18`, like a failed core homing cycle; the budget is
`gfcloud_home_timeout_s` (default 300 s).

### The homing session

The runner dispatches with `allow_print=False`, so a print can never run
inside a homing session. It drives the `GFUIService` dispatch loop itself,
because the stock `run()` loop can neither stop nor close the socket. The
service's sequence, as it runs against the current service, is `settings`,
`hunt`, `lid_image`, a single corner move, `lid_image`, then silence: the
service takes a lid image, moves the head, takes another, and computes where
the head is ([The cloud protocol](../machine/cloud-protocol.md)). The hunt is
answered as done without moving the lens or playing its file: the session
borrows the service for its camera homing only.

Completion is guarded:

- The runner treats a hunt, plus at least one motion window witnessed by the
  head accelerometer, plus 10 s of quiet as complete.
- A run of near-identical service corrections aborts: the machine is not
  physically moving.
- **A quiet service without an accelerometer-witnessed motion window is a
  failure, not a homing.** Position counters advancing are not proof of
  motion.

After the service goes quiet the lens takes the run's one reference, on the
hall sensor's edge, and the driver places it in Z.

### The lid

Homing is lid-gated in practice, even though the grblHAL core does not see
the door signal during `$H`. The session's move to the home corner is an
ordinary motion action: refused with the lid open, and stopped if the lid
opens partway through. The camera steps need the lid closed anyway
([The video pipeline](video-pipeline.md)). Only the lens (Z) **hunt** inside
the session ignores the lid, and in GRBL mode a hunt happens only inside a
homing session; there is no hunt outside one.

### What the session needs

- **A service session.** This is the factory homing method, so it signs in
  to the Glowforge service with the machine's built-in identity (the fuse
  serial and password), or with the `gf_serial` / `gf_password` overrides
  ([Cloud mode](cloud-mode.md)), and names its software as
  `ForgeFIRM/<version>` through the User-Agent, as cloud mode does. The
  service holds one session per machine.
  It is the one part of GRBL mode that needs the service, and an internet
  connection.
- **The lid closed**, for the motion and for the camera captures.
- **The head accelerometer**, as the motion witness.

### The position after a home

After a successful session the machine coordinates are set to
`gfcloud_home_x` and `gfcloud_home_y` (defaults 0 and 0), and Z to the park
height: the runner leaves the lens on the hall's rising edge, whose focal
height the focus card measured (`lens_hall_edge_z_mm`), then moves it the
whole half-steps to `lens_park_z_mm` (default 3 mm), inside the window every
head reaches without touching a stop
([The grblHAL driver](grblhal-driver.md#the-lens-z)).
The factory home is the machine origin, the back-left corner,
with the workspace all-positive from there
([The motion hardware](../machine/motion-hardware.md)). The position is then
anchored, and the panel shows it normally.

## Homing in cloud mode

Cloud homing is camera-based, in the same way: the service takes a lid image,
moves the head, takes another, and computes where it is. The lens hunt
references Z against the hall sensor. Hunts are not lid-gated.

- **Connecting zeroes the machine's counters** at the head's current
  position. GRBL-mode coordinates do not survive a switch to cloud mode and
  back: re-home after switching.
- **The connect-time hunt.** A process's first settings report carries the
  machine's values, and the service answers it with its connect-time hunt: a
  Z home, the service's XY hunt pattern, and the home offset. A report in the
  reconnect form (no values) makes the service keep the head position it
  already has instead, which is what the factory client does on every
  reconnect within a session. `gfcloud.py --no-hunt` starts that way on
  purpose ([Cloud mode](cloud-mode.md)); a print placed on a stale head
  position can run the gantry into a rail, so a fresh boot always reports
  the values and gets the hunt.
- **The service dead-reckons position** from the hunt onward. After any
  mid-job abort it re-hunts, and after a completed print it issues a
  `lid_image` and a Z re-hunt. The park after every print, finished or
  aborted, matters for that reckoning: a park cut short would offset every
  motion until the next camera home, which is why the park ignores the lid
  and the cancel flag ([Cloud mode](cloud-mode.md)).

## Running unhomed

**The machine cuts fine unhomed** in GRBL mode. Without a reference,
coordinates are relative to wherever the head happened to be when the
controller started, so the panel shows position in red to say so, and the
sender should use a job-start mode that does not depend on machine
coordinates ([GRBL mode](../../usage/grbl-mode.md)). After a successful home
the position is anchored and shown normally.

Position comes from the kernel step counters, anchored at the last completed
homing through `/run/grblhal.homed`, which the controller writes. forgectrl
serves it from there and never queries the Grbl socket
([forgectrl](forgectrl.md)).

Anything that invalidates position (an underrun, a stream fault) drops the
anchor deliberately, so a stale origin cannot be reused
([The grblHAL driver](grblhal-driver.md)). Z is never driven blind, homed or
not: the lens carriage is referenced against the hall sensor's edge, low in
its travel ([The motion hardware](../machine/motion-hardware.md#the-lens-and-its-travel)).
