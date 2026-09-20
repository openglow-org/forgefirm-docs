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

`homing_mode` in `/data/forgefirm/forgefirm.conf` selects what `$H` does. The panel's
Machine tab sets it, and the driver re-reads the file on every `$H`:

- `gfcloud`: camera homing through the Glowforge web service, the same cycle
  the factory machine runs. A cycle takes roughly a minute.
- `manual`: the operator puts the head against the stop blocks by hand and
  `$H` declares that spot as `manual_home_x`, `manual_home_y`. Nothing moves
  ([Manual homing](#manual-homing)).
- `switches`: the planned limit-switch cycle. `$H` is refused (error 53).
- `none`: `$H` is rejected (error 5).

The methods are rows of one table in the driver, `homing_providers[]` in
`glowforge_homing.c`: an id, a kind, and the function `$H` runs. The kind is
a property of the code, never of configuration. A `builtin` provider is a
function in the driver. A `runner-fd` provider hands the pulse device to a
root process that moves the machine; it suspends and resumes the stream
engine around its session, and it is refused while the motors are released.
Every provider ends in the same completion code: the soft limits, the
planner's position, the kernel counters cleared, the anchor written, the
core's homing-completed event, and the idle state.

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
   `/data/forgefirm/gfhome.conf`, seeded from `/etc/gfhome.conf.sample` on first
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
`gfcloud_home_timeout_s` (default 300 s, held to 10 to 3600 s: a value
outside is clamped with a log line, as `gfcloud_home_x` and
`gfcloud_home_y` are to the axis travel either side of the origin). The `ok` for `$H` is sent when the
session ends, so a sender that waits for it waits the whole session while
the status reports keep flowing.

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
`gfcloud_home_x` and `gfcloud_home_y` on the step grid (defaults 0 and 0;
either may be negative, and then the work envelope reaches back to the home
position on that axis, since the head stands there). Those two keys belong to
this provider alone, as `manual_home_x` and `manual_home_y` belong to the
manual one: no provider reads another's. Z is set to the park
height: the runner leaves the lens on the hall's rising edge, whose focal
height the focus card measured (`lens_hall_edge_z_mm`), then moves it the
whole half-steps to `lens_park_z_mm` (default 3 mm), inside the window every
head reaches without touching a stop
([The grblHAL driver](grblhal-driver.md#the-lens-z)).
The factory home is the machine origin, the back-left corner,
with the workspace all-positive from there
([The motion hardware](../machine/motion-hardware.md)). The position is then
anchored, and the panel shows it normally. A successful home also turns the
driver's X and Y soft limits on, with the bed as the envelope, whatever `$20`
says; they go off with the anchor whenever the position is invalidated
([The grblHAL driver](grblhal-driver.md#the-lens-z)).

## Manual homing

The operator's procedure is [Homing, Manual homing](../../usage/homing.md#manual-homing).

### The `manual` provider

`$H` under `manual` is accepted in Idle or Alarm, as every provider is. It
waits for the kernel to finish any decel tail, energizes X and Y if they are
released, and then declares the position: `sys.position` X and Y to
`manual_home_x` and `manual_home_y` on the step grid, X and Y added to the
homed mask, the kernel counters cleared, and the anchor written with the
source `manual`. The two keys belong to this provider alone. Unset, they are
the origin: the stop blocks are X0 Y0. They are never negative (forgectrl
refuses one, and the driver holds a hand-edited value to 0 up to the axis
travel, with a log line). The stop blocks are a wall, so the work envelope
starts at the declared position and ends at the axis travel. There is
no stream suspend, no runner, and no pulse byte. Z is not touched: its
position, its reference, and its envelope stay as they were, and since the
counters are cleared for all three axes the anchor carries the height the
lens stands at. There is no lid gate, because nothing moves and the lid is
open while the head is being pushed.

The sender gets a warning at every manual home, and the anchor names its
source so a reader can tell a position a hand declared from one the machine
found. The soft limits are exactly as true as the placement: a misplaced home
shifts the whole envelope, so a move inside the limits can reach the frame.
That is a mechanical matter and never an emission one. The crash watch is not
a backstop for it, since it arms only inside the laser's armed window
([The cooling engine](cooling-engine.md)).

### The motor release

`glowforge_release.c` registers two system commands, the way `$H` is
registered.

| Command | What it does |
|---|---|
| `$MD` | Waits up to 3 s for the kernel to finish a move's tail, then releases X and Y by taking their step currents (`pic/x_step_current`, `pic/y_step_current`) to 0. On the bench reference that lets the gantry and the head move freely by hand, with the steppers' detents still felt; the drivers stay enabled and the 40 V rail stays up. Accepted in Idle or Alarm with the kernel idle, and refused while a laser job is armed or arming. It drops the X and Y reference at once (homed bits, soft limits, their part of the anchor) and keeps Z's. |
| `$ME` | Energizes X and Y: the hold currents. The position stays invalid until a home. The machine returns to the state it was in before the release, so an alarm that was already standing is not cleared. |

**While released, every motion is refused, and nothing but `$ME` or a manual
`$H` energizes the motors.** The operator's hands are on the gantry, and a
stray jog from a sender, a pendant, or a bounced button must not snap the
rotors to a detent under them. The lock is the core's own alarm state
(ALARM:11), where the core refuses every g-code line and every jog with an
error, whoever sent it. The driver makes the lock unpickable:

- `$X` is shadowed and refused (error 9) while released.
- A soft reset leaves the alarm standing, as the core does for any alarm.
- A `runner-fd` homing provider is refused, since its session would energize
  the motors and move the head.
- The realtime poll puts the alarm back if anything else clears it.
- The driver's current scheme writes 0 to X and Y, and nothing else, for as
  long as the release is held, so neither the run nor the hold posture can
  energize them.
- The release leaves a marker, `motors.released`, in the state directory. A
  controller that starts over it (the one before it died, or was restarted)
  takes the release over before it writes its first current, and comes up
  locked.
- forgectrl reads the same marker: its motion probe is skipped and a switch
  to cloud mode is refused while it stands
  ([forgectrl](forgectrl.md#mode-supervision)).

A refused line gets a `[MSG:]` that says the motors are released, at most one
every two seconds.

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

## The lens reference at every start

The lens does not wait for a home. Before any controller starts, forgectrl
sweeps the lens onto the hall sensor's rising edge in the motion-verify
window, and the controller reads the focal height of that edge out of
`lens_hall_edge_z_mm`. Z is therefore referenced on every start, on its own,
while X and Y wait for a home ([forgectrl](forgectrl.md#mode-supervision)).

A lens that cannot reach its edge is a **hard fault**, not a fallback: the
lens motor is wedged, the carriage is jammed, or the hall sensor is dead, and
a machine whose focal height would be a guess does not get to run. The
supervisor holds every controller down and the panel names the reason.

## Running unhomed

**The machine cuts fine unhomed** in GRBL mode. Without a reference, X and Y
are relative to wherever the head happened to be when the controller started,
so the panel shows them in red to say so, and the sender should use a
job-start mode that does not depend on machine coordinates
([GRBL mode](../../usage/grbl-mode.md)). After a successful home the position
is anchored and shown normally. Z is the exception: it carries its own
reference from the start, so it reads normally while X and Y do not.

Position comes from the kernel step counters, anchored through
`/run/grblhal.homed`, which the controller writes. forgectrl serves it from
there and never queries the Grbl socket ([forgectrl](forgectrl.md)). The
anchor names the axes it references, so the lens reference anchors Z alone
and a completed home anchors all three. Its last field names what set it:
`gfcloud`, `manual`, or `startup` for the lens reference.

Anything that invalidates position (an underrun, a stream fault) drops the
anchor deliberately, so a stale origin cannot be reused. A motor release drops
X and Y from it and keeps Z
([The grblHAL driver](grblhal-driver.md)). Z is never driven blind, homed or
not: the lens carriage is referenced against the hall sensor's edge, low in
its travel ([The motion hardware](../machine/motion-hardware.md#the-lens-and-its-travel)).
