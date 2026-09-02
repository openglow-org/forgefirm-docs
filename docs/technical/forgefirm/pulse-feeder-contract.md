---
title: Pulse feeder contract
---

# Pulse feeder contract

`/dev/glowforge` is the pulse-stream ring device of `glowforge.ko`. This
page is the contract a feeder must obey: the device semantics, the
run-control attributes, live appends and backpressure, end-of-data and
underrun, the dead man's switch, and backtrack. The byte layout and the
hardware ring (SDMA + EPIT into a GPIO register) are on
[Step engine](../machine/step-engine.md). The other attributes of the module
are on [Kernel module](kernel-module.md). This page is the authoritative
text of the feeder contract.

Everything here is enforced by the SDMA script and the driver. It is not
negotiable at run time.

## The ring, and two ways to fill it

Pulse bytes go into a ring buffer in reserved memory, 32 MiB by default, the
same size the factory firmware uses. There are two ways to use it, and the
mode you run decides which:

- **Live streaming (GRBL mode).** The controller keeps only a small window of
  the job in the ring (a fraction of a second) and refills it continuously
  while the job plays. A write that would overflow is refused, and the
  feeder backs off; that is normal flow control, not an error. If the feeder
  falls behind far enough to empty the ring, the machine enters the
  **underrun** state: motion stops instantly, and position is no longer
  trusted.
- **Preloading (cloud mode).** The job is written into the ring before it
  starts, as much of it as fits: roughly 1 MiB per 100 seconds at the
  cloud's 10 kHz tick, so about 56 minutes at 32 MiB. A job longer than the
  ring runs anyway; the client tops the ring up as it drains. The ring size
  caps how much of a job is buffered at once, not how long a job may be.

The GRBL-side feeder is on [grblHAL driver](grblhal-driver.md); the cloud
preloader is on [Cloud mode](cloud-mode.md).

## Ring size and the reserved pool

