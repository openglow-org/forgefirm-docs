---
title: GRBL mode
---

# GRBL mode

GRBL mode turns the machine into a standard Grbl-speaking laser cutter. This
page tells you how to connect a sender, how the laser is armed and mapped, and
what pausing, stopping, the lid, and the button do.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

GRBL mode is the default mode and the one to use for your own designs
([Modes](modes.md)). How the controller turns G-code into the pulse stream, and
the state machine behind the behavior on this page, are in
[The grblHAL driver](../technical/forgefirm/grblhal-driver.md).

## Connecting

The controller speaks **Grbl 1.1 over TCP port 23**. Point LightBurn, UGS,
cncjs, or any Grbl sender at the machine's address on port 23. Setup details
and a first job are in [LightBurn](lightburn.md).

Only one sender at a time is meaningful. Opening a second connection displaces
the first. That is also why the web panel reads position from the machine's own
counters and never from the Grbl socket.

A TCP disconnect never stops the controller process. A disconnect during a
laser job holds the job where the cut stopped (see the table below). Jog from
a sender's console with a standard jog command, for example `$J=G91X40F1200`.

??? note "Running the controller by hand"

    Under ForgeFIRM the controller `grblHAL_glowforge` is a supervised child
    of `forgectrl`, which hands it the pulse device. You do not start it
    yourself. For bench or debug work it can run standalone, once the
    supervisor has released the device (`POST /controller/stop`):

    ```sh
    GFSINK=/dev/glowforge grblHAL_glowforge -p 23 -e /data/EEPROM.DAT
    ```

    Environment: `GFSINK` (the pulse device; unset = null-sink test mode),
    `GFSINK_RATE` (the machine tick, default 28160 Hz, the factory's own
    travel-move tick; accepted 1000 to 165000), `GFSINK_DEPTH_MS` (the queue
    depth, default 200; at least 20 and no more than half the stream ring at
    the chosen rate). An out-of-range value is reported and the default is
    used. Standalone, the driver opens the device itself and every takeover
    runs a deliberate rail-off settle (`rail_settle_s`).

## Laser mapping and power

- `$32` (laser mode) is **on by default**, so `M3`/`M4` and `S` behave the way
  senders expect. `M4` gives dynamic power scaled with speed through
  acceleration ramps; `M3` gives constant power.
- `$30` is 1000, and S values map onto the laser drive with `S1000` = full
  power. Set your sender's S-value maximum to 1000.
- Power changes are emitted ahead of the tick they apply to, so a power change
  and the motion it belongs to stay together.
