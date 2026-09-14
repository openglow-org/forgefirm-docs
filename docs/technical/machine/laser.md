---
title: The laser
---

# The laser

This page describes the laser drive as the hardware sees it: the power byte and
the PWM it sets, the fire bit, the rules the hardware imposes on a stream, and
what actually lets the beam out. How the grblHAL driver maps `S` values onto
power bytes and pulse density, and how the operator-armed window works, is on
[the grblHAL driver](../forgefirm/grblhal-driver.md); the operator's view is
on [GRBL mode](../../usage/grbl-mode.md).

## Laser drive is part of the motion stream

The laser is not a separate subsystem that gets told "on" and "off" while
motion happens elsewhere. **Power and fire ride the same bytes as the steps**,
on the same grid (see [The step engine](step-engine.md)):

- A **power byte** (top bit set) sets the PWM duty of the laser drive: 7 bits
  written raw into the hardware PWM (PWMSAR) against a 127-count period, at a
  carrier of 39.98 kHz. 127 is full power.
- The **fire bit** (bit 4) requests emission for that one tick, and only that
  tick.

Because both travel with the steps, power and position cannot drift apart. A
power change lands at exactly the point along the path where it was planned,
regardless of what the rest of the system is doing.

| Signal | Where | Role |
|---|---|---|
| Laser power | PWM2 on J1_13 | Sets the tube current setpoint. Not part of the safing chain; not gated. |
| FIRE (LASER_ENABLE) | GPIO2_30, driven by the SDMA script from bit 4 of each byte | The per-tick emission request. High impedance whenever the latch is locked or no run is in flight. |
| HV_ENABLE | J1_16 | Lets the high-voltage supply run. Lid closed and charge pump alive. |
| LASER_ON | J1_12 | The gated fire request: FIRE and both latches clear. |
| LASER_PGOOD | J1_14 | The supply's power-good: driven high while the supply reports its outputs within spec. Static across HV enable and emission; a supply-fault witness. |

## Three rules the hardware imposes

Both controllers obey them:

1. **Power before fire.** Starting a program resets the duty to about 100 %,
   so a stream must set power before its first fire bit. Otherwise the first
   pulses would fire at full power.
2. **No two power bytes in a row.** The playback script applies the first of a
   run of power bytes and discards the rest, so power changes are spaced by at
   least one step byte.
3. **End dark.** Every stream ends with fire clear; the end-of-data backstop is
   the safety net, not the mechanism.

Also worth knowing: **the duty setting persists after a program ends.** The
laser-off guarantee rests entirely on the fire bit and the hardware chain,
never on power being zero.

The tube itself fires a strike transient at every beam-on. A rendering that
switches FIRE on and off at a duty therefore burns a spot at each beam-on,
which is why ForgeFIRM's dose model fires every pulse at full power and
expresses the commanded level as pulse density instead (see
[the grblHAL driver](../forgefirm/grblhal-driver.md)). What the tube does
between "no light" and "full light" is below.

## What the tube does

