---
title: Homing
---

# Homing

The machine has no limit or home switches as it ships. This page tells you how
the machine finds its origin with the cameras, how you can set it by hand, what
the machine does without one, and what each homing setting means.

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
| `manual` | You put the head against the stop blocks by hand, and `$H` declares that spot as `manual_home_x`, `manual_home_y`. Nothing moves. No account, no service, no camera ([Manual homing](#manual-homing)). |
| `switches` | The planned limit-switch cycle. Not available. |
| `none` | `$H` is rejected (error 5). |

## Camera-referenced homing

`$H` from any sender runs the factory-style camera homing cycle through the
Glowforge service. The service takes a lid image, moves the head, takes
another, and computes where the head is; the machine moves to the home
corner. The service's lens hunt is answered as done without moving the lens;
after the session the lens takes its own reference on the hall sensor's edge,
Z is set to the focal point's height above the tray at that edge, the number
[Setup](setup.md#the-sheet) measured, and the lens then moves
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
- **The `ok` comes at the end.** Your sender's `ok` for `$H` arrives when the
  session ends; the status reports keep coming meanwhile.
- **After a home the bed is the limit.** A program move past the bed alarms
  before it moves (alarm 2), and a jog past it is refused (error 15). The
  limits go with the reference: an underrun or a stream fault takes both.

After a successful home the position is anchored and the panel shows it
normally. The home corner is the back-left corner of the bed, and the workspace
is all-positive from there (+Y runs toward the front of the machine; Z counts
positive upward). `gfcloud_home_x/y` on the Machine tab set the machine X and
Y the head is at after a completed camera homing (defaults 0 / 0): leave them
blank until a measurement says otherwise. They may be negative, when the
origin you calibrated lies inside the factory home; the soft limits then reach
back to the home position, since the head stands there. Camera homing alone
uses them: no other homing method reads them, and the panel shows them only
while camera homing is the method. Z after a home is `lens_park_z_mm`, the
focus height the lens parks at; the focus card measured where the hall edge
sits in that frame. To calibrate: home, jog to
a known reference, and enter the measured offsets.

Do not let a sender home automatically on connect: LightBurn's **Auto-home on
startup** stays off, and you run `$H` deliberately from its Console tab when you
want a true machine origin ([LightBurn](lightburn.md)).

## Manual homing

With `homing_mode = manual` you are the homing cycle. You push the head into
the home corner, and `$H` takes your word for it.

1. **Release the motors:** press **Release motors** on the panel's Machine
   tab, or send `$MD`. X and Y go limp so the gantry and the
   head move freely by hand. The machine stays on, and the lens is not
   released. The position is forgotten at once, and the machine locks: it
   reports ALARM:11 and refuses every move, from every source, until you end
   the release yourself. `$X` does not unlock it and a soft reset does not
   either, because your hands are on the gantry.
2. **Open the lid and push the head to the home corner:** the back-left
   corner, against the stop blocks. Push gently, and keep the gantry square
   to the machine as it goes back. Do not home against the bare factory
   corner: what the gantry meets there is springy, and what the head meets on
   the left is a cable.
3. **Close the lid and press Set home here** (Machine tab, shown while
   manual homing is the method), or send `$H`. The motors energize and hold, and the
   spot the head is in becomes `manual_home_x`, `manual_home_y`. Nothing
   moves. Z is left as it is: the lens carries its own reference
   ([Running unhomed](#running-unhomed)).

`manual_home_x` and `manual_home_y`, on the Machine tab, are the machine
coordinates the stop blocks stand for. Left blank, the blocks are the origin,
X0 Y0, and that is what most machines want. They are never negative, and
manual homing alone uses them: no other homing method reads them, and the
panel shows them only while manual homing is the method. The soft limits start at that position,
since the blocks are a wall, and end at the bed's travel.

To get out of a release without homing, press **Energize motors** (the same
button, while they are released) or send `$ME`: the motors energize, and X and
Y stay unreferenced until a home.

The panel's buttons and the `$` commands are the same operations. The buttons
go through the controller beside your Grbl client, so LightBurn stays
connected through the whole procedure, and its console shows each step. The
Status tab shows **X and Y motors: RELEASED** for as long as the release
stands.

**The soft limits are only as true as your placement.** After a manual home
the bed is the limit, exactly as after a camera home, but the machine cannot
check where you put the head. If the head was not in the corner, the whole
envelope is shifted by the same amount, and a move the limits allow can still
reach the frame. Your sender is told so at every manual home (`[MSG:Warning:
Manual home: position set where the head was placed. Soft limits may not match the
machine.]`). Home against the stop blocks, where an error leaves the far limits short
of the far frame rather than past it.

| While the motors are released | What you get |
|---|---|
| A jog, a `G0`, a program line | An error, and a `[MSG:]` that the motors are released. Nothing moves |
| `$X`, or a soft reset and then `$X` | Refused: error 9. The machine stays locked |
| `$H` with `homing_mode = gfcloud` | Refused: the homing session would energize the motors and move the head |
| `$ME` | The motors energize. X and Y stay unreferenced |
| `$H` with `homing_mode = manual` | The motors energize and the head's position becomes `manual_home_x`, `manual_home_y` |

`$MD` is refused while a program runs and while a laser job is armed.

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

Anything that invalidates position, an underrun, a stream fault, or a motor
release, drops the
anchor deliberately, so a stale origin cannot be reused. Re-home before you
trust coordinates again.

## Homing in cloud mode

Cloud homing is automatic and camera-based; the service runs it when the
machine connects and after prints. The lens hunt references Z against the hall
sensor. Connecting zeroes the machine's counters at the head's current
position, so GRBL-mode coordinates do not survive a switch to cloud mode and
back: re-home after switching ([Modes](modes.md), [Cloud mode](cloud-mode.md)).
