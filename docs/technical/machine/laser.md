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
| LASER_PGOOD (HV_OK) | J1_14 | Read as "power good" from the laser supply; not fully characterized. |

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
[the grblHAL driver](../forgefirm/grblhal-driver.md)).

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

Fire only ever rides motion segments of laser blocks. Jogs, rapids and homing
are fire-free by construction, not by convention.

## Emission witnesses

The software-visible evidence that the tube fires, or may fire:

- **`laser_on`** is the readback of the gated LASER_ON output on J1_12, the
  only software-visible proof of emission permission. `laser_on_sampled`
  counts, over a window of about one second (255 samples, one every
  ≈ 3.9 ms), how many samples read the line active.
- **`laser_enable`** is the state of the FIRE drive line: what the SoC
  requested, not what the chain did.
- **The head beam detector** (`beam_detect_analog`, `beam_detect_digital`) is
  the live emission witness ForgeFIRM reads during a job. See
  [Sensors](sensors.md).
- **`hv_current`** and **`hv_voltage`** are the supply's analog readings;
  their meaning is not established, and every supply examined ties the
  voltage input to ground. See [Sensors](sensors.md).
- **`laser_pgood`** (and `laser_pgood_sampled`) read the supply's HV_OK line.
  Its semantics are not fully characterized.

The attribute reference for these readbacks is on
[the kernel module](../forgefirm/kernel-module.md).
