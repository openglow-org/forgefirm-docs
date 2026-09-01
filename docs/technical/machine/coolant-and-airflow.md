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
output has no readback. The heater exists for diagnostics, not for warming the
machine up: it is how the cooling engine proves the coolant is actually moving
(see [the cooling engine](../forgefirm/cooling-engine.md)).

| Piece | Control | Notes |
|---|---|---|
| Pump | `thermal/water_pump_on` (0 = off, 1 = on) | A pump stop/start cycle can airlock the loop. |
| Inline heater | `thermal/heater_pwm` (0 to 65535, 0 = off) | Sits in the loop between the two water temperature sensors, so heat it puts in shows up as a difference between them. |
| TEC | `thermal/tec_on` (0 = off, 1 = on) | Pro machines only. Basic and Plus have no TEC fitted, and writing here does nothing on those. |
| Upstream thermistor | `pic/water_temp_2` | 10 kΩ B3380 NTC; conversion on [Sensors](sensors.md). |
| Downstream thermistor | `pic/water_temp_1` | Same sensor, downstream of the heater. |
| TEC temperature | `pic/tec_temp` | Pro only; conversion unknown; rails at 1023 without a TEC. |

**Coolant temperature is read, not guessed.** Both thermistors are converted
with the factory's own beta-equation curve, checked against a thermometer
([Sensors](sensors.md)). A sensor reading at either rail is treated as open or
shorted, not as a temperature.

## The airflow path

**The airflow path** has four independently driven pieces:

| Piece | What it does | Control |
|---|---|---|
| Exhaust blower | pulls smoke out of the enclosure | `thermal/exhaust_pwm` (0 to 65535) |
| Two intake fans | feed clean air in behind it | `thermal/intake_pwm` (0 to 65535); one output drives both fans |
| Air assist (in the head) | blows the cut line clear at the focal point | `head/air_assist_pwm` (0 to 1023); the factory firmware never sets it below 204, so the fan is never off |
| Purge air (in the head) | keeps the optics clean by purging smoke from the lens cavity; on whenever the machine is on | `head/purge_air` (0 = off, 1 = on) |

Every fan reports a tachometer, so the engine can tell a commanded duty from an
actual airflow, and the panel shows real speeds rather than setpoints: the
exhaust (`thermal/tach_exhaust`), each intake (`thermal/tach_intake_1`,
`thermal/tach_intake_2`) and the air assist (`head/air_assist_tach`) report
the period between tach pulses. The purge-air fan has no tachometer and
reports its current instead (`head/purge_air_current`). The period units and
RPM formulas are on [Sensors](sensors.md).

## What the kernel does on its own

On a dead man's switch trip (and on module removal) the kernel de-energizes
the heat sources, the loop heater and the TEC, and touches nothing else. The
pump, the exhaust and intake fans, and the head airflow belong to the cooling
engine and stay as they are: airflow and coolant circulation after an aborted
cut are wanted, and a pump stop/start cycle can airlock the loop. See
[the kernel module](../forgefirm/kernel-module.md).

The attribute reference for every control above is on
[the kernel module](../forgefirm/kernel-module.md).
