---
title: Homing
---

# Homing

The machine has no limit or home switches as it ships. This page tells you how
the machine finds its origin with the cameras, what the machine does without
one, and what each homing setting means.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

The mechanism, the homing runner and its handover, is in
[Homing internals](../technical/forgefirm/homing.md).

## The homing method is a setting

`homing_mode`, on the panel's Machine tab, selects what `$H` does. The
controller re-reads it on every `$H`.

| Value | What `$H` does |
|---|---|
| `gfcloud` | Camera-referenced homing through the Glowforge web service, the same cycle the factory machine runs. The method that works; set it on the Machine tab, since a fresh install leaves `homing_mode` unset. |
| `switches` | The planned limit-switch cycle. Not available. |
| `none` | `$H` is rejected (error 5). |

## Camera-referenced homing

`$H` from any sender runs the factory-style camera homing cycle through the
Glowforge service. The service takes a lid image, moves the head, takes
another, and computes where the head is; the machine moves to the home
corner. The service's lens hunt is answered as done without moving the lens;
after the session the lens takes its own reference on the hall sensor's edge,
Z is set to the focal point's height above the tray at that edge, the number
[Commissioning](commissioning.md#the-sheet) measured, and the lens then moves
to the park height, `lens_park_z_mm` on the Machine tab (default 3 mm), so a
home ends focused about 3 mm above the bed.

- **It needs a Glowforge account and a live service session.** This is the
  one part of GRBL mode that reaches the Glowforge service; everything else in
  GRBL mode runs without it. The cycle uses the machine's own credentials
  (the factory fuse identity, or the overrides on the GF Cloud tab; see
  [Cloud mode](cloud-mode.md)) and names its software as ForgeFIRM.
- **It needs the lid closed.** The camera steps need it, and the move to the
  home corner is an ordinary motion action: refused with the lid open, and
  stopped if the lid opens partway through. The lens reference after the
  session does not need the lid.
- **It takes about a minute.** A full cycle runs in 50 to 65 s. While it
  runs, `$H` suspends the stream engine, runs the session, and hands the
  machine back; your sender keeps getting status reports.
- **It can fail or time out.** `gfcloud_home_timeout_s` (default 300 s) is
  the budget for the whole session (sign-in, camera uploads, hunt, and corner
  moves). Past it, or on a failure, the controller alarms (ALARM:18) like a
  failed core homing cycle. A soft reset (`^X`) aborts the session.
- **A quiet service is not a homing.** The cycle counts as complete only when
  the accelerometer in the print head witnessed real motion during the
  session. A service that goes quiet without moving the head is a failure.

After a successful home the position is anchored and the panel shows it
normally. The home corner is the back-left corner of the bed, and the workspace
is all-positive from there (+Y runs toward the front of the machine; Z counts
positive upward). `gfcloud_home_x/y` on the Machine tab set the machine X and
Y the head is at after a completed homing (defaults 0 / 0): leave them blank
until a measurement says otherwise. Z after a home is `lens_park_z_mm`, the
focus height the lens parks at; the focus card measured where the hall edge
sits in that frame. To calibrate: home, jog to
a known reference, and enter the measured offsets.

Do not let a sender home automatically on connect: LightBurn's **Auto-home on
startup** stays off, and you run `$H` deliberately from its Console tab when you
want a true machine origin ([LightBurn](lightburn.md)).

## Running unhomed

**The machine cuts fine unhomed.** Without a reference, X and Y are relative
to wherever the head happened to be, so the panel shows them in red to say so,
and your sender should use a job-start mode that does not depend on machine
coordinates: in LightBurn, **Start From: Current Position**
([LightBurn, Job start mode](lightburn.md#job-start-mode)).

**Z is the exception.** The lens references itself against its hall sensor
every time the machine brings a controller up, so focus heights are good
without homing and Z reads its height while X and Y show as unreferenced. The
panel's **Homed** row names the axes that carry a reference, so an unhomed
machine reads `Z only` rather than a plain no. If the lens cannot find its
sensor the machine refuses to run at all and the panel says why: that is
broken hardware, not a state to work around.

Anything that invalidates position, an underrun or a stream fault, drops the
anchor deliberately, so a stale origin cannot be reused. Re-home before you
trust coordinates again.

## Homing in cloud mode

Cloud homing is automatic and camera-based; the service runs it when the
machine connects and after prints. The lens hunt references Z against the hall
sensor. Connecting zeroes the machine's counters at the head's current
position, so GRBL-mode coordinates do not survive a switch to cloud mode and
back: re-home after switching ([Modes](modes.md), [Cloud mode](cloud-mode.md)).
