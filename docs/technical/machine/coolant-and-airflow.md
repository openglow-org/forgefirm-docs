---
title: Coolant and airflow
---

# Coolant and airflow

This page describes the machine's thermal hardware: the coolant loop, the
airflow path, and the controls and readbacks each piece offers. How ForgeFIRM's
cooling engine drives them is on
[the cooling engine](../forgefirm/cooling-engine.md); what the operator sees
and can set is on [Cooling and fans](../../usage/cooling-and-fans.md).

The tube is water-cooled and the enclosure is air-cleared, and both matter
while the laser fires: coolant that has stopped circulating will let a tube
overheat within a cut, and smoke that is not pulled out spoils the work and
fogs the optics.

## The coolant loop

**The coolant loop** is closed: a pump, a radiator with fans, the laser tube,
and two thermistors, one **upstream** of the tube and one **downstream** of a
small inline heater. Pro machines are specified with a thermoelectric cooler
(TEC) on the loop; the board cannot tell whether one is fitted, because the TEC
output has no readback and the TEC temperature input says nothing about it
([Sensors](sensors.md#power-supply-and-tec-temperatures-picpwr_temp-pictec_temp)).
The heater exists for diagnostics, not for warming the
machine up: it is how the cooling engine proves the coolant is actually moving
(see [the cooling engine](../forgefirm/cooling-engine.md)).

| Piece | Control | Notes |
|---|---|---|
| Pump | `thermal/water_pump_on` (0 = off, 1 = on) | A pump stop/start cycle can airlock the loop. |
| Inline heater | `thermal/heater_pwm` (0 to 65535, 0 = off) | Sits in the loop between the two water temperature sensors, so heat it puts in shows up as a difference between them. |
| TEC | `thermal/tec_on` (0 = off, 1 = on) | Pro machines only. Basic and Plus have no TEC fitted, and writing here does nothing on those. |
| Upstream thermistor | `pic/water_temp_2` | 10 kΩ B3380 NTC; conversion on [Sensors](sensors.md). |
| Downstream thermistor | `pic/water_temp_1` | Same sensor, downstream of the heater. |
| TEC temperature | `pic/tec_temp` | A raw input; what it reads is on [Sensors](sensors.md#power-supply-and-tec-temperatures-picpwr_temp-pictec_temp). |

**Coolant temperature is read, not guessed.** Both thermistors are converted
with the factory's own beta-equation curve, checked against a thermometer
([Sensors](sensors.md)). A sensor reading at either rail is treated as open or
shorted, not as a temperature.

## The airflow path

**The airflow path** has four independently driven pieces:

| Piece | What it does | Control |
|---|---|---|
| Exhaust blower | pulls smoke out of the enclosure | `thermal/exhaust_pwm` (0 to 65535) |
| Intake fans, two or one | feed clean air in behind it | `thermal/intake_pwm` (0 to 65535); one output drives every intake fan |
| Air assist (in the head) | blows the cut line clear at the focal point | `head/air_assist_pwm` (0 to 1023); the factory firmware never sets it below 204, so the fan is never off |
| Purge air (in the head) | keeps the optics clean by purging smoke from the lens cavity; on whenever the machine is on | `head/purge_air` (0 = off, 1 = on) |

Every fan reports a tachometer, so the engine can tell a commanded duty from an
actual airflow, and the panel shows real speeds rather than setpoints: the
exhaust (`thermal/tach_exhaust`), each intake (`thermal/tach_intake_1`,
`thermal/tach_intake_2`) and the air assist (`head/air_assist_tach`) report
the period between tach pulses. The purge-air fan has no tachometer and
reports its current instead (`head/purge_air_current`). The period units and
RPM formulas are on [Sensors](sensors.md).

### One intake fan or two

Machines are built with two intake fans or with one. The bench reference has
two. A Pro from 2021 has one, the same make and model of fan as the bench
reference's, on the intake 1 tach. Its intake 2 tach never reads a pulse,
which is what a tach with no fan on it reads: the kernel reads 0 below
10 Hz (300 rpm at 2 pulses per revolution). The factory firmware carries a
setting that names the intake tachs it does not watch
(`intake_disabled_tachs`, a bitmask, 0 by default); where a machine gets
its value is not known. No other fan has one.

A silent intake 2 tach beside a turning intake 1 therefore reads the same
on a machine built with one intake fan as on a machine with two whose
second fan has stopped or come unplugged. ForgeFIRM keeps the count in
`cool_intake_fans`. The setup's Intake fans step counts the intake fans
before its checks, and where the tachs cannot tell, which is a silent
intake 2 or an intake 1 that does not come up to speed, it asks the
operator to look. Its airflow check goes by that count: a silent intake 2
is one fan on a machine counted with one and a failed check on a machine
counted with two, and both intakes turning set the count to two. Until the
count is known, no controller runs for a Grbl sender
([Setup](../../usage/setup.md#the-gate)). With one intake fan, the airflow
gates leave the second intake out; with two, a silent intake 2 trips the
airflow gate in every cut until it turns
([the cooling engine](../forgefirm/cooling-engine.md#airflow-gates-a-fan-that-is-not-moving-the-air)).

### What the fans actually reach

Measured on the bench reference
([The bench reference](index.md#the-bench-reference)) at the cut profile,
sampled once a second for two minutes from idle:

| Fan | Steady | Spread | Time to 90 % | At idle |
|---|---|---|---|---|
| Exhaust | 11640 rpm | 11444 to 11947 | 5 s | 0 rpm (off) |
| Intake 1 | 4157 rpm | under 100 rpm | 7 s | about 745 rpm |
| Intake 2 | 4158 rpm | under 100 rpm | 7 s | about 745 rpm |
| Air assist | 11050 rpm | 30 rpm | 1 s | about 1900 rpm (duty 204) |
| Purge air | about 625 counts of current | | | about 625 (always on) |

The purge fan reads about 1 with no current at all, which is what a dead one
looks like.

These are the numbers ForgeFIRM's airflow floors ship at 55 percent of, and
the spin-up times are why the gates have a grace window
([the cooling engine](../forgefirm/cooling-engine.md#airflow-gates-a-fan-that-is-not-moving-the-air)).
They are one machine's: an exhaust duct with an inline booster fan changes the
back pressure and can move the exhaust reading by a few percent either way,
and the setup airflow check measures your machine's own
([Setup](../../usage/setup.md#the-checks)).

## What the kernel does on its own

On a dead man's switch trip, and on module removal, the kernel de-energizes
the **heat sources only**, the loop heater and the TEC, and touches nothing
else. The pump, the exhaust and intake fans and the head airflow belong to the
cooling engine and stay as they are, deliberately: see
[the kernel module](../forgefirm/kernel-module.md#fail-safe-behavior) for why.

The attribute reference for every control above is on
[the kernel module](../forgefirm/kernel-module.md).