The numbers in this section are the bench reference's
([The bench reference](index.md#the-bench-reference)). A tube is a consumable
with a wide tolerance, and it ages, so treat the shape as general and the
values as one machine's. The setup sheet measures the two that matter
on yours ([Setup](../../usage/setup.md#the-sheet)).

### Two thresholds, far apart

Driving the tube at a steady duty and cutting a ladder of lines on scrap
(constant power, one line per rung) shows two separate thresholds:

| | Duty | What happens |
|---|---|---|
| **The discharge strikes** | between 2 % and 3 % (PWMSAR 3) | 2 % draws no measurable supply current and leaves nothing at all. 3 % draws current. |
| **The tube lases usefully** | 16 % (PWMSAR 20) | The lowest duty that leaves a continuous mark. |

Between them, from 3 % to 14 %, is a **dead band**: current flows and climbs,
and each line shows only a spot at its start, the strike transient, with a
dark line after it. The tube lights, drops below lasing gain, and coasts dark
for the rest of the line.

That dead band is the whole reason the dose model is pulse density rather
than duty. Under a duty model the bottom sixth of the control range is
physically dead, so a low power setting is either nothing or a row of spots.
Under a density model every pulse is full-power, so no commanded level can
land in the band.

### The response to density is convex

Firing full-power pulses at a density and measuring the light out (the head
beam detector, the tube current, and the mark on the material) gives a curve
that is far from a straight line:

| Pulse density | Light delivered, as a fraction of continuous fire |
|---|---|
| 80 % | about a half |
| 60 % | about a third |
| 45 % | about a fifth |
| 30 % | about a fourteenth |

This is why an `S` value is not a density. The driver maps the commanded
light fraction through the inverse of this curve onto the density that
delivers it, so half power means half the light
([the grblHAL driver](../forgefirm/grblhal-driver.md)). The same physics is
behind the factory's own mapping of its 1-to-100 scale onto densities of
18.9 to 79.5 percent ([Factory firmware](factory-firmware.md#how-the-factory-sets-power)).

### The low end is bounded by the gap between pulses, not by the pulse

Below the shortest pulse the model will emit, it skips periods and carries
the debt, so the interval between pulse starts is

```
interval = minimum pulse ticks x tick period / density
```

The base period cancels out of that expression, which is why base periods of
10, 20 and 40 ticks measured identically. What decides whether the tube
lights is the **gap**: the discharge is re-struck at every pulse, and past
roughly 2 to 4 ms it has decayed too far to catch.

Measured on the bench reference: the tube **strikes down to about 5 percent
density at a 2.26 ms interval** (a 3-tick, 106 µs minimum pulse) and **fails
to strike at 4.51 ms** (a 6-tick, 213 µs minimum). Lengthening the pulse at a
fixed density lengthens the gap in proportion, so a longer minimum pulse is
worse, not better. Below about 36 µs no pulse strikes at all. It **marks from
about 10 percent density** at 300 mm/min on scrap.

A 3-tick minimum is essentially the factory's own structure: its 6.5 percent
engrave jobs put 100 µs pulses 1.54 ms apart, against 1.64 ms for a 3-tick
minimum at that density.

That closes the pulse-shape route to a usable 1 percent: the interval grows
as 1/density, so 1 percent implies an 11 ms gap, five times what already
failed. The low end is a scaling problem instead, and the density floor is
what solves it ([the grblHAL driver](../forgefirm/grblhal-driver.md)).

## What actually lets the beam out

The fire bit is a *request*. Emission additionally requires the hardware
safing chain to agree: the lid switches, the remote interlock loop, HV good,
the supply rails, the charge-pump watchdog the kernel feeds only while a
program is playing, and the physical button latch. The chain is described on
[The safing chain](safing-chain.md). On top of that, ForgeFIRM keeps the
kernel's **laser latch** locked except inside an operator-armed job window, and
the kernel relocks it whenever the pulse device is closed.

Emission permission is FIRE ∧ chain. The laser-off guarantee rests on FIRE, and
the kernel drops FIRE within one tick on end-of-data or underrun.

Fire only ever rides motion segments of laser blocks. Rapids and homing are
fire-free by construction, not by convention; a jog is shipped dark by the
stream whatever the modal spindle says.

## Emission witnesses

The software-visible evidence that the tube fires, or may fire:

- **`laser_on`** is the readback of the gated LASER_ON output on J1_12, the
  only software-visible proof of emission permission. `laser_on_sampled`
  counts, over a window of about one second (255 samples, one every
  ≈ 3.9 ms), how many samples read the line active.
- **`laser_enable`** is the state of the FIRE drive line: what the SoC
  requested, not what the chain did.
- **The head beam detector** (`beam_detect_analog`, `beam_detect_digital`) is
  the live emission witness ForgeFIRM reads during a job. It is a scatter
  detector inside the head, ahead of the mirror that turns the beam down to
  the work, so it sees the beam and not the material. See
  [Sensors](sensors.md).
- **`hv_current`** and **`hv_voltage`** are the supply's analog readings;
  every supply examined ties the voltage input to ground. `hv_current` is the
  only live high-voltage telemetry on this supply, and it is a
  **presence-or-absence witness only**: the per-rung means of a power ladder
  are not monotonic at the top of the range, and the signal has no
  characterized transfer function. Read it as "the tube is drawing current",
  never as "the tube is delivering this much light". See [Sensors](sensors.md).
- **`laser_pgood`** (and `laser_pgood_sampled`) read the supply's power-good
  line: 1 while the supply's supervisor reports every DC output within spec,
  which is every moment a healthy supply is on. It does not follow HV_ENABLE
  or emission, so it witnesses a supply fault, never the beam.

The attribute reference for these readbacks is on
[the kernel module](../forgefirm/kernel-module.md).
