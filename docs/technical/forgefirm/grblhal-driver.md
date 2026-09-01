---
title: The grblHAL driver
---

# The grblHAL driver

`grblHAL-glowforge` is the controller of GRBL mode: a
[grblHAL](https://github.com/grblHAL) driver for the stock Glowforge
(Basic, Plus, and Pro) control board, the factory NXP i.MX6 SOM running
Linux. This page describes how the driver turns G-code into pulse bytes,
how it drives the laser, how a job is armed, and how it handles the lid,
the button, faults, and the cooling verdict.

- The operator's view of GRBL mode is [GRBL mode](../../usage/grbl-mode.md);
  sender setup is [LightBurn](../../usage/lightburn.md).
- The pulse-byte layout and the playback engine are
  [The step engine](../machine/step-engine.md).
- The laser hardware, the PWM, and the thresholds are
  [The laser](../machine/laser.md).
- The geometry, the speeds, and the limits are
  [The motion hardware](../machine/motion-hardware.md).
- Building the driver is [Build](../../developers/building.md).

## Architecture

The unmodified grblHAL core (a git submodule at `src/grbl`) runs as a Linux
userspace process. Steps are not fired from a GPIO ISR. The driver streams
**pulse bytes** (one byte per machine tick) into the kernel module's
SDMA + EPIT playback engine (`glowforge.ko`, `/dev/glowforge`), the same
jitter-free hardware step generator the factory firmware uses, fed live
from grblHAL's planner instead of from a cloud-generated file.

Three threads carry the work:

- **grbl protocol thread**: the parser, planner, and protocol loop. Grbl 1.1
  protocol over raw TCP (`-p 23`, compatible with LightBurn, UGS, and cncjs)
  or stdio.
- **stepper producer thread**: replaces a hardware step timer. It runs the
  core's stepper interrupt callback against a virtual step clock
  (1000 x the machine tick), wall-clock paced, and maps each step event onto
  the pulse-byte grid.
- **shipper thread** (`SCHED_FIFO`): writes due bytes to `/dev/glowforge`
  with a bounded queue (default 200 ms, which is also the feed-hold latency).
  It owns the kernel run/stop/streaming/underrun state machine and the
  factory's PIC run/hold stepper-current scheme.

The machine constants (steps/mm, maximum rates, accelerations) are measured
from the factory machine and its pulse streams. Their sources are noted in
[`src/boards/glowforge.h`](https://github.com/ScottW514/grblHAL-glowforge/blob/main/src/boards/glowforge.h);
the values are on [The motion hardware](../machine/motion-hardware.md).

Under the ForgeFIRM image the driver runs as a **supervised child of
forgectrl** and receives `/dev/glowforge` as a broker-inherited file
descriptor (`GF_PULSE_FD`). Handovers such as the `$H` homing session then
never close the device or cycle the 40 V motor rail. Standalone (no
`GF_PULSE_FD`), the driver opens the device itself, and every takeover runs
a deliberate rail-off settle (`rail_settle_s`). The broker and the rail
policy are described under [forgectrl](forgectrl.md).

## From G-code to pulse bytes

1. The sender streams G-code over TCP.
2. grblHAL parses it and plans motion in the usual way: look-ahead, junction
   deviation, acceleration ramps.
3. The producer thread runs the planner's step generator against a virtual
   clock a thousand times finer than the machine tick and places each step
   event on the byte grid.
4. The high-priority shipper thread writes due bytes to the pulse device
   roughly every 10 ms, keeping a bounded queue ahead of real time.

The queue depth is the trade: deeper means more immunity to system load,
shallower means a feed hold or a power override takes effect sooner. The
default is 200 ms, and the machine tick defaults to 28160 Hz, the same tick
the factory firmware uses for travel moves. The environment variables that
set the tick and the depth are on [GRBL mode](../../usage/grbl-mode.md).

The controller keeps only a small window of the job in the ring, a fraction
of a second, and refills it continuously while the job plays. A write that
would overflow is refused and the shipper backs off; that is normal flow
control, not an error. If the feed falls behind far enough to empty the
ring, the kernel enters the **underrun** state: motion stops instantly, and
position is no longer trusted. The ring semantics are
[The pulse-feeder contract](pulse-feeder-contract.md).

## Real-time design

The step timing itself is immune to the CPU: the hardware plays the bytes,
and no software runs between the timer and the pins. The software's only
duty is to supply bytes in time, and the design makes that duty cheap to
meet:

- The kernel runs with `CONFIG_PREEMPT=y`. A deep ring and a `SCHED_FIFO`
  shipper are enough; PREEMPT_RT is not selectable on arm32 6.12, and the
  buffer arithmetic makes it unnecessary
  ([The image and the BSP](image-and-bsp.md)).
- The shipper's queue is bounded (default 200 ms) so a feed hold or a power
  override takes effect within that time.
- The shipper never logs, except a fault. The shared `fflog` emitter uses a
  non-blocking socket, so a stalled log daemon can never park a controller
  thread ([Logging](logging.md)).
- A feed that does fall behind is detected as an underrun and treated as a
  fault, never as silent damage (see "Faults" below).

## Laser control

The laser path is `src/glowforge_laser.c`. grblHAL laser mode maps spindle
power onto the pulse stream's power bytes and fire bits:

- `$32` (laser mode) is **on by default**, so `M3`/`M4` and `S` behave the
  way senders expect. `M4` gives dynamic power scaled with speed through the
  acceleration ramps; `M3` gives constant power.
- `$30` is 1000, and S values map linearly onto the 7-bit power byte:
  `S1000` is full power, `S500` about half.
- Power changes are emitted ahead of the tick they apply to, so a power
  change and the motion it belongs to stay together.
- The **fire bit** (bit 4 of a step byte) requests emission for that one
  tick, and only that tick. Because power and fire travel with the steps,
  power and position cannot drift apart.
- Fire only ever rides motion segments of laser blocks. Jogs, rapids, and
  homing are fire-free by construction, not by convention.
- The driver obeys the three stream rules of the hardware: power before
  fire, no two power bytes in a row, and end dark. The reasons are on
  [The laser](../machine/laser.md). The duty setting persists after a
  program ends, so the laser-off guarantee rests on the fire bit and the
  hardware chain, never on power being zero.

**Dose model.** Density is the only model: every pulse fires at full power,
and the commanded level only masks FIRE ticks the core asked for, never adds
one, so emission stays exactly where the core commanded it. The density
base period is `laser_pulse_ticks` in machine ticks (35.5 us each at the
default tick), and `laser_pulse_min_ticks` is the shortest pulse; below it a
period is skipped and its debt carried. `laser_floor_density` is the S-range
floor, the lowest density that still marks; the driver loads it into `$35`
at every spindle precompute, so `$35` is derived, never typed. S commands a
light fraction, and `laser_dose_curve` maps it onto the density that
delivers it; `laser_corner_gamma` is the corner rolloff under `M4`. The
analog rendering (continuous FIRE at a duty) is not selectable on a machine.
It fires the tube's strike transient as a spot at every beam-on, and exists
only as the host harness's conservatism reference. The settings and their
defaults are on [Settings](../../usage/settings.md); the panel's recorder
that measures a machine's own curve is described under
[forgectrl](forgectrl.md).

**The laser latch.** The driver keeps the kernel's laser latch locked except
inside an operator-armed job window, and the kernel relocks it whenever the
pulse device is closed ([The kernel module](kernel-module.md)). The hardware
safety AND-chain stays authoritative regardless: an armed underrun fails
safe, and the latch relocks on disarm, alarm, and reset.

## The armed window

The first laser-on of a job does not fire. Instead the controller runs the
arm flow on the protocol thread:

1. **Checks the coolant verdict.** If a flow fault or an over-temperature
   condition stands, arming is refused outright
   ([The cooling engine](cooling-engine.md)).
2. **Checks that a print head is present.** No head, no arming: the lens,
   the air assist, and the beam detector live on the head, and the hardware
   chain has no head term. Presence is the head driver having probed (the
   `/sys/glowforge/head/` group exists), never the head-attention switch
   bit.
3. **Forces the cut airflow profile on**, so every fire window is covered
   by running fans and active flow verification.
4. **Unlocks the kernel laser latch, lights the button white, and pauses
   the job** until the operator presses the physical button. The sender
   keeps getting status reports, so it does not time out.

The hardware button latch is what the press clears. The software wait exists
so the job does not start streaming FIRE bits into a blocked gate. A press
with the lid open does not arm; the hardware button latch would not clear on
it either. A soft reset, or a lid or interlock open, cancels the job
instead. If nobody presses within `laser_button_timeout_s` (default 300 s),
the job ends in an alarm with the latch relocked. The coolant verdict is
re-checked after the press, so a window can never open against a fault that
appeared during the wait.

**The window is per job, not per fire.** It survives `S` changes and
`M5`/`M3` toggles, so nothing re-prompts mid-job. It closes, relocking the
latch, when any of these happens:

- program end (`M2`, `M30`, `%`), the normal case, within the cycle;
- the sender's connection changes (the consent belonged to that session);
- `laser_disarm_s` (default 60 s) of spindle-off idle, counted down in Hold,
  Door, and Tool Change as well as Idle;
- immediately on alarm, homing, reset, or a stream fault.

**Disarm.** After the disarm grace, or on program end or abort, the
controller relocks the latch, turns the button LED off, and stands the
cooling profile down. A job paused on the button is no laser use: the grace
counts down through the hold and closes the window under a job left
standing, so a long pause ends with the machine disarmed and the next
emission needs a fresh press. The relock waits for the kernel to finish the
queue tail, so a controlled stop can never leave FIRE driven.

The next job re-arms with a fresh button press, the same press the hardware
button latch itself requires. That is why software and hardware cannot
disagree about whether the machine is armed.

## Lid, interlock, and button

The safety inputs are `src/glowforge_switches.c`. The lid switches and the
remote-interlock loop drive the core's safety-door signal. The `doors` bit
(both lid switches closed, the series combination the hardware chain sees)
and the `interlock` bit (loop open) are read from the gpio-keys switch
device; the switch map is under [forgectrl](forgectrl.md).

**The safety door.** The signal is shown to the core only while it is in a
job-time state (cycle, hold, tool change, door). A running job parks with a
planned deceleration, and what happens next is the `lid_policy` setting:

- `cancel` (the default, and the factory firmware's behavior): the job is
  canceled. Motion stops within milliseconds of the switch edge, the armed
  window closes, the reason is reported, and a soft reset ends the sender's
  stream from a fully parked state, so the position is kept and no alarm is
  raised. The head then returns to where the job started, with the latch
  locked, lid open or not, exactly as the factory does. The return-home move
  always runs to completion. The next job re-arms with a fresh button press,
  which is also what clears the hardware button latch the lid set.
- `hold`: the stock Grbl door hold. The job parks in the Door state; once
  the door or loop closes the controller reports `Door:0`, and a cycle start
  finishes the move with its position intact.

During the arm wait (button lit), either opening cancels the job outright
under both policies.

While the core is idle, jogging, or homing, and during the return-to-start
motion after a cancel, the signal is hidden from it. The lid is opened at
idle every time material is loaded, and a door seen there would strand the
controller in Door. The signal is delivered the moment the core leaves
those states, so a job started with the lid open parks (and cancels) on its
first poll. Consequences:

- **Idle lid cycles are ignored.** Opening the lid to load material, or
  powering up with it open, does not leave the controller parked; senders
  connect normally.
- **Jogs are not lid-gated.** A jog both starts and runs with the lid open;
  the beam is blocked in hardware regardless.
- **Homing is lid-gated in practice**, even though the core does not see
  the door during `$H`. How, and the one part of a homing session that
  ignores the lid, is on [Homing](homing.md).

This is a motion and UX gate. The lid is *also* cut in hardware by the button
latch, and the interlock by the interlock latch
([The safing chain](../machine/safing-chain.md)).

**The button.** Outside the arm wait the button is the job pause/resume
toggle: a press while running is a feed hold, and a press while held is a
cycle start. A held button has no further meaning during a job. A pause is
deliberately **not** a cancel: the latch stays unlocked and the armed window
open, which is what lets the next press resume the job. Emission still ends
with the pause: the stream stops driving FIRE, and the chain drops HV_ENABLE
by itself ([The kernel module](kernel-module.md)). The window closes on its
own if the pause outlives the disarm grace. A cycle start after that, from
the sender or the button, re-arms first: the button lights and the press
resumes the job. A lid or interlock open while paused takes the cancel path,
so nothing resumes past an enclosure opening.

**Telemetry that gates nothing.** The `hv_enable` bit is the readback of the
board's HV_ENABLE output (high only while a run feeds the charge-pump
watchdog with the lid closed). It is telemetry and gates nothing.

## Faults

The operator's table of what each stop does is on
[GRBL mode](../../usage/grbl-mode.md). The mechanisms behind it:

- **Feed hold** is a controlled ramp to a stop with the position kept. The
  deceleration runs lit (velocity-scaled under `M4`), the stationary stretch
  is dark, and the disarm grace keeps counting.
- **Cycle start** resumes from the hold, lit from the first step, so a pause
  is a sharp corner in time and the corner rolloff governs its mark. The
  driver does not request a backtrack from the kernel (the ring keeps a
  retained gap that would allow one; see
  [Pulse feeder contract](pulse-feeder-contract.md)): the kernel's own stop
  plays the shipped bytes time-stretched with the beam on, which would
  over-dose more than the planned deceleration does. A resume against a
  window the grace has closed re-arms first: the button lights, and the
  press resumes the job.
- **A sender change while a job runs** holds the job and closes the window.
  The next sender finds the cut in Hold where it stopped and resumes it
  through the same re-arm, or resets it.
- **Jog cancel** is a controlled stop with the jog abandoned and the
  position kept.
- **Soft reset** (`^X`) is a controlled deceleration into Alarm with the
  latch relocked and the machine position retained; `$X` clears the alarm.
  A termination signal during motion is treated the same way: controlled
  stop, latch relocked, exit.
- **Underrun** stops motion instantly. While armed it is a hard fault: alarm,
  latch relocked, position invalidated, so the machine must be re-homed
  before its coordinates are trusted ([Homing](homing.md)). A motion-only
  job gets one sanctioned retry.
- **A coolant fault or over-temperature** verdict is a feed hold with the
  cut airflow forced on; fire is gated. Over-temperature resumes
  automatically once the loop recovers (see "The cooling client" below).
- **A controller crash or hang** is caught by forgectrl: it stops motion,
  relocks the latch, and restarts the controller ([forgectrl](forgectrl.md)).

Anything that invalidates position (an underrun, a stream fault) drops the
homing anchor deliberately, so a stale origin cannot be reused.

## The cooling client

Cooling is enforced in-process but owned by the forgectrl cooling engine,
the sole owner of the thermal hardware. The driver is a client of it over
two channels ([The cooling engine](cooling-engine.md) owns both formats):

- **Job-state reports.** The driver reports its job state to the engine
  (`POST /cool/state`: mode and armed, level-triggered at about 1 Hz). GRBL
  mode omits the per-job fan duties, so the engine's configured run profile
  applies. It also publishes `grbl.state` and `grbl.settings` under
  `/run/forgefirm`, written atomically on change from the protocol thread;
  forgectrl echoes them in its status ([forgectrl](forgectrl.md)).
- **The verdict.** The driver reads the engine's published verdict file,
  gates fire, and issues hold and resume from it. A missing or stale verdict
  reads as fire-blocked. The armed window requires a fresh `fire_ok` verdict
  (flow verification, over-temperature, the airflow floors on every fan, the
  lid-IR emission witness); a stale or failed verdict relocks in-process.
  Auto-resume after an over-temperature hold is the controller's call, on
  the verdict's `resume_ok`.

The thermal gates are settings with a wide range whose far end turns the gate
off by value, loudly ([Cooling and fans](../../usage/cooling-and-fans.md)).
The fresh-report rule, the emission witness, the dead-man, and the latch are
not settings and stay in force whatever the gates are set to.

**Emergency fallback.** If the verdict goes stale while the laser is armed,
the driver (besides gating fire and holding) writes the run fan duties
directly once, compiled-in factory values with no config dependency, then
stands down. This is the one sanctioned exception to the single-writer rule,
taken only when the single writer is provably absent.

## Witnesses

Position counters are not proof of motion: the step-stream drives are open
loop. The head accelerometer is the motion witness, and
`beam_detect_analog` on the head is the live emission witness.

## Homing handover

`$H` is a driver command that shadows the core's homing cycle. Under
`homing_mode = gfcloud` it suspends the stream engine, runs a service-driven
homing session in a child process that inherits the pulse device, and hands
the machine back. The mechanism is on [Homing](homing.md).

## Where the driver sits in the safety design

Every software layer sits *in front of* the hardware chain: it can only
withhold FIRE, hold the lock, or starve the charge pump. None can produce
emission the hardware would not allow. The driver's layer is the armed
window, the disarm, the dose model, the coolant fire gates, the safety
door, the button, and the witnesses, described above. The kernel's layer is
on [The kernel module](kernel-module.md), forgectrl's on
[forgectrl](forgectrl.md), and the chain itself on
[The safing chain](../machine/safing-chain.md).
