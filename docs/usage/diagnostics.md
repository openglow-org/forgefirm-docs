---
title: Diagnostics
---

# Diagnostics

The panel's Setup tab runs hardware tests that take the machine over.
This page tells you what each tool does, how long it takes, and when to run it.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## What a diagnostic does to the machine

Every tool on the tab takes the hardware over: the active controller is
suspended through the supervisor for the duration, the cooling engine stands
aside and publishes fire-blocked, and the controller is restored on every exit
path (completion, a tool error, or your pressing **Abort**). The laser stays
latched throughout; a diagnostic never touches it. While a diagnostic runs,
settings cannot be saved, `/status` reports `diag: true`, and the panel locks
with a banner. Progress, both coolant temperatures, and a scrolling log stream
to the page while it runs.

A diagnostic starts only when the machine is idle and no other diagnostic runs.
The routes are `POST /diag/aa-offset-calibrate`, `POST /diag/abort`, and
`GET /diag/status` for the live progress.

## Coolant offset

**Calibrate coolant offset** measures the air-assist fan's effect on the two
coolant readings. The fan's return current shares a ground with the
thermistors' reference, so both coolant sensors read low by a fixed number of
counts while the fan runs (about 20 counts, or 1.2 °C near 22 °C, at the run
duty on the bench reference). The tool steps the fan from idle to run and
back three times, with the tube dark and the heater off, averages the step on
both sensors at every edge, and recommends the value for
`cool_aa_offset_counts`; **Apply** writes it. Zero, the default, is the factory
behavior, which never corrected the shift. Without the correction the
over-temperature gates read the coolant about 1.2 °C cooler than it is while
the air assist runs ([Cooling and fans](cooling-and-fans.md)).

## Other measurements from the panel

The **dose-curve recorder** on the GRBL tab measures your tube's own dose curve
in one press. It is a laser job, not a diagnostic: it runs the ladder job
itself, you press the physical button to start the fire, and every arm gate
stands ([LightBurn, Power](lightburn.md#power)). It measures with the head's
beam sensor. If the sensor gives no output, the recorder still burns the
whole ladder. Then it fails at the end with a notice that says so. The
machine keeps the curve it has and runs as before.
