---
title: The step engine
---

# The step engine

This page describes the hardware step engine on the control board: the EPIT
timer and SDMA engine that play one stream of bytes out to the stepper and
laser lines, the byte layout, the ring buffer, the position counters, and the
stop and resume mechanisms the engine offers. How ForgeFIRM feeds the ring
(append, free, end of data, underrun, dead man, backtrack) is the
[pulse feeder contract](../forgefirm/pulse-feeder-contract.md).

Everything the machine does physically, every step of the gantry, every lens
move, every laser pulse, comes out of **one stream of bytes** played by hardware
at a fixed rate.

## Timer and DMA, no software in between

The control board does not decide, moment by moment, when to move a motor.
Instead a hardware timer (EPIT) fires at a fixed **machine tick**, and a DMA
engine (SDMA) hands the next byte of a prepared stream straight to the GPIO
register that drives the stepper and laser lines. No software runs between the
timer and the pins.

That is what makes motion smooth: step timing cannot be disturbed by a busy
CPU, a camera stream, a network client, or a garbage collector. The worst a
loaded system can do is fail to supply bytes fast enough, and that case is
detected and treated as a fault rather than as silent damage.

SDMA and EPIT run without the CPU. Once a program is started, the engine keeps
playing the ring even if the kernel stops; the kernel module's panic handler
exists for exactly that reason (see
[the kernel module](../forgefirm/kernel-module.md)).

## One byte per tick

Each byte covers exactly one tick. If the top bit is clear, the byte commands
steps and fire; if it is set, the byte sets laser power.

| Bit | Meaning |
|---|---|
| 0 | X step |
| 1 | X direction (set = −X) |
| 2 | Y step |
| 3 | Y direction (set = +Y; the two Y motors are driven complementary) |
| 4 | **Laser fire during this tick** |
| 5 | Z step |
| 6 | Z direction (set = lens up, away from the bed = +Z) |
| 7 | 0 = step byte · 1 = power byte (low 7 bits are the power level) |