- An S value commands a fraction of the light, not a fraction of the pulses:
  the controller maps it through a measured dose curve onto the pulse density
  that delivers it. Every power level marks, low levels included.
  [LightBurn, Power](lightburn.md#power) explains the model as you meet it,
  and [Settings](settings.md) lists the laser keys.
- `$35`, the power floor, is derived from the `laser_floor_density` setting
  at every job. Do not type it; the controller overwrites it.
- A change to a spindle `$` setting takes effect when the controller restarts
  (a mode switch away and back, or a reboot). `$$` reports the new value at
  once, but the mapping in force stays the one loaded at start.

Fire only ever rides motion segments of laser blocks. Jogs, rapids, and homing
are fire-free by construction, not by convention.

## Arming: the button press is part of every job

The first laser-on of a job does not fire. Instead the controller:

1. **Checks the coolant verdict.** If a flow fault or an over-temperature
   condition stands, arming is refused outright
   ([Cooling and fans](cooling-and-fans.md)).
2. **Checks that a print head is present.** No head, no arming.
3. **Forces the cut airflow profile on**, so every fire window is covered by
   running fans and active flow verification.
4. **Unlocks the kernel laser latch, lights the button white, and pauses the
   job** until you press the physical button. The sender keeps getting status
   reports, so it does not time out.

A press with the lid open does not arm; the hardware button latch would not
clear on it either. A soft reset, or a lid or interlock open, cancels the job
instead. If nobody presses within `laser_button_timeout_s` (default 300 s), the
job ends in an alarm (alarm 3) with the latch relocked. The coolant verdict is
re-checked after the press, so a window can never open against a fault that
appeared during the wait.

**The window is per job, not per fire.** It survives `S` changes and `M5`/`M3`
toggles, so nothing re-prompts mid-job, and it closes, relocking the latch,
when any of these happens:

- program end (`M2`, `M30`, `%`): the normal case, within the cycle;
- the sender's connection changes (the consent belonged to that session);
- `laser_disarm_s` (default 60 s) of spindle-off idle, counted down in Hold,
  Door, and Tool Change as well as Idle;
- immediately on alarm, homing, reset, or a stream fault.

The next job re-arms with a fresh button press: the same press the hardware
button latch itself requires, which is why software and hardware cannot
disagree about whether the machine is armed. The mechanism behind the
window is on [The grblHAL driver](../technical/forgefirm/grblhal-driver.md).

## Pausing, stopping, and faults

| You do | What happens |
|---|---|
| Feed hold (`!`) | Controlled ramp to a stop, position kept. The ramp runs lit (velocity-scaled under `M4`), the stop is dark, and the disarm grace keeps counting. |
| Cycle start (`~`) | Resumes from the hold, lit from the first step: a pause is a sharp corner in time, and the corner rolloff governs its mark. If the grace closed the window during the pause, the button lights first and your press resumes the job. |
| Your sender disconnects mid-job | The job is held where the cut stopped and the window closes. The next sender finds it in Hold: `~` lights the button and a press resumes it, or `^X` ends it. |
| Jog cancel (`0x85`) | Controlled stop, jog abandoned, position kept. |
| Soft reset (`^X`) | Controlled deceleration into Alarm, latch relocked, machine position retained; `$X` clears the alarm. |
| Press the button mid-job | Pause; press again to resume (below). |
| Open the lid or the interlock loop | The job is **canceled**, not paused (below). |
| Ring runs dry (underrun) | Motion stops instantly. While armed this is a hard fault: alarm, latch relocked, position invalidated; re-home before trusting coordinates. A motion-only job gets one sanctioned retry. |
| Coolant fault or over-temp | Feed hold with cut airflow forced on; fire is gated. Over-temp resumes automatically once the loop recovers. |
| Controller crash or hang | The daemon stops motion and relocks the latch, then restarts the controller. |

The controller clamps any feed faster than its limits: travels run up to
200 mm/s (`$110`/`$111` = 12000 mm/min).

## Lid, interlock, and button

ForgeFIRM reproduces the factory machine's behavior:

- **A lid or interlock open during a job cancels it.** Motion stops within
  milliseconds of the switch edge, the job is not resumable, the latch relocks,
  and the head returns to the position the job started from, **with the lid
  still open**, exactly as the factory does. The return-home move always runs
  to completion.
- **The button pauses and resumes.** In GRBL mode a press is a feed hold and
  the next press is a cycle start. A pause is not a cancel: the armed window
  stays open across it. A pause longer than the disarm grace closes the
  window; the next press then lights the button and re-arms before the job
  resumes.
- **Idle lid cycles are ignored.** Opening the lid to load material, or
  powering up with it open, does not leave the controller parked. Senders
  connect normally.
- **Jogs are not lid-gated.** A jog both starts and runs with the lid open;
  the beam is blocked in hardware regardless.
- **Homing needs the lid closed.** With `homing_mode = gfcloud` the cycle is a
  cloud homing session, and its move to the home corner is an ordinary motion
  action: refused with the lid open, and stopped if the lid opens partway
  through. The camera steps need the lid closed anyway. Only the lens hunt
  inside that session ignores the lid ([Homing](homing.md)).

If you prefer stock Grbl door behavior, set `lid_policy = hold` (the GRBL
tab): the job parks in the Door state, and a cycle start after the lid closes
finishes the move with its position intact. The button still has to be pressed
before the beam can return.

## Homing, and running unhomed

The homing method is a setting, `homing_mode`, chosen in the web panel:
`gfcloud` (camera homing through the Glowforge service), `switches` (the
planned limit-switch cycle, not available), or `none` (`$H` is rejected).
[Homing](homing.md) has the procedure.

**The machine cuts fine unhomed.** Without a reference, coordinates are
relative to wherever the head happened to be, so the panel shows position in
red to say so, and your sender should use a job-start mode that does not depend
on machine coordinates ([LightBurn, Job start mode](lightburn.md#job-start-mode)).
After a successful home the position is anchored and shown normally.

Anything that invalidates position, an underrun or a stream fault, drops the
anchor deliberately, so a stale origin cannot be reused.

## Fans

In GRBL mode the cut fan profile follows your sender's `M8`/`M9` (LightBurn's
per-layer Air Assist), OR'd with the armed window: while the laser is armed the
fans run the cut profile whatever the sender says
([Cooling and fans](cooling-and-fans.md)).
