---
title: Diagnostics
---

# Diagnostics

The panel's Setup tab runs hardware tests that take the machine over.
This page tells you what each tool does, how long it takes, and when to run it.
The setup runs the same tests as its coolant steps, with the automatic heater
retry and the record ([Setup](setup.md#the-checks)); the tools
here are the way to run one by hand.

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
The routes are `POST /diag/flow-verify`, `POST /diag/flow-calibrate`,
`POST /diag/aa-offset-calibrate`, `POST /diag/abort`, and `GET /diag/status`
for the live progress.

## Cooling system: verifying and calibrating flow

The two flow tools prove and tune coolant flow verification, the check that
tells a circulating loop from a stagnant one by heating the coolant and
watching the downstream sensor ([The cooling engine](../technical/forgefirm/cooling-engine.md)).

Both tools run at your *configured* duty, window, and threshold
(`cool_flow_heater_pct`, `cool_flow_check_s`, `cool_flow_rise`), so the
verdict applies to the check the machine actually performs, and both use
cut-profile chassis fans, the condition the numbers were characterized under.
Any pump-off window aborts immediately if the downstream sensor passes 48 °C.

**Flow verify** (about 3 minutes): one check with the pump running and one
with it commanded off.

- **PASS** = your threshold separates the two readings.
- Margins under 1.5 °C add a warning that you should re-calibrate.
- A failure here means the threshold no longer suits the loop, or the loop has
  a real problem.

**Flow calibrate** (15 to 25 minutes): three trials of each case, alternating,
with settle gates between them. It reports both bands and recommends a
threshold midway between the highest flowing reading and the lowest stagnant
one, with an **Apply** button that writes it to `cool_flow_rise`.

- If the gap between the bands is under 3 °C it refuses to recommend anything
  and tells you to raise the heater duty and rerun.

**When to calibrate:** after replacing coolant (a different blend carries heat
differently), after changing or servicing the pump, if flow verify warns about
thin margins, or if you see suspicions that you can trace to nothing real. The
shipped default suits the factory loop; a rebuilt one may differ.

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
stands ([LightBurn, Power](lightburn.md#power)).
