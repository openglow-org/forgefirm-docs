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

The grblHAL core (the project's fork, a git submodule at `src/grbl`; its
changes are listed in the fork's `FORK-CHANGES.md`) runs as a Linux
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
millimeter), `$32` (laser mode), bit 0 of `$63` (laser off in a hold) and
`$44`-`$46` (the homing cycle masks) are
pinned the same way: a typed `$102` would move the Z envelope off the head,
laser mode is the machine's, not a sender's choice, a held job's laser is
off whatever a sender typed (the disarm grace under a hold rests on it; the
other bits of `$63` stay the sender's), and the core keeps an
axis homed only while a homing cycle names it, so a typed `$44` would drop
the Z homed bit that the lens hold rests on. The cycles stay the core's
defaults (`$44=4`, `$45=3`, `$46=0`); the driver's `$H` never runs them
([Homing handover](#homing-handover)). The driver writes the mode to the
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
- The shipper logs only faults and warnings, through a raw write. The
  shared `fflog` emitter uses a non-blocking socket, so a stalled log
  daemon can never park a controller thread ([Logging](logging.md)).
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
through the same spindle configuration the arm runs: the setup's Laser
floor burn turns the floor and the curve off for its rungs that way. The
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
hardware button latch, which only a press taken with the lock released
clears ([The safing chain](../machine/safing-chain.md#logic)), so every lock
the software writes costs a new press by construction. The hardware safety
AND-chain stays authoritative regardless: an armed underrun fails safe, and
the latch relocks on disarm, alarm, and reset.

## The armed window

The first laser-on of a job does not fire. Instead the controller runs the
arm flow on the protocol thread:

1. **Checks the coolant verdict.** If an over-temperature or another
   cooling hold stands, arming is refused outright with `ALARM:3`
   ([The cooling engine](cooling-engine.md)). The refusal says
   `laser fire blocked: a cooling gate is closed`, or, while a fault waits
   for its Acknowledge (the verdict's `ack_wait`, under any verdict name),
   `laser fire blocked: a fault waits for its Acknowledge on the
   control panel`
   ([The operator's attention](cooling-engine.md#the-operators-attention)).
   The re-check after the press uses the same words. Every refused arm,
   and a wait that ends without a press (the button timeout, a sender
   change, unreadable switches, an alarm under the wait), also resets the
   job the way `^X` resets it, and the alarm stands through the reset:
   the parser drops the job's `M3`/`M4` and the rest of the stream, so
   after `$X` the next laser-on asks for the press again. A lid or
   interlock opening during the wait cancels the job with the reset alone
   (below).
2. **Checks that a print head is present.** No head, no arming: the lens,
   the air assist, and the beam detector live on the head, and the hardware
   chain has no head term. Presence is the head driver having probed (the
   `/sys/glowforge/head/` group exists), never the head-attention switch
   bit.
3. **Checks that the button can be read.** On hardware the button is an
   EV_SW bit on the input device the device tree names `switches`; no
   device, no arm, because a button that cannot be read is no consent.
4. **Forces the cut airflow profile on**, so every fire window is covered
   by running fans.
5. **Unlocks the kernel laser latch, sets the button breathing white, and
   pauses the job** until the operator presses the physical button. The
   sender keeps getting status reports, so it does not time out; the `ok`
   for the line that armed the laser follows the press.

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
duties when it reads that report. Until it does,
the verdict on file is the one computed for the idle session before the arm,
which says fire is fine because at idle nothing is wrong. So the controller
holds at the re-check until the engine's own armed flag comes back in the
verdict, and refuses the job if it does not arrive within its wait
([The cooling engine](cooling-engine.md#airflow-gates-a-fan-that-is-not-moving-the-air),
"The first fire waits for the fans"). A press that lands the instant the
button starts breathing is the case this covers: it reaches the re-check before the
engine has ticked, and without the wait the first fire goes out with the
fans still at their idle duty. The window belongs to the sender that asked
for the press: a sender that changes during this wait cancels the job as a
change during the button wait does (`sender changed during arm - job
canceled`, `ALARM:3`, the reset), and the poll closes an open window whose
sender is any other.

**The window is per job, not per fire.** It survives `S` changes and
`M5`/`M3` toggles, so nothing re-prompts mid-job. It closes, relocking the
latch, when any of these happens:

- program end (`M2`, `M30`), the normal case, within the cycle. A `%` is
  not a program end here: the core reports one only for a program read
  from a file stream, which the TCP transport is not, so a program that
  ends on `%` closes its window by the grace;
- the sender's connection changes (the consent belonged to that session);
- `laser_disarm_s` (default 60 s) of grace. It counts with the laser off
  in Idle, in a jog, and in a job parked in Hold, Door, and Tool Change,
  and with `M3`/`M4` still modal whenever the machine is at rest: Idle with
  nothing planned, or a jog. A window does not outlive its job at rest, and
  a jog is not the job the press consented to. Only a cycle, or a laser
  the core left on in a parked job, keeps the window open, and bit 0 of
  `$63` is pinned so that a hold leaves it off
  ([The XY scale](#the-xy-scale));
- the cooling verdict's fail tier (`FIRE`, `CRASH`, `AIRFLOW`, `CRITICAL`):
  the latch locks, the job is reset the way `^X` resets it, and `ALARM:3`
  says why ([The cooling client](#the-cooling-client));
- on a home of either kind (the web-service home as it enters the homing
  state; the manual home, which never leaves Idle, at the completion event
  every provider ends on), a stream fault, or a reset at rest: at once. A
  soft reset during motion, and an alarm the core reports before the
  driver's poll sees it, close the window after the core's alarm report
  ([Faults](#faults)).

Nothing widens the window. A jog under an open window ships dark and does not
restart the grace, and the pause tier of the verdict holds the job under the
window without touching the latch.

**The parser's `M3`/`M4` goes with the window.** The core asks the spindle
only when an `M3`, `M4`, or `M5` changes the modal state, so a window that
closed with `M3`/`M4` still modal would leave the next job's identical word
asking nothing: no arm and no prompt. When a window closes that way with no
job parked, the controller turns the modal state off once, at Idle
(`modal_poll`, through the core's `gc_spindle_off`: `M5` and `S0` in the
parser and in the reports), and says
`laser off (M5): the armed window closed - the next M3 or M4 asks for the button`.
The next `M3`/`M4` is then a state change and runs the arm. A job parked in
Hold, Door, or Tool Change keeps its `M3`/`M4`: the resume gate re-arms a held job by that
state ([Lid, interlock, and button](#lid-interlock-and-button)), and a
window that opens again cancels the drop.

**A stalled job does not run on dark.** The drop takes `M3`/`M4` from under
whatever was in progress, and a job that had only stalled (a sender that
stopped sending for longer than the grace, a long dwell) would carry on with
the laser off. From the drop on, the first feed move that the core plans
with the laser off under an `S` above zero ends the job
(`dark_watch_poll`): the sender is told
`the laser window closed while the job waited - job stopped; start it again`,
the job is reset the way `^X` resets it, and `ALARM:3` follows. The drop
zeroes the modal `S`, so that `S` is a word the job sent after it; a feed
move with no `S` word or with `S0`, a rapid, and a jog move on. The newest
planned block is looked at on every poll and each time the core reads the
sender's stream, which follows the line that planned it. The watch ends at
an `M3` or `M4` (the arm asks for its own press), a program end, a reset or
an alarm, any disarm, and a window that opens. One limit stands: an `M5`
that changes nothing never reaches the driver, so after such a drop a
stream that sends `M5` and then feed moves with `S` words is stopped once,
where it would have run dark.

**Disarm.** After the disarm grace, or on program end or abort, the
controller relocks the latch, turns the button LED off, and stands the
cooling profile down. A job paused on the button is no laser use: the grace
counts down through the hold and closes the window under a job left
standing, so a long pause ends with the machine disarmed and the next
emission needs a fresh press. The relock waits for the kernel to finish the
queue tail, so a controlled stop can never leave FIRE driven. A laser-on
that arrives while a program end's close is still waiting for that tail
belongs to the next job: the controller waits for the tail (2 s at most),
closes the window, and runs the arm, so it gets a press of its own. In a
held state the window closes at once.

The next job re-arms with a fresh button press, the same press the hardware
button latch itself requires. That is why software and hardware cannot
disagree about whether the machine is armed.

## Lid, interlock, and button

The safety inputs are `src/glowforge_switches.c`. The lid switches and the
remote-interlock loop drive the core's safety-door signal. The `doors` bit
(both lid switches closed, the series combination the hardware chain sees)
and the `interlock` bit (loop open) are read from the gpio-keys switch
device; the switch map is under [forgectrl](forgectrl.md). The
device must be the one the device tree names `switches`; on a host,
`GF_SWITCH_DEV` points a null-sink run at another path, a test hook the
controller ignores with `GFSINK` set
([Building](../../developers/building.md#grblhal-glowforge)). A device
that cannot be opened refuses the
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

During the arm wait (the button breathing), either opening cancels the job outright
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
the sender or the button, goes through the resume gate
(`gflaser_resume_gate`) and re-arms first: the latch unlocks, the button
breathes white (`press the button to resume the laser job`), and the press
is recorded once the button has been seen up. The window opens, and the
cycle start follows, when the cooling engine has acknowledged the job
(its `armed` in the verdict), inside the same budget as at the first arm;
an acknowledgment that does not arrive refuses the job with `ALARM:3`.
The press and the acknowledgment are both taken from the poll, because a
blocking wait cannot run in a held state. The switches are read through
the whole re-arm, the wait for the acknowledgment included. A sender
change or a button timeout ends the re-arm with the latch relocked and the
job still held; under a standing pause-tier verdict, or a fault that waits
for its Acknowledge, the gate refuses and the job stays held
([The cooling client](#the-cooling-client)). A lid or interlock open while
paused takes the cancel path, so nothing resumes past an enclosure opening.

**The button's light** (`button_lamp`) has three states of the
controller's own: breathing white while the arm or the re-arm waits for the
press, solid white while the core is in a cycle, a jog, or homing (set from
`gflaser_poll`, except while an arm wait has the button), and dark
otherwise, a job paused or held included: a paused job's button breathes
only once a resume has asked for the re-arm's press, and is dark again
from that press to the resume. A write happens on a change,
and it stops the LED trigger's pulse before the new pattern. Once a second
(`lamp_keep`, from `gflaser_poll`) the controller reads the LED back against
the state it set and writes that state again if something wrote over it,
never over the cooling engine's red flash, which stands over all three
([The button's light](forgectrl.md#the-buttons-light)). The lamp that
follows the machine's state is not written over the flash either
(`lamp_follow`): a change under it is recorded, and `lamp_keep` writes it
within a second of the flash ending. The flash leaves
the button dark when it ends, so an arm or re-arm wait under it breathes
again within a second. Solid white is judged as no pulse and every target
at 255 ([LEDs](kernel-module.md#leds)).

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
    window the grace has closed re-arms first: the button breathes white,
    the press is taken, and the job resumes once the cooling engine has
    acknowledged it ([Lid, interlock, and button](#lid-interlock-and-button)).
- **A sender change while a job runs** holds the job and closes the window.
  The next sender finds the cut in Hold where it stopped and resumes it
  through the same re-arm, or resets it.
- **Jog cancel** is a controlled stop with the jog abandoned and the
  position kept.
- **Soft reset** (`^X`) during motion takes effect once the core has
  reported the alarm (`ALARM:3`), which holds 100 ms. Until then the
  kernel plays its queue at the commanded rate, lit where the job is
  lit. Then the driver relocks the latch, the kernel ramps the motion
  down (`cnc/stop`), and the driver drops the bytes that it had not
  shipped. When the ramp has ended, the driver clears from the ring what
  the ramp did not reach, and reads the position back from the kernel's
  step counters ([`position`](kernel-module.md#position)). The steps
  that never played come off the core's count, so the machine position
  counts only the steps that the kernel played. The core keeps its
  reference. `$X` clears the alarm. A position that cannot be read back
  is lost, as is one a reset dropped during the web-service homing
  session, where nothing is read back. On either, the driver tells the
  sender (one warning), drops the X and Y reference and the homing
  anchor, and holds the lens where it reads: after `$X` a Z
  jog is refused with error 15 and a program Z move raises `ALARM:2`
  ([The lens (Z)](#the-lens-z)). The machine must be re-homed before its
  coordinates are trusted. A reset that lands right after a move, a jog
  or a starve has ended, before the core takes the cycle complete, gets
  the same stop and read-back. A termination signal during motion is
  treated the same way: the latch relocked, the kernel's ramp, then the
  exit.
- **Underrun** stops motion instantly. An underrun while the kernel plays a
  stream is a fault, armed or not: alarm (`ALARM:17`), latch relocked,
  position invalidated, so the machine must be re-homed before its
  coordinates are trusted ([Homing](homing.md)). The one sanctioned retry
  is for an underrun the driver meets at a run start outside an armed
  window: the kernel ran out of the previous stream's tail just before the
  new bytes landed. The driver acknowledges it, drops the anchor, asks for
  the run again, and takes the answer to that request as the answer.
  Armed, that case fails safe too. An empty ring at the retry's answer, or
  at the stream's first run request, means that the new bytes are gone
  (they played and ran out, or the ring was cleared): a fault.
- **A stop by another writer** (the cooling engine's safing stop, a halt)
  that leaves bytes of a stream unplayed is a fault too. While the driver
  feeds a stream, a run that runs out of bytes ends in an underrun, never
  in idle, so a kernel that stops running then was stopped by someone
  else. A stop that ends the run after the stream's end, short of its last
  byte, leaves the rest of the stream in the ring, and the next run start
  finds it: the driver asks for a run only over exactly the bytes that it
  wrote for that run ([run](pulse-feeder-contract.md#run)). Either way the
  driver raises `ALARM:17`, relocks the latch, invalidates the position,
  and asks for no run over what the ring still holds.
- **After any stream fault** (an underrun, a stop by another writer, a
  kernel fault, a refused run, a write error) the alarm is critical: `$X`
  is refused (error 79) until a
  soft reset. The reset acknowledges the fault: the kernel is stopped and
  re-armed, and what the ring still held is cleared. Then `$X` unlocks, and
  the controller moves again without a restart. The position stays invalid
  until a re-home. A kernel fault (a stepper driver's fault line) is the
  exception. The kernel stays in its fault state through the reset and
  refuses a run there, so after `$X` the next move alarms again. The
  kernel leaves that state only on an `enable` write, once the fault line
  has cleared ([The kernel module](kernel-module.md#enable)).
- **The cooling verdict** has two tiers ([The cooling client](#the-cooling-client)):
  the pause tier is a feed hold, resumed when the verdict clears, with no
  press while the window is still open; the fail tier ends the job with
  `ALARM:3`.
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

Anything that invalidates position (an underrun, a stream fault, a soft
reset whose position cannot be read back, a soft reset during the
web-service homing session) drops the homing anchor deliberately, so a
stale origin cannot be reused. A controller restart drops it too: the
anchor belongs to the controller that wrote it, and a respawn starts
unreferenced. forgectrl restarts the controller after a crash or hang and
after the two fail-tier verdicts that end the controller, `FIRE` and
`CRASH` ([The cooling engine](cooling-engine.md#what-the-verdicts-do)). The other fail-tier
verdicts, `AIRFLOW` and `CRITICAL`, end the job through the driver alone:
the reset reads the position back, and the home stays.

## The cooling client

Cooling is enforced in-process but owned by the forgectrl cooling engine,
the sole owner of the thermal hardware. The driver is a client of it over
two channels ([The cooling engine](cooling-engine.md) owns both formats):

- **Job-state reports.** The driver reports its job state to the engine
  (`POST /cool/state`: mode and armed, level-triggered at about 1 Hz, each
  with the secret the supervisor handed the controller at its spawn). GRBL
  mode omits the per-job fan duties, so the engine's configured run profile
  applies. It also publishes `grbl.state` and `grbl.settings` under
  `/run/forgefirm`, written atomically on change from the protocol thread;
  forgectrl echoes them in its status ([forgectrl](forgectrl.md)).
- **The verdict.** The driver reads the engine's published verdict file
  every 500 ms and enforces the cached flags on every poll. A missing or
  stale verdict (older than 2 s) reads as fire-blocked and held. The armed
  window requires a fresh `fire_ok` verdict (over-temperature, the
  airflow floors on every fan, the lid-IR fire watch)
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
      press while the window is open. The grace counts down through the
      hold, so once it has closed the window the resume re-arms first: the
      button breathes white, and the press resumes the job
      ([The armed window](#the-armed-window)). The pause tier never writes
      the latch: a lock sets the hardware button latch, which only a press
      clears, so a lock belongs to the fail tier alone. A `SENSOR`,
      `FLAME`, or `BUMP` still standing when the window closes leaves a
      fault waiting for its Acknowledge once it clears: the verdict's
      `ack_wait`, and the name `ACK` where no other verdict stands
      ([The operator's attention](cooling-engine.md#the-operators-attention)).
      The driver does not resume its hold while a fault waits for its
      Acknowledge (`gfcool_poll`; `gfcool_ack_waits` reads the field and
      the name): the job stays held until the
      operator acknowledges it, and the clean verdict's resume then goes
      through the re-arm's press.
    - **A resume with the window closed** (the button, `~`, a sender) goes
      through the resume gate (`gflaser_resume_gate`). Under a fresh
      verdict short of the fail tier that blocks fire or carries
      `ack_wait` (`gfcool_hold_stands`), the gate refuses and the job
      stays held: no alarm, no reset, no unlock. Under a closed cooling
      gate it says
      `laser fire blocked: a cooling gate is closed - the job stays held`,
      and the same resume re-arms once the verdict has cleared. Under a
      fault that waits for its Acknowledge it says
      `laser fire blocked: a fault waits for its Acknowledge on the control panel - the job stays held`.
      A re-arm already waiting when a gate closes, or a fault comes and
      goes, ends the same way once its press is in: the latch relocks, the
      job stays held. The fail tier and a stale verdict end the job on the
      resume instead: the arm's refusal (above), `ALARM:3`, and the reset.
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
loop. The head accelerometer is the motion witness, and the kernel's count
of samples with the gated LASER_ON output active (`cnc/laser_on_sampled`)
is the live emission witness; the driver's own check of it once a second is
under [Faults](#faults). The driver does not read the head's beam detector.

## Homing handover

`$H` is a driver command that shadows the core's homing cycle. Under
`homing_mode = gfcloud` it suspends the stream engine, runs a service-driven
homing session in a child process that inherits the pulse device, and hands
the machine back. Under `homing_mode = manual` it declares the spot the
operator put the head in (against the gantry stops) as X0 Y0, or as minus
`manual_home_x`, `manual_home_y` and then jogs the head to X0 Y0. `$MD` and `$ME` release and
energize the X and Y motors for that, and while they are released the driver
holds the machine in the alarm state so that nothing moves. The mechanism is
on [Homing](homing.md).

## The controller port

Beside the Grbl socket the driver serves a second, local channel,
`/run/forgefirm/grbl.ctl`: forgectrl jogs and reads state through it without
displacing the Grbl sender, and the panel's motor release and manual home go
through it. Its only motion is `$J=`, the one motion the stream ships dark
whatever the modal laser state is. The wire format, the two operation sets,
and the sender-goes-first rule are on
[The controller port](controller-port.md).

## The lens (Z)

The driver's Z is the focal point's height above the tray: Z 0 focuses on
the bed, Z 3 focuses 3 mm above it, on the top of 3 mm material. With the
crumb tray out it is the height above the floor of the cut area instead
([below](#the-crumb-tray)). The lens is
a 2 in lens under a collimated beam, so the focal point moves 1:1 with the
lens and +Z is lens up; the travel is the lens carriage's 0.485 in
([The motion hardware](../machine/motion-hardware.md#the-lens-and-its-travel)).
Every head shares the lens screw and its travel, so the Z scale is a
constant: `$102` is 2.922 half-steps per millimeter (36 over the carriage's
12.32 mm), about 0.34 mm a half-step. What differs from head to head is the
step along the travel at which the hall sensor trips. That rising edge is
the one reference the head has, and the setup's Focus burn measures
the one number the head needs: `lens_hall_edge_z_mm`, the focal height above
the tray when the lens sits on it. A home in gfcloud mode leaves the lens on
that edge, sets Z to the number, placed on the whole step the controller
counts (so the reported position and the home position agree), and then
parks the focus at `lens_park_z_mm`, a user setting (default 3 mm; the runner
takes the whole half-steps from the edge to the nearest step at the park
height). The park and the Z envelope keep to the head's free travel as the
setup's Lens travel check found its stops (`lens_stop_below_steps`,
`lens_stop_above_steps`), or, until it has run or when the stops could not
be found, to the fallback window of ten half-steps below the edge to twelve
above; the lens is never driven onto a stop on a user's machine. The
defaults are the bench reference's, placeholders until those steps have
run. The homing
session answers the service's lens hunt as done without moving the lens;
the lens reference is the session's own, after the service goes quiet.
The lens is in the pulse path like X and Y (the driver writes
`cnc/motor_lock` 0 at its start): a job's or a jog's Z moves it, in
half-steps, at its drive current during a run and its hold current at
rest. The lens is never moved without a reference: the driver's Z soft limit
is always on, whatever `$20` says, and until Z is referenced it holds Z
where it is (a jog is refused with error 15, a program move raises the
soft-limit alarm before it starts). The hold rests on the Z homed bit,
which the core keeps only while a homing cycle names Z, so `$44`-`$46` are
pinned ([The XY scale](#the-xy-scale)): a `$44=1` from a sender answers
ok and changes nothing. X and Y join it after a home: a
successful home turns the driver's X and Y soft limits on with the bed as
the envelope (from the home corner to the far edges, `$130` by `$131` unless
the bed check measured them; [Homing](homing.md#the-far-edges)), whatever
`$20` says,
and whatever invalidates the position (an underrun, a stream fault, a soft
reset whose position cannot be read back, a soft reset during the
web-service homing session, a new homing session) turns them off again
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

### The crumb tray

The crumb tray comes out for work taller than it allows. The work then sits
on the floor of the cut area, `tray_offset_mm` below the tray (1.35 in,
34.29 mm, by default, as measured on the bench reference; held to 13 to
60 mm), and Z is the focal height above that floor. `M103 P1` sets the tray
out and `M103 P0` sets it in; any other `P`, a missing `P`, or an axis word
on the line is an error (28, 39, 31) and changes nothing. The M-code is
synchronized: the planner drains, and the switch waits for the kernel to
finish playing the move before it, the wait a package's M-code makes
([A package's M-code](extensions.md#a-packages-m-code)), before the frame
changes. The Grbl sender is told `[MSG:Tray out]` or `[MSG:Tray in]`, also
when the mode it asked for already stands.

Nothing moves: the driver moves the numbers. The Z position, the home
position, the Z envelope (a referenced one, or the one pinned where an
unreferenced lens stands), and the anchor's Z all move by the offset in
whole lens half-steps, the offset times `$102`, rounded (1.35 in is 100
half-steps, 34.22 mm), so nothing drifts by rounding. The lens reference at
a controller's start and a gfcloud home take the edge in the frame of the
mode that stands. The park after a home is counted from the edge, so the
lens parks in the same place in both modes and only the Z it reports
differs: on the bench reference with the defaults, Z 3.08 with the tray in
and Z 37.30 with it out. The offset is larger than the lens's whole travel,
so the two modes' Z ranges never overlap: a program written for the other
mode that commands Z stops at the Z soft limit instead of running out of
focus.

The mode persists across a soft reset, a controller restart, and a reboot:
the marker `/data/forgefirm/tray.out` means the tray is out. The controller
is its only writer. It writes the marker, synced, before the frame changes,
so a mode that cannot be saved does not change, and a job that asked for it
is held with a message. forgectrl reads the marker for the panel, and
refuses a change of `tray_offset_mm` while the tray is out, so the offset in
force never changes under a live frame. The panel's switch is the controller
port's `tray` op ([The controller port](controller-port.md)). The setup's
laser burns need the tray in ([Setup](../../usage/setup.md#the-laser-burns)).

Host tests: `tray_test.py` on the null-sink controller build, in the
driver's CI (the shift and its envelope, the errors, the wait for the move
before it, the port's `tray` op and its refusals, the mode across a soft
reset and a restart, an unreferenced lens, and a camera
home in both modes), and `lens_home_test` for the offset on the step grid.

## Where the driver sits in the safety design

Every software layer sits *in front of* the hardware chain: it can only
withhold FIRE, hold the lock, or starve the charge pump. None can produce
emission the hardware would not allow. The driver's layer is the armed
window, the disarm, the dose model, the coolant fire gates, the safety
door, the button, and the witnesses, described above. The kernel's layer is
on [The kernel module](kernel-module.md), forgectrl's on
[forgectrl](forgectrl.md), and the chain itself on
[The safing chain](../machine/safing-chain.md).
