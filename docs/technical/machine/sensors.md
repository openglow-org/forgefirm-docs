---
title: Sensors
---

# Sensors

This page lists the machine's sensors: what each one measures, its raw range,
and how a raw reading converts to a physical value. One formula per sensor,
stated once. The sysfs attribute reference (names, permissions, groups) is on
[the kernel module](../forgefirm/kernel-module.md); this page keeps what the
sensor is and how its reading converts.

The reference implementation of the conversions is forgectrl `src/status.c`;
`gfhardware`'s `cooling.py` implements the coolant conversion for the cloud
client. The GRBL controller converts nothing: it enforces the cooling engine's
published verdict.
Consumers must not reintroduce private variants.

Most analog readings come through the board's PIC analog/digital I/O
controller (the `pic/*` group), whose 10-bit ADC returns 0 to 1023.

## Coolant temperature (`pic/water_temp_1`, `pic/water_temp_2`)

Both water sensors are 10 kΩ B3380 NTC thermistors in a 10 kΩ divider behind a
1.3× gain stage, read by a 10-bit ADC. The factory firmware converts with the
single-parameter B (beta) equation, and ForgeFIRM uses the same formula:

```
F    = 1024 * 1.3                      # ADC steps x gain = 1331.2
R    = 10000 / (F / raw - 1)           # divider resistor 10 kΩ
Rinf = 10000 * exp(-3380 / 298.15)     # R0 = 10 kΩ at 25 C, beta = 3380
degC = 3380 / ln(R / Rinf) - 273.15
```

Higher raw = colder (NTC), so a rising reading means a falling temperature.
The constants are the factory's own, not a curve fit, which is why they are
exact. Treat `raw <= 0` or `raw >= F` as an open or shorted sensor, not a
temperature.

Reference points: raw 640 → 27.0 C, 680 → 23.9 C, 740 → 19.2 C; inversely
31.04 C → raw 591, 50.01 C → raw 391. Checked against a thermometer with the
loop at room-temperature equilibrium: within about 1 C of measured.

`water_temp_1` is **downstream** of the flow-check heater, `water_temp_2`
**upstream**. The run and resume ceilings gate on the upstream sensor (see
[the cooling engine](../forgefirm/cooling-engine.md)).

## Chassis temperature (LM75)

Read through `/sys/class/hwmon`, **resolved by name, never by index**:
enumerate `hwmon*/name` and use the node whose name starts with `lm75`
(`temp1_input`, millidegrees C). hwmon numbering depends on probe order; on
this platform `hwmon0` is `imx_thermal_zone` (the CPU die) and `hwmon1` is
`lm75b`, so a hardcoded `hwmon0` reads the CPU die.

## SoC die temperature

The i.MX6 on-die monitor reports the SoC temperature in degrees. The SoC
guards itself: the kernel throttles the CPU at 85 C and powers the board off at
90 C on this part. forgectrl reports the temperature as `soc_c` and the
throttle state as `soc_throttle` (0 at full speed).

## Power-supply and TEC temperatures (`pic/pwr_temp`, `pic/tec_temp`)

`pwr_temp` (0 to 1023): best guess `degC = raw * 0.08715 - 21`,
**unverified**. The slope is positive, so this is not the coolant NTC path:
the factory firmware instantiates the beta-equation conversion only for the two
water sensors. The conversion stays unverified by decision (the supply's
heatsink cannot be reached with a thermometer while the machine runs), so
ForgeFIRM reports this sensor as a raw count (`supply_raw`) and never as
degrees.

`tec_temp` (0 to 1023): the thermoelectric cooler temperature. The conversion
is unknown (it does not use the coolant beta conversion). Pro machines only: on
a Basic or Plus there is no TEC and no sensor, and the reading sits at the 1023
rail. Report raw values as raw, never as trusted degrees.

## High-voltage supply (`pic/hv_current`, `pic/hv_voltage`)

`hv_current` (0 to 1023): HV current. The exact meaning of the value is not
established; ForgeFIRM ranges it in every job's log line.

`hv_voltage` (0 to 1023): HV voltage. Every power supply examined ties the
input of this A/D to ground.

## Lid IR sensors (`pic/lid_ir_1` to `pic/lid_ir_4`)

Four IR sensors in the lid, each 0 to 1023. Their purpose is flame detection
within the enclosure; the factory sends per-job IR thresholds in every pulse
header (see [Factory firmware](factory-firmware.md)). The lid IR channels read
the lid lamp, so a threshold has to be lamp-aware; ForgeFIRM's fire watch is on
[the cooling engine](../forgefirm/cooling-engine.md).

## Fan tachometers

All tachometer attributes report the **period between pulses**; 0 = stopped or
stalled (not "infinite speed").

| Attribute | Period unit | Pulses per revolution | RPM |
|---|---|---|---|
| `thermal/tach_exhaust` | ns | 2 | `60e9 / (period * 2)` |
| `thermal/tach_intake_1`, `_2` | ns | 2 | `60e9 / (period * 2)` |
| `head/air_assist_tach` | µs | 8 | `60e6 / (period * 8)` |

The purge-air fan in the head has no tachometer. `head/purge_air_current`
(0 to 1023) is a raw current reading, qualitative only: about 1 with the fan
off, about 628 with it on.

## Head sensors

- **Lens hall sensor** (`head/hall_sensor`, 0 or 1): the lens home-position
  sensor. 1 = at the home position. It changes to 1 when the lens is at or
  above a specific positive position, and that position varies from unit to
  unit; the factory's hunt program tells each machine how many steps toward
  the bed reach the zero focus level (see [Homing](../forgefirm/homing.md)).
- **Beam detector** (`head/beam_detect_analog`, 0 to 65535;
  `head/beam_detect_digital`, 0 or 1): the analog and digital outputs of the
  beam detector in the head. How the detector operates is not fully
  investigated; ForgeFIRM reads the analog output as the live emission
  witness during a job (see [The laser](laser.md)).
- **Accelerometer**: the head carries an ST LIS2HH12 accelerometer, bound to
  the mainline `st_accel` driver, with two on-chip interrupt generators.
  `head/accel_irq` reports whether it set its IRQ. The accelerometer is the
  machine's **motion witness**: the step drives are open loop, so position
  counters are never proof of motion, and it is the sensor ForgeFIRM's
  motion-liveness gate and crash watch use (see
  [forgectrl](../forgefirm/forgectrl.md) and
  [the cooling engine](../forgefirm/cooling-engine.md)).

## Safety-chain readbacks

The lid switches, the button, the interlock loop, the two latches, the
charge-pump watchdog, LASER_ON and LASER_PGOOD are all readable. They are
monitoring only; enforcement is the hardware AND gate. The inputs, their pins
and their Linux exposure are tabulated on
[The safing chain](safing-chain.md); the attribute and switch reference is on
[the kernel module](../forgefirm/kernel-module.md) and
[forgectrl](../forgefirm/forgectrl.md).