The Z convention is hardware-verified: bit 6 set moves the lens up, away from
the bed, the position counter counts it as +Z, and the kernel's single-step
control follows the same sense. A Z step in the stream reaches the motor only
while bit 3 of `cnc/motor_lock` is clear; the factory's idle posture sets it,
and both ForgeFIRM controllers set it at their start and lift it for a motion
that moves the lens ([The kernel module](../forgefirm/kernel-module.md#motor_lock)).

**Speed is density, not clock.** The tick rate never changes inside a job.
Going faster means setting a step bit in more of the bytes; going slower means
spacing them out. A move is planned in the usual way (acceleration, cruise,
deceleration) and then resampled onto this fixed grid.

Two consequences worth knowing:

- **Resolution is bounded by the tick rate.** At the GRBL machine tick of
  28160 Hz for ×8 microstepping, one axis can take at most 28160 steps per
  second, about 528 mm/s, comfortably above the machine's 200 mm/s top
  speed. The GRBL tick scales with the microstep mode (56320 Hz at ×16,
  112640 Hz at ×32), so the ceiling in millimeters per second is the same
  at every mode.
- **There is a hardware ceiling.** The playback script needs about 6 µs per
  byte, so beyond roughly 165 kHz the timer outruns it and the effective
  consumption rate saturates (measured on hardware: 164.6 kHz sustained at a
  step frequency of 200000). Ticks are chosen far below that: plan machine
  ticks at or below 100 kHz; 20 to 50 kHz covers realistic kinematics with a
  large margin.

### The machine tick

The step frequency (`step_freq`) ranges from 1000 to 200000 Hz, default 10000,
and cannot change while a program runs. The factory firmware uses 10 kHz for
prints and hunts and 28160 Hz for travel moves; GRBL mode runs at 28160 Hz
times the microstep mode over 8 ([the grblHAL driver](../forgefirm/grblhal-driver.md#the-xy-scale)),
and cloud mode takes the tick from each job's header. The stop ramp
(`ramp_rate`, Hz per second of step frequency) follows the tick, so a
controlled stop covers the same distance at every tick.

## The ring, and two ways to fill it

Pulse bytes go into a ring buffer in reserved memory. Its size is the
`ring_mb` module parameter: a power of two, default 32 MiB (the same size the
factory firmware uses), and it must fit the reserved-memory pool the device
tree provides (see [Image and BSP](../forgefirm/image-and-bsp.md)). There are
two ways to use the ring, and the mode you run decides which:

- **Live streaming (GRBL mode).** The controller keeps only a small window of
  the job in the ring (a fraction of a second) and refills it continuously
  while the job plays. A write that would overflow is refused, and the feeder
  backs off; that is normal flow control, not an error. If the feeder ever
  falls behind far enough to empty the ring, the machine enters an
  **underrun** state: motion stops instantly, and position is no longer
  trusted.
- **Preloading (cloud mode).** The job is written into the ring before it
  starts, and a job that fits the ring cannot starve. A longer job is topped
  up as the ring drains, live-fed like GRBL mode, and can underrun the same
  way. What fits is capped by the ring size: roughly 1 MiB per 100 seconds at the cloud's 10 kHz tick, so
  about 56 minutes at 32 MiB. How the cloud client handles a job longer than
  the ring is on [Cloud mode](../forgefirm/cloud-mode.md).

A writer leaves 32 KiB of ring unwritten behind the play head. That gap is
retained history (3.2 s at the 10 kHz print tick), and it is what a pause can
back into (below).

## Position counters

The engine keeps three axis counters (X, Y, Z, in steps) and two byte counters
(program bytes processed, and program size). The processed count is a 32-bit
SDMA counter and wraps modulo 4 GiB under a long live stream; the size is a
64-bit host tally that saturates at 4 GiB. The kernel exposes all of them in
one 32-byte little-endian record (see
[the kernel module](../forgefirm/kernel-module.md)).

The counters count bytes played, not motion. The step drives are open loop, so
position counters advancing are never proof that the machine moved; the head
accelerometer is the motion witness (see [Sensors](sensors.md)).

## Stopping and resuming at the hardware level

The pulse engine offers three ways out of a running program, and both
controller modes are built on them:

- **Controlled stop.** The tick rate ramps down at a set rate (`ramp_rate`,
  10000 to 500000 Hz/s, default 125000; constant, independent of the target
  speed) until motion halts. No steps are lost, so position stays accurate.
  This is what a feed hold, a jog cancel, a lid-open cancel and a soft reset
  all use.
- **Halt.** An immediate stop with no ramp. Steps can be lost; used only for
  emergencies.
- **Resume with a waypoint.** From a controlled stop the program can be
  resumed a chosen number of steps backward (laser forced off) or forward
  (laser re-enabled after the requested steps). This is how the factory's
  pause-and-resume works, and cloud mode uses it. The waypoint counter is
  28 bits. What bounds the backward walk is the ring's retained history
  (`max_backtrack`), not how the ring was filled: a live-fed program can back
  up on the same terms as a preloaded one, and a request longer than the
  history is refused rather than shortened.

Once stopped, the laser-enable line is released (laser off) and the step lines
are driven low; the stepper motors stay powered.

Whenever a stream ends, normally or by starvation, the playback script drives
the fire and step lines low as a hardware backstop, before it signals the host.
The stream must not rely on it: it is the underrun safety net, not the
mechanism.

## See also

- [The laser](laser.md): the power byte and the fire bit.
- [Motion hardware](motion-hardware.md): steps per millimeter, travel, speeds.
- [The pulse feeder contract](../forgefirm/pulse-feeder-contract.md): what a
  feeder must obey.
- [The grblHAL driver](../forgefirm/grblhal-driver.md): how G-code becomes
  pulse bytes.
