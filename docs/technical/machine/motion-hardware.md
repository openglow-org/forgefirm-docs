---
title: Motion hardware
---

# Motion hardware

This page gives the machine's geometry, its speed and acceleration limits, the
axis conventions, and the stepper drive facts. How the grblHAL planner uses
these limits is on [the grblHAL driver](../forgefirm/grblhal-driver.md); how
the step stream itself works is on [The step engine](step-engine.md).

## Geometry, speeds and limits

| Property | Value |
|---|---|
| X/Y resolution | 0.15 mm per full step, ×8 microstepping → 53.333 µsteps/mm |
| Z resolution | 0.70612 mm per full step, driven in half-steps (0.3531 mm) → 2.832 half-steps/mm |
| Work area | 495 × 279 mm |
| Z travel | about 10.6 mm (0.417"), hall-referenced at the top |
| Max X/Y rate | 12000 mm/min (200 mm/s) |
| Max Z rate | 300 mm/min |
| Acceleration | 700 mm/s² X, 590 mm/s² Y, 50 mm/s² Z |

The laser PWM carrier (39.98 kHz, 7-bit duty) is on [The laser](laser.md).

Origin is the **back-left** corner, and the workspace is all-positive from
there. **+Y moves the gantry toward the front of the machine.** Z counts
positive upward, away from the bed.

Z is never driven blind: the lens carriage is referenced against a hall sensor
at the top of travel, and moves are supervised against it. The sensor and the
unit-to-unit variation of its trip point are on [Sensors](sensors.md).

The machine has **no limit or home switches** as it ships. What that means in
practice, how each mode establishes an origin and how the machine behaves
without one, is on [Homing](../../usage/homing.md) (the operator view) and
[Homing internals](../forgefirm/homing.md) (the mechanism).

The Grbl `$` settings (steps/mm, rates, accelerations) default to the values
above, which are the factory machine's own measured values.

## Stepper drives

**X and Y.** The X axis and the two Y motors are driven from the pulse stream
(see [The step engine](step-engine.md)). The two Y motors (Y1, Y2) are driven
complementary from one Y step and direction pair. The drivers expose:

- Microstepping mode per axis (`x_mode`, `y_mode`): 1, 2, 4, 8, 16 or 32.
  1 = full steps. The machine runs at ×8.
- Current decay mode per axis (`x_decay`, `y_decay`): 0 = slow (fast stop,
  slow response), 1 = mixed (decay pin high impedance), 2 = fast (fast
  response, slow stop).
- Drive current set through the PIC: `x_step_current` and `y_step_current`
  are 10-bit DAC values (0 to 1023, 0 = minimum). The two axes' DAC scales
  differ by design; the factory runs X at 135 (33 at hold) and Y at 22 (5 at
  hold), and ForgeFIRM writes the same.
- Fault lines from the drivers: bit 0 = X, bit 1 = Y1, bit 2 = Y2
  (`faults`); each can be masked (`ignored_faults`).
- A per-motor lock (`motor_lock`, bits X, Y1, Y2, Z) that holds an axis still
  while a program runs.

**Z.** The Z axis moves the lens carriage in the print head. Its driver
enable, current (high or low) and microstep mode (full or half-step) are head
controls (`z_enable`, `z_current`, `z_mode`). Z also has a direct single-step
control (`z_step`: 0 = toward the bed, 1 = away from it) that pulses the GPIO
outside the pulse stream.

The attribute reference for all of these is on
[the kernel module](../forgefirm/kernel-module.md).

## The 40 V motor rail

The stepper drivers run from a 40 V motor rail, switched by the kernel's
`cnc/enable` and `cnc/disable`. The drivers on this board can latch into an
unserviceable state on a rail glitch: the position counters keep counting
while the motors produce nothing. Two consequences follow for how ForgeFIRM
treats the rail (it stays up while the machine is on, and the machine proves it
can move before the first job of a session); both are on
[ForgeFIRM internals](../forgefirm/index.md).

Position counters are not proof of motion. The head accelerometer is the
motion witness (see [Sensors](sensors.md)).
