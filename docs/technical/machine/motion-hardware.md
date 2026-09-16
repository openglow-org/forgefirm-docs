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
| X/Y resolution | 0.15 mm per full step; ×8 microstepping (the factory's) → 53.333 µsteps/mm, ×16 → 106.667, ×32 (the default) → 213.333 (the `xy_microsteps` setting, [Settings](../../usage/settings.md#settings-that-affect-motion)) |
| Z resolution | about 0.34 mm per half-step (36 half-steps over the carriage's travel), driven in half-steps; the driver's default `$102` is 2.832 half-steps/mm |
| Work area | 495 × 279 mm |
| Z travel | 0.485 in (12.32 mm), the lens carriage's slot; the hall sensor's edge partway up it, at a step that differs from head to head (below) |
| Max X/Y rate | 12000 mm/min (200 mm/s) |
| Max Z rate | 300 mm/min |
| Acceleration | 700 mm/s² X, 590 mm/s² Y, 50 mm/s² Z |

The laser PWM carrier (39.98 kHz, 7-bit duty) is on [The laser](laser.md).

**Where the limits come from.** They are the factory machine's own, decoded
from captured factory pulse streams rather than chosen: acceleration about
700 mm/s² on X and 590 on Y under firmware 2.6.0 (2018-era firmware used about
1000), travel moves peaking at 202 mm/s of vector speed (about 8 in/s) at the
28160 Hz travel tick, prints and hunts at a 10 kHz tick, a cut feed of
145 mm/s in the sample print, and a Z cadence of 61 to 115 ms per half-step,
about 5.7 mm/s at most.

One correction worth keeping, because the tag names invite the mistake: the
`HAxr`, `HAyr` and `HAar` values in a pulse header are **not** motion
acceleration limits. They are head-accelerometer interrupt-generator threshold
registers, which is the factory's crash detector
([Sensors](sensors.md#the-head-accelerometer)).

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
end of what the bench reference counts (its stops sit 18 half-steps
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
per-head number for Z: the setup focus card references the lens on
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
bench reference's, and the user is told. See
[Setup](../../usage/setup.md#the-sheet).

The factory's focus law, from its own Z commands, is a count of full steps
up from its zero, where its hunt parks the lens: 4 full steps down from the
hall edge. It runs about 2.8 half-steps per millimeter of material and
saturates at 30 half-steps, its idea of the usable travel.

In GRBL mode Z is the focal point's height above the tray: Z 0 focuses on
the bed, Z 3 on the top of 3 mm material, and +Z is lens up. A home leaves
the lens on the hall edge, sets Z to the edge's focal height on the step
grid (ten half-steps, Z 3.42 mm, on the bench reference), and parks
the focus at `lens_park_z_mm`, a user setting, 3 mm by default
([The grblHAL driver](../forgefirm/grblhal-driver.md#the-lens-z)). Z may go
below the tray: the tray comes out for tall work.

The lens is never moved without a reference first: in GRBL mode a job's Z
moves it within the free travel once a home, or a setup card, has
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
  1 = full steps. The factory runs at ×8; ForgeFIRM's GRBL mode runs at the
  `xy_microsteps` setting (8, 16 or 32, default 32) and derives its steps
  per millimeter, its machine tick and the kernel stop ramp from it
  ([the grblHAL driver](../forgefirm/grblhal-driver.md#the-xy-scale)).
  Cloud mode runs at the service's own ×8. The mode is written at the
  controller's start, at idle: a DRV8825 can re-index its microstep table
  by up to one full step when MODE changes with the motor energized.
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
`cnc/enable` and `cnc/disable`.

**The DRV8825 drivers on this board wedge on rail glitches.** A glitch can
leave them unserviceable: SDMA playback and the position counters run normally
while the motors produce nothing at all, or stall mid-move. The supply itself
is fine; this is a driver failure mode, not a marginal rail. `cnc/faults` does
not flag the state, and whether a given rail power-up wedges them is chance.

The kernel drives their nRESET and nSLEEP pins (`reset-gpio` gpio3 18,
`sleep-gpio` gpio3 16), but only as a pair inside every enable and disable
cycle, together with the rail. The reset pulse therefore rides along on every
recovery attempt, and it has never shortened the recovery: a logic reset alone
does not clear the state, and only the rail-off duration matters. That fits a
latched internal state nRESET does not reach. Recovery is a longer true
power-off (ForgeFIRM ladders 5, 15 and 30 seconds) and, at worst, a full
machine power cycle.

Three consequences follow, and all three shape how ForgeFIRM is built:

- **Position counters, homing anchors and a `H:1` status are never proof of
  motion.** The head accelerometer is the motion witness (below, and
  [Sensors](sensors.md)).
- **The rail stays up while the machine is on.** Every power-up is a fresh
  gamble, so the cheapest policy is not to cycle it. That is why the pulse
  device is brokered rather than opened per controller, and why there is no
  idle-rail-off policy ([forgectrl](../forgefirm/forgectrl.md)).
- **The machine proves it can move before the first job of a session**
  ([ForgeFIRM internals](../forgefirm/index.md)).

### What the motion witness reads

The liveness probe commands a small move and reads the head accelerometer
across it. On the bench reference, on an identical commanded move
([The bench reference](index.md#the-bench-reference)):

| Condition | Peak-to-peak on X or Y, raw counts |
|---|---|
| Real motion | 1800 to 2900 |
| A dead or wedged axis | 250 or less |
| An axis masked out of the pulse path | 144 to 480 |
| The rail-on and current-step jolt, with nothing moving | up to about 700 |

The noise floor for scale: 1 g reads about 16384 counts. ForgeFIRM gates a
controller start at 800 counts, clears any leftover axis mask before its own
move so a mask cannot read as a wedge, and settles 300 ms after the
run-current step before it samples, because that step jolts the head.

Raw accelerometer reads through sysfs take about 150 ms each, which is enough
for a yes-or-no verdict over a multi-second window and useless for a waveform.
Reading the part straight over its bus gives about 530 to 800 samples a
second, which is what the crash watch and the setup lens finder use
(see [Sensors](sensors.md)).

**A contact strike, for any future contact sensing.** From the retired
accelerometer-homing work: creeping toward a rail reads a baseline of about
0.5 to 2 thousand counts, and contact jumps to 29 to 42 thousand within about
4 ms, 20 to 40 times over. But **a slow approach is near-silent**: belt
compliance turns low-speed skipping into sub-threshold grinding. Any
contact-sensing scheme has to strike fast.

## What the microstep mode changes, and what it does not

X and Y run at 8, 16 or 32 microsteps from one setting, and the machine holds
its 200 mm/s top speed at all three because the machine tick scales with the
mode ([the grblHAL driver](../forgefirm/grblhal-driver.md#the-xy-scale)).
Measured on the bench reference, dry and under the laser: position returns
exactly at every mode, with no underruns and no clamped events, and the tube
current at cruise reads alike across the three.

What does change is **vibration**, and the finer mode is the quieter one. With
every fan, the coolant pump and the TEC commanded off so the machine is
silent, running a pattern at 12000 mm/min and reading the head accelerometer
over its bus:

| Cruise RMS, raw counts | x8 | x16 | x32 |
|---|---|---|---|
| A 9 inch circle, X | 2289 | 1939 | 1638 |
| A 9 inch circle, Y | 1343 | 1192 | 1181 |
| Overall, X | 1742 | 1500 | 1369 |
| Overall, Y | 1209 | 1110 | 1118 |

The rest floor is about 50 counts with everything off, and about 200 with the
coolant pump running: the pump is in the reading. The single-axis legs sit
within a few percent of each other at every mode; the gain is on the legs
where both axes move, and most of all on a circle.

### An arc's tone is the planner's, not the motor's

grblHAL traces an arc as chords whose sagitta is `$12` (0.002 mm by default),
and every chord is a planner block. A 9 inch circle at 12000 mm/min is
therefore 531 chords of 1.35 mm and 148 block boundaries a second: an audible
tone that **no microstep mode changes**, because the planner's geometry makes
it and the motor's step grid cannot.

Driving `$12` finer moves the tone up (148, 209, 296 Hz) and does not lower
the vibration. Above about 300 chords a second the feed sags mid-arc and the
circle takes longer, with the processor flat at about a third of the core and
no underrun: the planner plans to a stop at the end of what it holds, and 100
blocks of 0.3 mm is 30 mm against a 29 mm stopping distance from 200 mm/s. A
deeper planner buffer does not move that; the chord rate the protocol loop can
feed is the ceiling. On a 9 inch radius the finest `$12` that holds top speed
is 0.0005 mm; at a lower feed a finer value holds in proportion, and a smaller
radius reaches the same chord rate sooner.

`$398`, the planner buffer depth, runs over its whole 30 to 1000 range.
