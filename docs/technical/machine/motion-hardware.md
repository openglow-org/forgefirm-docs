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
| Z resolution | about 0.34 mm per half-step (36 half-steps over the carriage's travel), driven in half-steps; the driver's default `$102` is 2.832 half-steps/mm |
| Work area | 495 × 279 mm |
| Z travel | 0.485 in (12.32 mm), the lens carriage's slot; the hall sensor's edge 13 half-steps above the bottom stop |
| Max X/Y rate | 12000 mm/min (200 mm/s) |
| Max Z rate | 300 mm/min |
| Acceleration | 700 mm/s² X, 590 mm/s² Y, 50 mm/s² Z |

The laser PWM carrier (39.98 kHz, 7-bit duty) is on [The laser](laser.md).

Origin is the **back-left** corner, and the workspace is all-positive from
there. **+Y moves the gantry toward the front of the machine.** Z counts
positive upward, away from the bed.

Z is never driven blind: the lens carriage is referenced against a hall sensor
low in its travel, and moves are supervised against it. The sensor and the
unit-to-unit variation of its trip point are on [Sensors](sensors.md); the
lens, its travel, and the focus are below.

## The lens and its travel

The head carries a 2 in focal length lens (Glowforge's own figure) under a
collimated beam, so the focal point moves with the lens, 1:1: a millimeter
of lens is a millimeter of focus height. The lens sits in a carriage that
travels 0.485 in (12.32 mm) between two mechanical stops, driven by a small
stepper through a lead screw. Every head shares the screw, so a half-step
is the same height everywhere, about 0.34 mm: ForgeFIRM takes the travel as
36 half-steps (`$102` is 2.922 per millimeter), a half-step of leeway at each
end of what the bench reference machine counts (its stops sit 18 half-steps
below its hall edge and 20 above, 38 in all).

The hall sensor is the only position reference. It reads home from an edge
partway up the travel to the top stop. The rising edge, the first position
that reads home going up, found by stepping down out of the zone and back
up, is what everything references; it is exact and repeatable, where a
count that ends in a stall against a stop is not (the rotor slips whole
steps against the stop and re-engages up to three full steps out of phase,
so such a count reads low by an even number at random). Going down, the
sensor lets go four to six half-steps under the edge; the lens rings a
little on every step, which is the jitter in that band. Where along the
travel the edge sits differs from head to head, and that is the one
per-head number for Z: the commissioning focus card references the lens on
the edge, burns a ladder over the head's free travel, and the user's pick
on the sheet's thickness gives the focal height when the lens is on the
edge (`lens_hall_edge_z_mm`). The free travel itself is found by the head
accelerometer: a free half-step rings, on every second step strongly, and
at a stop the ring dies two to four steps before the rotor would slip, so
the card steps toward each stop one half-step at a time, calls contact on
the first quiet strong step, backs off two, and proves by the count back to
the edge that nothing slipped (`lens_stop_below_steps`,
`lens_stop_above_steps`; 14 below and 20 above on the bench reference
machine). Nothing in ForgeFIRM drives the lens onto a stop on a user's
machine; when the stops cannot be found on a head, every move keeps a
fallback window, ten half-steps below the edge to twelve above, that clears
both stops on any head whose edge sits within six half-steps of the bench
reference machine's, and the user is told. See
[Commissioning](../../usage/commissioning.md#the-sheet).

The factory's focus law, from its own Z commands, is a count of full steps
up from its zero, where its hunt parks the lens: 4 full steps down from the
hall edge. It runs about 2.8 half-steps per millimeter of material and
saturates at 30 half-steps, its idea of the usable travel.

In GRBL mode Z is the focal point's height above the tray: Z 0 focuses on
the bed, Z 3 on the top of 3 mm material, and +Z is lens up. A home leaves
the lens on the hall edge, sets Z to the edge's focal height on the step
grid (ten half-steps, Z 3.42 mm, on the bench reference machine), and parks
the focus at `lens_park_z_mm`, a user setting, 3 mm by default
([The grblHAL driver](../forgefirm/grblhal-driver.md#the-lens-z)). Z may go
below the tray: the tray comes out for tall work.

The lens is never moved without a reference first: in GRBL mode a job's Z
moves it within the free travel once a home, or a commissioning card, has
referenced it, and the driver refuses Z otherwise.

The lens rises only at the driver's drive current (`z_current` 0). At the
hold current (1) the motor lifts the lens two steps into the service's ramp
(630, 164 and 115 ms, then 77 ms per step) and stalls; lowering works at
either current (measured on the bench head with single steps at the ramp's
timing). Every path that moves the lens sets the drive current first and the
hold current after: the homing sweeps, the focus card, and the cloud client's
motions.

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
