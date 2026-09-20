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

Four threads carry the work:

- **grbl protocol thread**: the parser, planner, and protocol loop. Grbl 1.1
  protocol over raw TCP (`-p 23`, compatible with LightBurn, UGS, and cncjs)
  or stdio.
- **stepper producer thread** (`SCHED_FIFO`): replaces a hardware step
  timer. It runs the core's stepper interrupt callback against a virtual
  step clock (1000 x the machine tick), wall-clock paced, and maps each step
  event onto the pulse-byte grid.
- **shipper thread** (`SCHED_FIFO`): writes due bytes to `/dev/glowforge`
  with a bounded queue (default 200 ms, which is also the feed-hold latency).
  It owns the kernel run/stop/streaming/underrun state machine and the
  factory's PIC run/hold stepper-current scheme. It builds each chunk under
  the engine's lock and writes it with the lock released, so a write that
  blocks never holds the producer.
- **cooling reporter thread**: reports the job state to the forgectrl
  cooling engine at 1 Hz ([Cooling engine](cooling-engine.md)).

The machine constants (steps/mm, maximum rates, accelerations) are measured
from the factory machine and its pulse streams. Their sources are noted in
[`src/boards/glowforge.h`](https://github.com/openglow-org/grblHAL-glowforge/blob/main/src/boards/glowforge.h);
the values are on [The motion hardware](../machine/motion-hardware.md).

### The XY scale

The X and Y microstep mode is one number in the shared config,
`xy_microsteps` (8, 16 or 32; unset reads as 32, and 8 is the factory's), read once at
the driver's start. Three things are derived from it and never typed:

| Mode | `$100`/`$101` (steps/mm) | Machine tick (Hz) | Kernel stop ramp (Hz/s) |
|---|---|---|---|
| 8 | 53.333 | 28160 | 125000 |
| 16 | 106.667 | 56320 | 250000 |
| 32 | 213.333 | 112640 | 500000 |

The tick scales with the mode so the ticks per step, and with them the
top speed, stay the same. The stop ramp is Hz per second of tick
frequency, so it scales with the tick in force to keep a controlled stop
over the same distance. `$100`/`$101` are re-asserted from the mode on
every settings dispatch, in RAM only, the way `$35` is: a `$100` typed by a
sender is overwritten on the spot. `$110`/`$111` are held under the feed the
tick carries (one step per tick per axis), which only bites when the bench
lowers the tick with `GFSINK_RATE`. `$102` (the lens screw's half-steps per
millimeter) and `$32` (laser mode) are pinned the same way: a typed `$102`
would move the Z envelope off the head, and laser mode is the machine's,
not a sender's choice. The driver writes the mode to the
drivers' MODE pins at its start, at idle. A change of the setting takes a
controller restart, which forgectrl does for an idle machine when the
setting is saved. Cloud mode runs at the service's own 8.

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
default is 200 ms, and the machine tick is the microstep mode's: 28160 Hz at
8, the same tick the factory firmware uses for travel moves, doubled at 16
and quadrupled at 32 ([The XY scale](#the-xy-scale)). The environment
variables that override the tick and set the depth are on
[GRBL mode](../../usage/grbl-mode.md).

The controller live-streams: it keeps a fraction of a second of the job in
the ring and refills it continuously, so a write that would overflow is
refused and the shipper backs off. That is normal flow control, not an error.
A feed that falls far enough behind to empty the ring is an **underrun**, and
that is a fault ([Step engine](../machine/step-engine.md#the-ring-and-two-ways-to-fill-it),
[Pulse feeder contract](pulse-feeder-contract.md)).

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
- The shipper logs only a fault and the start of a deferred run, through a
  raw write. The shared `fflog` emitter uses a non-blocking socket, so a
  stalled log daemon can never park a controller thread
  ([Logging](logging.md)).
- A feed that does fall behind is detected as an underrun and treated as a
  fault, never as silent damage (see "Faults" below).

### The protocol loop paces on the file descriptors

`serial_wait()` drains the transmit side and then waits on the listening and
client descriptors with a timeout that depends on the state: 10 ms at idle and
in alarm (1 ms while a delay callback is pending), 200 µs during motion, and
the coarse idle poll in the parked states, a completed feed hold, a door ajar
or closed, and sleep. The motion sub-phases that are still moving, a hold's
deceleration and a park retract or resume, keep the tight pace.

Traffic therefore wakes the loop at once while an idle machine ticks cheaply.
Measured on the bench reference: **2.7 percent of the core at idle, 34 to 35
percent during an active move, and 2.7 to 3.0 percent parked.** Client receive
is armed only while the ring has a full read's worth of room, so a sender that
ignores flow control is paced rather than spun on.

**Every sender that connects is welcomed with the banner**
(`GrblHAL 1.1f ['$' or '$HELP' for help]`), the way a UART build prints it at
power-up, so a sender that waits for the banner before it speaks does not sit
on a running controller in silence. The transmit ring holds 2048 bytes, and a
`$$` dump (about 750 bytes) queues whole. A sender that stops reading for a
second is dropped, and a drop is a sender change: a running laser job holds
and its window closes ([The armed window](#the-armed-window)).

### Idle is produced, not played

**The controller reports Idle when the stream is produced; the kernel is still
playing it, one queue depth behind.** The machine keeps moving for about one
depth after the status says Idle.

The tail is flat, not cumulative: chaining jogs does not grow it. Measured
against `cnc/state` across four chained 50 mm jogs, it read 171, 175, 177 and
176 ms. A `cnc/stop` issued at Idle discards whatever is still queued, and the
position counters stay true to what was actually played, so nothing is lost
except the rest of the move.

Anything that must keep position waits for `cnc/state` to read idle before it
stops the controller. forgectrl's own idle test reads that attribute, and the
mode switch, the cooling gate and the daemon shutdown all gate on it.
`POST /controller/stop` deliberately does not, because it is also the
emergency lever: it safes the machine with `cnc/stop` and the latch before the
signal instead ([forgectrl](forgectrl.md#mode-supervision)).

## Laser control

The laser path is `src/glowforge_laser.c`. grblHAL laser mode maps spindle
power onto the pulse stream's power bytes and fire bits:

- `$32` (laser mode) is **on by default**, so `M3`/`M4` and `S` behave the
  way senders expect. `M4` gives dynamic power scaled with speed through the
  acceleration ramps; `M3` gives constant power.
- `$30` is 1000, and S values command a light fraction of full through the
  dose curve: `S1000` is full power, and the density a lower S delivers is
  the one the curve maps its light fraction onto (see "The dose curve"
  below), not a linear share of the power byte.
- Power changes are emitted ahead of the tick they apply to, so a power
  change and the motion it belongs to stay together.
- The **fire bit** (bit 4 of a step byte) requests emission for that one
  tick, and only that tick. Because power and fire travel with the steps,
  power and position cannot drift apart.
- Fire only ever rides motion segments of laser blocks. Rapids and homing
  are fire-free by construction, not by convention. A jog carries the modal
  spindle in Grbl, so the stream masks fire for as long as the core is
  jogging: every jog tick ships dark whatever S is in force, and the cut
  after it lights from the state the jog did not disturb.
- The driver obeys the three stream rules of the hardware: power before
  fire, no two power bytes in a row, and end dark. The reasons are on
  [The laser](../machine/laser.md). The duty setting persists after a
  program ends, so the laser-off guarantee rests on the fire bit and the
  hardware chain, never on power being zero.

**Dose model.** Density is the only model: every pulse fires at full power,
and the commanded level only masks FIRE ticks the core asked for, never adds
one, so emission stays exactly where the core commanded it. The density
base period is `laser_pulse_ticks` in ticks of the 28160 Hz reference tick
(35.5 us each; the driver scales the count to the tick in force, so the
period is a time at every microstep mode), and `laser_pulse_min_ticks` is
the shortest pulse in the same ticks; below it a
period is skipped and its debt carried. `laser_floor_density` is the S-range
floor, the lowest density that still marks; the driver loads it into `$35`
at every spindle precompute, so `$35` is derived, never typed. S commands a
light fraction, and `laser_dose_curve` maps it onto the density that
delivers it; `laser_corner_gamma` is the corner rolloff under `M4`. `M102`
reloads the three inside a job, synchronized behind every buffered motion,
through the same spindle configuration the arm runs: the setup
sheet's cards change them between their passes. The
analog rendering (continuous FIRE at a duty) is not selectable on a machine.
It fires the tube's strike transient as a spot at every beam-on, and exists
only as the host harness's conservatism reference. The settings and their
defaults are on [Settings](../../usage/settings.md); the panel's recorder
that measures a machine's own curve is described under
[forgectrl](forgectrl.md).

**Why the model has the shape it has.** The base period ships at 20 reference
ticks, 710 µs, which is the factory's own roughly 1.43 kHz. The minimum pulse
ships at 3 ticks, 106 µs, because that is what the tube will re-strike: the
gap between pulses, not the pulse, is what decides at the low end, and a
longer minimum makes the gap longer in proportion
([The laser](../machine/laser.md#the-low-end-is-bounded-by-the-gap-between-pulses-not-by-the-pulse)).

Skipping a period carries its whole debt forward, so the average density is
untouched and only the texture changes. At level 2 the stream goes from 444
one-tick bursts to 147 three-tick bursts: the same density to four decimal
places, delivered as fewer, longer pulses the supply can actually strike.
Every level already above the minimum is bit-identical either way.

Structurally the model is a mask on the core's fire state and never a source
of one, which is what keeps it out of the safety argument: the armed window,
the latch, the coolant gates and the hardware chain are all upstream and
untouched. Emission stays exactly where the core commanded it.

Rasters hold their tonality down to about 14 pulse slots per pixel, which is
508 DPI at 6000 mm/min: the dither accumulator's averaging across pixels
recovers the levels, with no visible dither pattern.

**The laser latch.** The driver keeps the kernel's laser latch locked except
inside an operator-armed job window, and the kernel relocks it whenever the
pulse device is closed ([The kernel module](kernel-module.md)). The latch
has one writer in the process: every lock and unlock goes through the stream
engine, which records which way this process last wrote it. A write that
fails is tried three times, 10 ms apart. A lock that still fails is a stream
fault (the window closes, the homing anchor drops, the job alarms), and an
unlock that fails refuses the arm. A run start unlocks only a lock this
process wrote inside an open window with the fire gate open; a lock it did
not write, the cooling engine's fail tier, is never undone: the job plays
dark and the verdict closes the window. Locking the latch also sets the
hardware button latch, which only a physical press clears, so every lock the
software writes costs a new press by construction. The hardware safety
AND-chain stays authoritative regardless: an armed underrun fails safe, and
the latch relocks on disarm, alarm, and reset.

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
3. **Checks that the button can be read.** On hardware the button is an
   EV_SW bit on the input device the device tree names `switches`; no
   device, no arm, because a button that cannot be read is no consent.
4. **Forces the cut airflow profile on**, so every fire window is covered
   by running fans and active flow verification.
5. **Unlocks the kernel laser latch, lights the button white, and pauses
   the job** until the operator presses the physical button. The sender
   keeps getting status reports, so it does not time out; the `ok` for the
   line that armed the laser follows the press.

The hardware button latch is what the press clears. The software wait exists
so the job does not start streaming FIRE bits into a blocked gate. A press
counts only after the button has been seen released during the wait, so a
button held from before the job never arms. A press with the lid open does
not arm; the hardware button latch would not clear on it either. A soft
reset, a lid or interlock open, a sender change (the consent belongs to the
session that asked), or three unreadable switch reads in a row cancel the
job instead. If nobody presses within `laser_button_timeout_s` (default
300 s), the job ends in an alarm with the latch relocked. Check mode (`$C`)
never arms: a dry run keeps the laser off. The coolant verdict is re-checked
after the press, so a window can never open against a fault that appeared
during the wait.

The re-check waits for a verdict that answers this job. Forcing the airflow
profile on is a report to the cooling engine, and the engine applies the run
duties and the flow interrogation when it reads that report. Until it does,
the verdict on file is the one computed for the idle session before the arm,
which says fire is fine because at idle nothing is wrong. So the controller
holds at the re-check until the engine's own armed flag comes back in the
verdict, and refuses the job if it does not arrive within five seconds. A
press that lands the instant the button lights is the case this covers: it
reaches the re-check before the engine has ticked, and without the wait the
first fire goes out with the fans still at their idle duty.

**The window is per job, not per fire.** It survives `S` changes and
`M5`/`M3` toggles, so nothing re-prompts mid-job. It closes, relocking the
latch, when any of these happens:

- program end (`M2`, `M30`, `%`), the normal case, within the cycle;
- the sender's connection changes (the consent belonged to that session);
- `laser_disarm_s` (default 60 s) of spindle-off grace, counted down in
  Idle, in a jog, and in a job parked in Hold, Door, and Tool Change; only a
  cycle or a lingering `M3` keeps the window open, and a jog is not the job
  the press consented to;
- the cooling verdict's fail tier (`FIRE`, `CRASH`, `AIRFLOW`, `CRITICAL`):
  the latch locks, the job is reset the way `^X` resets it, and `ALARM:3`
  says why ([The cooling client](#the-cooling-client));
- immediately on alarm, homing, reset, or a stream fault.

Nothing widens the window. A jog under an open window ships dark and does not
restart the grace, and the pause tier of the verdict holds the job under the
window without touching the latch.

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
device; the switch map is under [forgectrl](forgectrl.md). On hardware the
device must be the one the device tree names `switches` (`GF_SWITCH_DEV`
points a bench at another path). A device that cannot be opened refuses the
arm, and a read that fails is never "still closed": a failing read ends an
arm wait, and a lid cancel in flight goes on to its reset and its park
without waiting on the device.

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

    The deceleration is lit in both spindle modes, and it has to be: the
    core's own laser-off-during-hold acts only once the hold has *completed*,
    so the beam goes off at the end of the ramp, never at its start. Measured
    on the stream at the 28160 Hz tick, a 100 mm/s cut at `S500`: under `M4`
    the density follows velocity down to the floor (2.9 fire ticks per step at
    cruise, 5.4 in the last 25 ms at 13 mm/s), and under `M3` the fire rate
    stays constant through the ramp, so fire per step rises from 2.9 to 22.
    That is the `M3` corner dose, and it is why `M4` is the mode to pause in.
    Between the last step and the first step the stream is dark.

- **Cycle start** resumes from the hold, **lit from its first step** in both
  modes (measured: the first fire lands 9 ticks after the first step under
  `M4`, with the deceleration's profile in reverse). So a pause is a sharp
  corner in time, and the corner rolloff governs its mark.

    There is no resume dwell, and none is warranted: the safing chain is back
    within about 3 ms of the resume while motion only restarts about 219 ms
    later, so the chain re-arms roughly 216 ms *before* the first step
    ([the kernel module](kernel-module.md#safety-functions)).

    The driver does not request a backtrack from the kernel (the ring keeps a
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
- **After any stream fault** (an underrun, a kernel fault, a refused run, a
  write error) the alarm stands until `$X`. The unlock acknowledges the fault:
  the kernel is stopped and re-armed, what the ring still held is cleared, and
  the controller moves again without a restart. The position stays invalid
  until a re-home.
- **The cooling verdict** has two tiers ([The cooling client](#the-cooling-client)):
  the pause tier is a feed hold under the open window, resumed with no
  press when the verdict clears; the fail tier ends the job with `ALARM:3`.
- **Late step events.** A producer that falls behind real time (starved of
  CPU) has its late events clamped forward onto later bytes, and the clamp
  is counted. Unarmed that is a warning in the log and the move completes.
  Inside an armed window it is a fault (`ALARM:17`): the burst the clamp
  compresses onto later bytes is energy where it was not commanded, so the
  stream stops the kernel, the latch locks, and the anchor drops.
- **Uncommanded emission.** Once a second the driver reads the emission
  sample count on the gated output (`cnc/laser_on_sampled`). Emission with
  the window closed for more than 3 s (the sample window's lag past a
  disarm) locks the latch and raises `ALARM:3`. The cooling engine runs the
  same witness from its side ([The cooling engine](cooling-engine.md#the-fire-watch)).
- **A kernel state that cannot be read** is never "still playing". The
  relock after a job waits for the kernel to idle, a state that stays
  unreadable is relocked after 2 s, and a run is refused rather than
  started against a state the driver cannot read.
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
- **The verdict.** The driver reads the engine's published verdict file
  every 500 ms and enforces the cached flags on every poll. A missing or
  stale verdict (older than 2 s) reads as fire-blocked and held. The armed
  window requires a fresh `fire_ok` verdict (flow verification,
  over-temperature, the airflow floors on every fan, the lid-IR fire watch)
  and the engine's own `armed` acknowledgment. Inside an open window the
  verdict has two tiers, keyed on its name:
    - `FIRE`, `CRASH`, `AIRFLOW`, and `CRITICAL` are the fail tier. The
      window closes, the latch locks, the job is reset the way `^X` resets
      it, and `ALARM:3` is raised. Nothing resumes it.
    - Every other `fire_ok=false` verdict, and a stale one, is the pause
      tier. The job is held under the open window: the first deceleration
      runs lit and the fire gate masks from the stop on, a resume under the
      standing verdict (the button, `~`, a sender) moves dark and is held
      again within the next poll with the sender told why, and the clean
      verdict's `resume_ok` resumes the hold the driver took, with no new
      press. The pause tier never writes the latch: a lock sets the hardware
      button latch, which only a press clears, so a lock belongs to the fail
      tier alone.
- **The fire gate.** The stream engine masks the FIRE bit on every tick with
  a gate the laser module publishes: the window, and the verdict's
  `fire_ok`, held open through the pause tier's first deceleration. A gate
  that falls clears the fire state in flight and every queued fire-on, so no
  fire in flight survives a closed window beyond the bytes already in the
  kernel's queue, and fire returns only when the core asserts it again.

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
`beam_detect_analog` on the head is the live emission witness; the driver's
own check of it once a second is under [Faults](#faults).

## Homing handover

`$H` is a driver command that shadows the core's homing cycle. Under
`homing_mode = gfcloud` it suspends the stream engine, runs a service-driven
homing session in a child process that inherits the pulse device, and hands
the machine back. Under `homing_mode = manual` it moves nothing and declares
the spot the operator put the head in (against the stop blocks) as `manual_home_x`, `manual_home_y`. `$MD` and `$ME` release and
energize the X and Y motors for that, and while they are released the driver
holds the machine in the alarm state so that nothing moves. The mechanism is
on [Homing](homing.md).

## The controller port

Beside the Grbl socket the driver serves a second, local channel,
`/run/forgefirm/grbl.ctl`: forgectrl jogs and reads state through it without
displacing the Grbl client, and the panel's motor release and manual home go
through it. Its only motion is `$J=`, the one motion the stream ships dark
whatever the modal laser state is. The wire format, the two operation sets,
and the sender-goes-first rule are on
[The controller port](controller-port.md).

## The lens (Z)

The driver's Z is the focal point's height above the tray: Z 0 focuses on
the bed, Z 3 focuses 3 mm above it, on the top of 3 mm material. The lens is
a 2 in lens under a collimated beam, so the focal point moves 1:1 with the
lens and +Z is lens up; the travel is the lens carriage's 0.485 in
([The motion hardware](../machine/motion-hardware.md#the-lens-and-its-travel)).
Every head shares the lens screw and its travel, so the Z scale is a
constant: `$102` is 2.922 half-steps per millimeter (36 over the carriage's
12.32 mm), about 0.34 mm a half-step. What differs from head to head is the
step along the travel at which the hall sensor trips. That rising edge is
the one reference the head has, and the setup focus card measures
the one number the head needs: `lens_hall_edge_z_mm`, the focal height above
the tray when the lens sits on it. A home in gfcloud mode leaves the lens on
that edge, sets Z to the number, placed on the whole step the controller
counts (so the reported position and the home position agree), and then
parks the focus at `lens_park_z_mm`, a user setting (default 3 mm; the runner
takes the whole half-steps from the edge to the nearest step at the park
height). The park and the Z envelope keep to the head's free travel as the
focus card found its stops (`lens_stop_below_steps`, `lens_stop_above_steps`),
or, until it has or when the stops could not be found, to the fallback
window of ten half-steps below the edge to twelve above; the lens is never
driven onto a stop on a user's machine. The defaults are the bench
bench reference's, placeholders until the card has run. The homing
session answers the service's lens hunt as done without moving the lens;
the lens reference is the session's own, after the service goes quiet.
The lens is in the pulse path like X and Y: a job's or a jog's Z moves it,
in half-steps, at its drive current during a run and its hold current at
rest. The lens is never moved without a reference: the driver's Z soft limit
is always on, whatever `$20` says, and until Z is referenced it holds Z
where it is (a jog is refused with error 15, a program move raises the
soft-limit alarm before it starts). X and Y join it after a home: a
successful home turns the driver's X and Y soft limits on with the bed as
the envelope (`$130` by `$131` from the home corner), whatever `$20` says,
and whatever invalidates the position (an underrun, a stream fault, a new
homing session) turns them off again
([Homing](homing.md#the-position-after-a-home)). In practice Z is referenced from the
start: forgectrl sweeps the lens onto its hall edge before the controller
exists, and the driver takes that reference as it loads its settings, which
opens the envelope to the head's free travel (the found stops, a half-step
of slack at each end). The daemon steps the lens over GPIO, which the kernel
counters never see, so the driver re-zeroes them at the reference and
anchors Z alone. A gfcloud home references the lens the same way and anchors
all three axes. Beyond the free travel, referenced, the same refusal. The
panel's Machine tab shows the reach, and Z reads its height while X and Y
still show as unreferenced
([Homing](homing.md#the-lens-reference-at-every-start)).

## Where the driver sits in the safety design

Every software layer sits *in front of* the hardware chain: it can only
withhold FIRE, hold the lock, or starve the charge pump. None can produce
emission the hardware would not allow. The driver's layer is the armed
window, the disarm, the dose model, the coolant fire gates, the safety
door, the button, and the witnesses, described above. The kernel's layer is
on [The kernel module](kernel-module.md), forgectrl's on
[forgectrl](forgectrl.md), and the chain itself on
[The safing chain](../machine/safing-chain.md).
