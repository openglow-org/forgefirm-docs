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

### Three things that move a coolant reading, and are not temperature

All three were found on the bench reference and all three are small, but each
is the size of a gate's margin, so each is corrected or accounted for
somewhere in the stack.

**The processor's load at the moment of conversion, about 6 counts (0.35 C).**
The PIC converts its inputs in a free-running loop and a read returns the last
conversion, so what a reader gets was converted before it asked. The ADC
references the PIC's own supply while the sensor dividers hang on the board's
reference, so the count follows whatever the supply is doing, and the SoC's
load moves it: a value converted while the processor idled reads about 6
counts below one converted under load, with both regimes tight (an
interquartile range of 2 over 200 reads). A reader that wakes and reads at
once therefore gets one regime, and its next read a fraction of a millisecond
later gets the other. The kernel module removes the split by keeping the
processor busy before every transaction
([the kernel module](../forgefirm/kernel-module.md#sysglowforgepic)).

**The air-assist fan's return current, about 20 counts (1.2 C).** The fan's
return shares a ground path with the two thermistors' reference, so **both**
sensors read low by the same amount while it runs, in proportion to the fan's
current: nothing below the fan's start duty of 256, and about 1.2 C at the run
duty near 22 C. It is not crosstalk on the sensor cable and it is not the
high-voltage supply; the step appears with the fan and reverses with it, and
a session in which the fan never left idle showed none. The correction is a
per-machine setting the coolant-offset diagnostic measures
([the cooling engine](../forgefirm/cooling-engine.md#the-air-assist-offset-on-the-coolant-readings)).

**A lit tube, 0.6 to 1.1 C, toggling.** With the tube firing, both readings
step between two levels mid-run, together, up to twenty-odd times in a run. It
is not the fans (steady fans alone show none), not motion (a jog with the fan
at run duty shows none), and not the armed state (an armed window with no
emission shows none): every toggle sits inside a lit period. The remaining
candidate is the high-voltage supply's input current on a return the
thermistor reference shares, or its switching. **The source stays
uncharacterized by decision**: the toggle sits inside the over-temperature
ceiling's 2 C hysteresis, and the flow check reads means rather than single
samples, so it has no consequence for any gate. Settling it wants a scope on
the two sensor lines during a cut.

Rare excursions of 10 to 25 counts appear in every regime at a few samples per
hundred; the diagnostics that care take interquartile means and drop them.

## Chassis temperature (LM75)

Read through `/sys/class/hwmon`, **resolved by name, never by index**:
enumerate `hwmon*/name` and use the node whose name starts with `lm75`
(`temp1_input`, millidegrees C). hwmon numbering depends on probe order; on
this platform `hwmon0` is `imx_thermal_zone` (the CPU die) and `hwmon1` is
`lm75b`, so a hardcoded `hwmon0` reads the CPU die.

## SoC die temperature

The i.MX6 on-die monitor is `thermal_zone0` (`imx_thermal_zone`, the same node
as `hwmon0`), governor `step_wise`. forgectrl reports the temperature as
`soc_c` and the throttle state as `soc_throttle` (0 at full speed).

**The SoC guards itself.** Its trip points are the consumer-grade ones the
driver derives from the part's own fuses: a hot point of 95 C, critical at hot
minus 5, passive at hot minus 10, so **85 C passive** and **90 C critical** on
this part. The passive trip is bound to `cpufreq-cpu0` (996, 792 and 396 MHz
operating points; `performance` is the only governor built, so the core sits
at 996 MHz until the trip lowers it) and to both GPU cooling devices. The
critical trip is the kernel's orderly power-off. A throttle slows the step
producer, the camera and the protocol thread before it slows the step stream,
because the ring is already in hand.

**The board carries no heatsink or fan on the SoC**, only the mounting holes
for one, and it needs none. Under a full core for five minutes on top of a
live camera stream, in a 30 C chassis, the bare die climbs 2.9 C in the first
30 seconds and then plateaus at **70.8 C** from three and a half minutes on:
14 C under the passive trip and 19 C under the power-off, with the core still
at 996 MHz and no cooling device leaving state 0. The die-to-chassis delta at
full load is about 41 C, so by arithmetic the passive trip is a hot-*chassis*
case (above roughly 44 C ambient inside the machine), not a load case.

ForgeFIRM watches this rather than gating on it: the range over each job and
any throttle go into one log line at the job's end
([the cooling engine](../forgefirm/cooling-engine.md)).

## Board temperatures at idle

For scale, with the room at about 22 C and the machine on for hours:

| Sensor | Reading |
|---|---|
| Chassis (LM75) | 29.0 C |
| Power supply (`pic/pwr_temp`) | 589 raw |
| SoC die | 42.8 C |

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
within the enclosure, and the factory sends per-job IR thresholds in every
pulse header (see [Factory firmware](factory-firmware.md)).

**They are first of all a photometer for the lid lamp.** Measured against
`lid_led` (sysfs brightness 0 to 1023) on the bench reference, all four
channels follow the lamp as a straight line, about 0.16 counts per unit:

| `lid_led` | Channels 1 and 2 | Channels 3 and 4 |
|---|---|---|
| 0 | 2 | 1 to 2 |
| 128 | 32 to 33 | 33 to 35 |
| 256 | 54 to 56 | 57 to 61 |
| 512 | 95 to 98 | 103 to 105 |
| 768 | 131 to 133 | 139 to 143 |
| 1023 | 161 to 163 | 172 to 177 |

Channels 3 and 4 read about 7 percent above 1 and 2.

Against that lamp-set level, the things a fire watch would like to see barely
move the reading. A full-power cut raises the channels only **+4 to +6
counts**, and a candle burning on the bed raises them **+3 to +6**, against
about ±3 counts of ambient noise and about +22 counts of day-to-day drift.
A candle and a cut are the same size, so no threshold separates them.

Two consequences shape ForgeFIRM's fire watch: a fixed absolute threshold has
to sit above a fully lit lamp or the lamp itself trips it, and what such a
threshold catches is a developed fire, not a small flame. The design is on
[the cooling engine](../forgefirm/cooling-engine.md#the-fire-watch).

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

- **Lens hall sensor** (`head/hall_sensor`, 0 or 1): the lens position
  reference. 1 = home, read from an edge low in the lens's travel (13
  half-steps above the bottom stop on the bench reference's head) up to the top
  stop; the edge's height varies from unit to unit. The factory's hunt steps
  4 full steps down from the edge to its zero, and its prints count up from
  there ([The motion hardware](motion-hardware.md#the-lens-and-its-travel),
  [Homing](../forgefirm/homing.md)).
- **Beam detector** (`head/beam_detect_analog`, 0 to 65535;
  `head/beam_detect_digital`, 0 or 1): the analog and digital outputs of the
  beam detector in the head. It is a scatter detector in the beam path ahead
  of the mirror that turns the beam down to the work, so it sees the beam and
  not the material. ForgeFIRM reads the analog output as the live emission
  witness during a job (see [The laser](laser.md)). Measured on the bench
  reference: near **1834 dark**, and **2600 to 2890** during fire at `S300` to
  `S400`. Its response at low fire energies is unmeasured. How the detector
  works inside the head is below.
- **Accelerometer**: the head carries an ST LIS2HH12, bound to the mainline
  `st_accel` driver. It is the machine's **motion witness**: the step drives
  are open loop, so position counters are never proof of motion, and it is the
  sensor ForgeFIRM's motion-liveness gate, crash watch and commissioning lens
  finder all use (see [forgectrl](../forgefirm/forgectrl.md),
  [the cooling engine](../forgefirm/cooling-engine.md), and
  [Motion hardware](motion-hardware.md#what-the-motion-witness-reads) for what
  it reads). `head/accel_irq` reports whether it set its IRQ. The part's own
  interrupt generator is below.

### The head accelerometer

The same part (ST LIS2HH12) sits in three places: the head at i2c-3 address
0x1e, the board at i2c-3 address 0x1d, and the lid at i2c-0 address 0x1e.
**Resolve them by bus path, never by index.**

The head one carries a full on-chip interrupt generator, and that generator is
the factory's head crash detector:

- Per-axis 8-bit thresholds (`IG_THS_X1`/`Y1`/`Z1`, registers 0x32 to 0x34),
  a duration counter (`IG_DUR1`, 0x35), a per-axis event register (`IG_SRC1`,
  0x31), full scale of ±2, ±4 or ±8 g (`CTRL4`), and two independent
  generators, IG1 and IG2.
- **The threshold LSB is full scale / 256.** The datasheet states no LSB for
  `IG_THS` (only for `ACT_THS`, which is full scale / 128), so this was
  settled on the bench: at ±2 g a threshold of 100 trips on the 1.03 g gravity
  reading and 150 does not, which brackets gravity at full scale / 256 and
  would be impossible at full scale / 128. The factory's own values agree:
  under full scale / 128 its travel-abort threshold of 133 would be 4.16 g at
  ±4 g, past the measurable range, an abort that could never fire.
- **The factory arms it per job from the pulse header's `HA*` tags**, which
  map bit-exactly onto these registers (per-axis threshold to `IG_THS`,
  duration to `IG_DUR1`, full scale to `CTRL4`, period and decimator to
  `CTRL5` and the output data rate), and reads trips by polling `IG_SRC1` over
  the accelerometer's own bus, in two tiers: an alert pauses, an abort fails.
  So the `HA*` values are register values at the scale the `HAsr` tag sets,
  not numbers in an unknown unit.
- **What the factory actually ships**, across the 23 captured headers: hunts
  arm nothing (every threshold zero); travel files are abort-only (`HAar` 133
  at ±4 g, about 2.08 g); a cut job is alert-only (`HAxr` 132, about 2.06 g;
  `HAyr` 112, about 1.75 g). `HAz*` and every idle threshold are zero in every
  header. The factory never arms Z, because gravity rides it, and never arms
  the idle state.
- **The INT pin does not reach the SoC as a host interrupt.** It wires to the
  head MCU's GPIO and surfaces only as a flag bit there (below). Neither the
  factory device tree nor ForgeFIRM's gives the accelerometer an `interrupts`
  property.
- **The generator only samples at a running output data rate**, and
  `st_accel` leaves the part powered down between one-shot reads. Anything
  that arms the generator has to set the rate itself and re-assert it after
  any liveness read. The registers coexist with the bound driver over
  `i2c-dev`: `IG_SRC1` polls at about 166 Hz while `st_accel` raw reads keep
  working.

For scale: normal commanded motion reads under 0.2 g, and a rail strike reads
1.8 g and up, so the factory's roughly 2 g band sits where it should.

### The head MCU, and what the head IRQ really is

The head carries a Kinetis KL17 at i2c-3 address 0x47. It is
**I²C-slave-only** to the SoC and never talks to the accelerometer itself.

Once per main-loop pass it samples four head-local GPIO input levels into the
read-only flag register **0x05**: bit 0 `hall_sensor` (the lens Z home), bit 1
the head accelerometer's INT pin (a bare level, not a bus read), bit 2 the raw
beam-detect comparator output, and a fourth, unidentified input the driver
does not expose (a candidate second hall sensor, or a head-present line). A
fifth flag, bit 7, is the processed beam-detect verdict (below). No GPIO pin
interrupts are configured anywhere in its firmware; every input is polled.

The **head-attention line** the SoC sees (gpio-keys code 7, factory pad name
HEAD_IRQ, GPIO3_22) is the MCU's own output driven back. It is level-driven
and mirrors register **0x02**, the latched IRQ status, being nonzero. Register
0x02 latches edges on the 0x05 bits, but only those the SoC arms through
registers **0x03** (rising) and **0x04** (falling), and it is read-to-clear.
So the SoC chooses which head events raise the line, answers by reading 0x02
to identify and clear, and reads 0x05 for live levels.

ForgeFIRM writes neither 0x03 nor 0x04 and reads neither 0x02 nor the two
undecoded flags, so **the head IRQ is dormant by construction**: the line sits
idle low with a healthy head, pulses while the head MCU reboots (hence the
60 ms debounce in the device tree), and floats to the SoC's pull-up with no
head. That is why the raw level is not a presence signal. Presence is the head
answering at address 0x47 ([Buses](buses.md)).

### Beam detect inside the head MCU

The head's beam detector is more than the two attributes the driver exposes:

- The sensor reaches the MCU's ADC on pin PTE16, and its **raw analog level**
  is register 0x16, published as `head/beam_detect_analog`.
- A float EWMA and CUSUM over five coefficients (registers 0x22 to 0x2a:
  `LAMBDA_K` 0x07ae, `LAMBDA_T` 0x1999, `THETA_R` 0x20, `THETA_T` 0x28,
  `E_T` 0x60) feeds an N-of-M sliding-window verdict into flag **0x05 bit 7**.
  ForgeFIRM's head probe writes those five coefficients, but they are the
  firmware's own power-on defaults.
- A DAC (register 0x1e, default 0x3ff) sets an analog comparator threshold
  whose raw output is flag **0x05 bit 2**, published as
  `head/beam_detect_digital`.

The driver exposes the raw comparator and the raw analog level, **not** the
processed verdict at bit 7. Whether the factory enables beam detect in
production is unknown: its 2.6.0 application carries a complete but
config-gated subsystem, with separate printing and idle enables, three
severities, a level-or-edge trigger option and a fault-report upload, and an
invalid severity defaults to disabled.

## Safety-chain readbacks

The lid switches, the button, the interlock loop, the two latches, the
charge-pump watchdog, LASER_ON and LASER_PGOOD are all readable. They are
monitoring only; enforcement is the hardware AND gate. The inputs, their pins
and their Linux exposure are tabulated on
[The safing chain](safing-chain.md); the attribute and switch reference is on
[the kernel module](../forgefirm/kernel-module.md) and
[forgectrl](../forgefirm/forgectrl.md).