The ring size is the `ring_mb` module parameter: the size in MiB, a power of
two from 1 to 1024, default 32. An invalid value is logged and the default
is used. The ring must fit the cnc reserved-memory pool (`cnc-pulsebuf` in
the device tree), a size-aligned no-map pool of 32 MiB that the device tree
reserves for it; the pool is described on
[Image and BSP](image-and-bsp.md#the-reserved-motion-memory-pool). For
longer cloud-mode jobs, raise both the pool and `ring_mb`.

A writer must leave 32 KiB of ring unwritten behind the play head. The gap
is retained history: 32 KiB is 3.2 s at the 10 kHz print tick, and it
survives any fill, live-fed or preloaded, so a pause always has at least
this much to back into.

## The device: /dev/glowforge

Write/Seek/Lock, Binary, ring (size = the `ring_mb` module parameter,
default 32 MiB; power of two, must fit the cnc reserved-memory pool).

Interface to the pulse-stream ring buffer. **Exclusive-open:** a second open
fails with EBUSY, so one process holds one fd and routes every write and
seek through it.

| Seek to | Effect |
|---|---|
| 0 | Clear program data, byte counters, and position counters |
| 1 | Clear program data and byte counters |
| 2 | Clear position counters |

Locking the file (`flock LOCK_EX`) arms the **dead man's switch**: if the fd
is closed while locked and a program is running, the device performs an
emergency stop. The switch is per-holder state: every fresh open starts with
it disarmed, shared locks (`LOCK_SH`) are rejected with EINVAL, and
`LOCK_UN` disarms.

Every close of the device locks the laser latch
([Kernel module](kernel-module.md#safety-functions)). The open itself has no
rail side effect; the 40 V rail moves only on `cnc/enable` and
`cnc/disable` writes.

Under ForgeFIRM, forgectrl opens the device once and holds it for its
lifetime, and the controllers inherit the fd (`GF_PULSE_FD`). A controller
crash is therefore not a final close, and the supervisor is the dead-man for
its writers. That arrangement is on
[forgectrl](forgectrl.md#pulse-device-ownership).

## Run control attributes

These attributes live under `/sys/glowforge/cnc`.

### run

Write, ASCII, 1

Writing "1" switches the device to the "run" state from "idle" and starts
executing the loaded program. Every run started this way resets the laser
duty to about 100 % (see [Power bytes](#power-bytes)).

### stop

Write, ASCII, 1

Writing "1" performs a controlled stop of a running program: the step
frequency ramps down to the minimum at `ramp_rate`, motion comes to a
smooth stop, and the device switches to the "idle" state. Because the
deceleration is controlled, no steps are lost, so the reported position
stays accurate. Once stopped, the laser-enable line is released (laser off)
and the step lines are driven low; the stepper motors remain powered. For
an immediate stop with no deceleration (at the cost of possibly losing
steps), see `halt`.

In the "underrun" state, writing "1" acknowledges the underrun and returns
the device to "idle" (position should be re-homed before it is trusted).
Otherwise it has no effect unless the device is in the "running" state.

### halt

Write, ASCII, 1

Writing "1" performs an immediate stop of a running program: pulse-data
processing ends at once with no deceleration, and the device switches to
the "idle" state. As with `stop`, the laser-enable line is released (laser
off) and the step lines are driven low, while the stepper motors remain
powered. Unlike `stop`, there is no controlled ramp-down, so if the machine
is moving at speed the motors may lose steps (overshoot) and the reported
position may no longer be accurate. Use `halt` for an immediate or
emergency stop where stopping promptly matters more than preserving
position; use `stop` for a clean, position-preserving stop. Has no effect
unless the device is in the "running" state.

### resume

Write, ASCII, -268435455 to 268435455

- **Negative values:** laser disabled. Accelerate backward, run the number
  of specified steps, then decelerate and stop. Refused (EPERM) if the
  request is longer than `max_backtrack`: the run is never quietly
  shortened, because a caller sizes the laser-on lead of its resume to the
  distance it asked for, and a silent shortfall would put the beam back on
  ahead of the pause point. A live feed is backtrackable on the same terms
  as a preloaded program: what bounds the walk is the ring's retained
  history, not how the ring is filled.
- **Positive values:** accelerate forward, run the number of requested
  steps, re-enable the laser, and continue the program normally.
- **Zero:** accelerate forward, continue the program without re-enabling
  the laser.

The step count is a 28-bit waypoint counter; magnitudes at or above 2^28^
are rejected with EINVAL rather than silently truncated.

### max_backtrack

Read, ASCII, steps

The longest backward run (see `resume`) the ring can still play: bytes it
has already played, that belong to this program, that are not overwritten,
less the steps the controlled deceleration plays out past the
waypoint. A pause reads this and sizes both its backtrack and the laser-on
lead of the resume that follows from it, so a pause early in a program (or
on a ring a live feed has just refilled) shortens the retrace instead of
failing it.

The floor is the retained gap: a writer must leave 32 KiB of ring unwritten
behind the play head, so 32 KiB of history (3.2 s at the 10 kHz print tick)
survives any fill, live-fed or preloaded. Each read performs SDMA channel-0
transactions.

### streaming

Read/Write, ASCII, 0-1

Declares how end-of-data is interpreted. A live feeder (one that streams
pulse data while the program runs, rather than preloading it) writes "1"
before starting a run: running out of data mid-run then transitions the
device to the "underrun" state instead of "idle", making buffer starvation
distinguishable from normal completion. Write "0" after enqueueing the
final bytes of a job so the terminal end-of-data counts as completion.
Default is 0 (factory/preload behavior: any end-of-data is a normal stop).

At end-of-data the SDMA script itself forces the laser and step lines low
before signaling the host, regardless of this setting.

### underruns

Read, ASCII, count

Number of streaming underruns (see `streaming`) since module load.

### free

Read, ASCII, bytes

Free space in the pulse ring (already net of the reserved 32 KiB backtrack
gap): the largest write that succeeds at the moment of the read. This is a diagnostic,
advisory readback, not the backpressure primitive: a feeder paces by wall
clock and takes the write's -ENOMEM return as the back-off signal (see
[Pacing and backpressure](#pacing-and-backpressure)). Each read performs
SDMA channel-0 transactions. Do not poll it for pacing.

## The feeder contract

Everything a streaming feeder (for example the grblHAL step backend) must
obey.

### Byte layout

One byte per EPIT tick. If bit 7 is clear, the byte is a step/laser
command; if bit 7 is set, the low 7 bits are a laser power level. The bit
table and the X, Y, and Z direction conventions are on
[Step engine](../machine/step-engine.md).

### Fixed byte density

There is no per-byte timing. The engine consumes exactly one byte per timer
tick at `step_freq`. All velocity is expressed as step **density** across
bytes (software DDS/Bresenham resampling of variable-rate segments into a
fixed-tick stream). `step_freq` is immutable while running (-EBUSY); a
mid-run speed change is density, not clock.

### Effective rate ceiling

The script's per-byte execution time is about 6 µs: above about 165 kHz the
EPIT outruns the script and the effective consumption rate saturates
(measured on hardware: 164.6 kHz sustained at `step_freq=200000`). Plan
machine ticks at or below 100 kHz; 20 to 50 kHz covers realistic kinematics
with a large margin.

### Power bytes

A power byte sets the laser PWM duty (7-bit, written raw into PWMSAR; full
range at the ~40 kHz carrier). Two rules:

- **Consecutive power bytes are dropped.** Only the first of a run of power
  bytes applies; the rest are consumed without effect (one power change per
  non-power byte). Interleave a step byte between power changes.
- **Every run started without preserve_power (the plain `run` attribute)
  resets the duty to about 100 %.** A stream must send its first power byte
  before its first laser-on byte, or the first pulses fire at full power.

### Termination

End every stream with laser-off bytes (bit 4 clear). The script forces the
laser and step lines low at end-of-data as a hardware backstop, but the
stream must not rely on it: it is the underrun safety net.

### Streaming protocol

Write `streaming=1` before a live-fed run. End-of-data mid-run then lands in
the `underrun` state (position no longer trusted; re-home) instead of
"idle", and new runs are refused until acknowledged via `stop`. Write
`streaming=0` after enqueueing the final bytes of a job so its terminal
end-of-data counts as completion.

### Pacing and backpressure

Writes either commit fully or fail -ENOMEM (no partials; 32 KiB of ring is
reserved as a backtrack gap). Do not poll `free` for pacing: every read
costs two channel-0 SDMA transactions. Pace by wall clock
(`enqueued_target = elapsed * step_freq + queue_depth`) and treat -ENOMEM as
"back off". Keep the queue depth **bounded** (50 to 200 ms) so feed and
power overrides take effect promptly. The ring (default 32 MiB, the
`ring_mb` module parameter) holds many minutes of stream, so depth is a
latency choice, not a capacity one.

A whole-file preloader (cloud mode) buffers as much of the job as the ring
holds, about 1 MiB per 100 s of 10 kHz stream, so about 56 min at the
32 MiB default, and appends the rest as the ring drains.

Measured reference (i.MX6 Solo, `CONFIG_PREEMPT`, `SCHED_FIFO` feeder, full
CPU and I/O load): a 150 ms depth at 100 kHz ran 2 minutes with 0.2 ms worst
write latency and zero underruns.

### Do not write while running backward

A write during a backtrack would clobber the backtrack dead-stop. Such
writes are rejected with -EBUSY.

### Pausing a live feed

The 32 KiB the writer keeps clear is retained history, so a live-fed program
can back up and resume exactly like a preloaded one. Read `max_backtrack`
for the distance available, ask for no more than that (a longer request is
refused, not shortened), and lead the laser back on over the ground the
backward run retraced. Topping the ring up between the read and the
`resume` write can shorten the answer, so treat an -EPERM there as "read it
again or hold where you are", not as a fault.

### Recommended feeder shape

Hold the fd open and flock'd for the whole job (dead-man armed). Prefill
one queue depth. Write `run`. Top up on a 10 to 20 ms cadence by wall
clock. On `underrun`, raise a controller alarm, re-home, acknowledge via
`stop`, seek-clear, and regenerate. For feed hold or jog cancel use `stop`
(controlled deceleration) or `halt` plus seek-clear and regenerate.

## Progress counters under a live feed

The `position` attribute carries two byte counters: bytes processed (a
32-bit SDMA counter that wraps modulo 4 GiB) and program size (a 64-bit
host tally that saturates at 4 GiB). Under a long live stream they diverge
past 4 GiB. A controller that compares them for progress must track the
wrap itself, or use its own count of bytes written. The layout is on
[Kernel module](kernel-module.md#position).

## Fast beam stop on a feeder stall

The fast beam-stop path on a feeder stall is the ring-drain chain: the ring
runs dry, the SDMA script forces the FIRE and step lines low in the same
tick, the driver leaves the running state, the charge pump self-terminates
on its next 200 ms tick, and the HV watchdog disarms the chain. Cloud mode
preloads a job that fits the ring, so that ring does not drain on a feeder
stall (a job longer than the ring is live-fed past it, and can); that
residual is covered by the cooling engine's hung-controller dead-man
([forgectrl](forgectrl.md#watchdog-scope)).
