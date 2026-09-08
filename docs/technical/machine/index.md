---
title: The machine
---

# The machine

This section describes the Glowforge machine as built, independent of
ForgeFIRM: the control board's safing chain, the step engine, the laser drive,
the motion hardware, the sensors, the coolant and airflow hardware, the
cameras, the buses, the boot and storage layout, and how the factory firmware
and its cloud protocol work. How ForgeFIRM drives all of it is in
[ForgeFIRM internals](../forgefirm/index.md).

## The models

The control board is common to the Glowforge Basic, Plus, and Pro. Its SoC is
an NXP i.MX6 Solo, a single-core part. One ForgeFIRM image covers every model.

What is common to all of them:

- The hardware safing chain on the control board
  ([The safing chain](safing-chain.md)).
- The SDMA + EPIT step engine and its 32 MiB pulse ring
  ([The step engine](step-engine.md)).
- A 495 × 279 mm work area, and no limit or home switches as shipped
  ([Motion hardware](motion-hardware.md)).
- A closed coolant loop with a pump, a radiator, two thermistors and an inline
  heater; an exhaust blower, two intake fans, and air assist and purge air in
  the head ([Coolant and airflow](coolant-and-airflow.md)).
- Two cameras, one in the lid and one in the head, sharing one MIPI receiver
  through a hardware switch ([Cameras](cameras.md)).

What differs:

| | Basic and Plus | Pro |
|---|---|---|
| Remote-interlock connector (J8) | factory-jumpered, so the loop always reads closed | brought out for an external lockout chain |
| Thermoelectric cooler (TEC) on the coolant loop | not fitted; the TEC temperature reading sits at the 1023 rail | specified; the board cannot detect whether one is fitted |

Independently of the model, two camera-sensor variants exist. Standard machines
carry the **5 MP OV5648**; "HD" machines carry the **8 MP OV8856**. The 5 MP
path is hardware-validated. The 8 MP capture path is complete in the firmware
and is untested on hardware, because no 8 MP machine has been available
([Cameras](cameras.md)).

Early machines have the FT230X USB-serial bridge (U37) and its micro-USB
connector (J13) populated on the control board; later boards carry only the
footprints ([Buses and the serial console](buses.md)).

## The bench reference

**The bench reference is one machine: a Glowforge Basic built in late 2017.**
Every measured value on this site was taken on it, unless the page says
otherwise. Values that come from somewhere else say so: a figure decoded from
the factory firmware, a number read off a captured pulse file, a manufacturer's
datasheet, or a drawing.

Read every measurement as *what this one machine does*, not as a
specification. Three things make another machine read differently:

- **Manufacturing variance.** Two units off the same line differ. A fan's
  steady speed, a thermistor's exact curve, the step at which a lens hall
  sensor trips, the duty at which a tube strikes: each is a part with a
  tolerance, and each has been seen to vary.
- **Changes to the product over time.** Glowforge revised the machine across
  its production run. The control board is common to every model, but the
  parts around it are not all the same as the bench reference's.
- **Model differences.** A Pro has a remote-interlock connector brought out
  and is specified with a thermoelectric cooler; a Basic and a Plus have
  neither fitted (the table above). An "HD" machine carries a different
  camera sensor.

This is why the numbers that matter are **settings, not constants**. Every
value a machine can measure for itself is a setting with a wide legal range,
and the bench reference's measurement is only its shipped default: the fan
floors, the coolant flow threshold, the tube's heat coefficients, the
air-assist offset on the coolant readings, the laser floor and dose curve, and
the head's lens reference height. The first run of the control panel measures
them on your machine and writes your values
([Commissioning](../../usage/commissioning.md)).

Where a number is a genuine constant, it is one because the mechanism makes it
so, and the page says which: the lens screw's pitch, the step engine's byte
grid, the pulse header's tag table.

## Pages in this section

| Page | Contents |
|---|---|
| [The safing chain](safing-chain.md) | The parts, inputs, SoC outputs and logic of the laser-safing hardware; what each condition does in hardware alone; what is proven. |
| [The step engine](step-engine.md) | EPIT + SDMA, one byte per tick, the byte layout, the ring, the position counters, stop and resume. |
| [The laser](laser.md) | The power byte and PWM, the fire bit, the rules the hardware imposes, what lets the beam out, the emission witnesses. |
| [Motion hardware](motion-hardware.md) | Steps per millimeter, axis directions, travel, speed and acceleration limits, the stepper drives, the 40 V rail. |
| [Sensors](sensors.md) | Every sensor, its raw range, and how the reading converts. |
| [Coolant and airflow](coolant-and-airflow.md) | The coolant loop, the heater, the TEC, the fans and their tachometers. |
| [Cameras](cameras.md) | The two cameras, the MIPI switch, the sensors and their modes, the 8 MP status. |
| [Buses and the serial console](buses.md) | The pogo-pin serial console port and the I²C devices. |
| [Boot and storage](boot-and-storage.md) | The eMMC layout, boot0/boot1, U-Boot and its environment, the A/B slots, recovery mode, the `.fw` format. |
| [Factory firmware](factory-firmware.md) | How the factory machine works: the session, the pulse file, the header, the holds around a print. |
| [Cloud protocol](cloud-protocol.md) | Sign-in, the wire format, the actions, the events, progress reporting, image upload. |
