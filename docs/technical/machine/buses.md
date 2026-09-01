---
title: Buses and the serial console
---

# Buses and the serial console

This page describes the control board's serial console port and the I²C
devices the public documents name. The circuit of the pogo-pin serial adapter
is in its own repository:
[DESIGN.md](https://github.com/ScottW514/openglow-serial-adapter/blob/main/DESIGN.md).
How to get a console on your machine is on
[Serial access](../../install/serial-access.md).

## The serial console

The i.MX6 serial console is brought out to the factory in-circuit-test via grid
on the control board. Three usable points sit in a **straight line on the
2.54 mm (0.100") test grid**:

| Position | Board test point | Net | Direction (board) |
|---|---|---|---|
| 1 | **D3B** | `SERIAL_CONSOLE_TX`: i.MX6 `UART1_TX`, ball M1 | output |
| 2 | **D3D** | `SERIAL_CONSOLE_RX`: i.MX6 `UART1_RX`, ball M3 | input |
| 3 | unlabeled via | `GND` | none |

Facts about the interface:

- **The console runs at 1.8 V, not 3.3 V.** In the ForgeFIRM device tree the
  console pads are `MX6QDL_PAD_CSI0_DAT10__UART1_TX_DATA` /
  `CSI0_DAT11__UART1_RX_DATA`, which live in the i.MX6 `NVCC_CSI` supply
  domain (test point C4D). Applying 3.3 V or 5 V destroys the control board.
- **Pad configuration is `PAD_CTL_PUS_100K_UP`**: the target's own RX pad
  holds itself high through a 100 kΩ pull-up when nothing drives it.
- Console settings are **115200 8N1**.
- The factory board carries an unpopulated FT230X footprint (U37) and
  micro-USB connector (J13) on the same two nets; on early machines those are
  stuffed and no adapter is needed.
- The vias are through-plated, so the same three points are reachable from the
  **bottom** of the board if it is removed, a fallback if the top side is too
  crowded.
- The test points are bare ENIG vias, roughly 0.7 to 0.9 mm pad over a
  ~0.3 mm drill, with neighboring grid points 2.54 mm away in every direction.

### The problem an unpowered adapter causes

A plain 1.8 V TTL cable soldered to the test points carries a defect: **when the
adapter is not powered it must be unplugged, or the machine will not boot.**
Two mechanisms:

1. The target's TX idles high at 1.8 V into the adapter's unpowered input pin.
   Current flows through that input's ESD clamp into the dead I/O rail,
   clamping the line to about 0.6 V and pulling milliamps out of the board's
   1.8 V bus.
2. The adapter's unpowered TX pin holds the target's RX low, which the console
   reads as a continuous break / `0x00`, enough to interrupt U-Boot autoboot.

The pogo-pin adapter is designed to be clipped on and left there, so its
unpowered state is benign: both target-facing pins go high-impedance (≤ 2 µA)
when USB is unplugged. The circuit that achieves this is in
[DESIGN.md](https://github.com/ScottW514/openglow-serial-adapter/blob/main/DESIGN.md).

## I²C devices

The public documents name these I²C devices on the board and in the head:

| Device | Where | What the documents state |
|---|---|---|
| Camera sensor (OV5648 or OV8856) | camera bus | Both sensors share one device-tree node, `camera@36` (address 0x36); the capture path follows whichever driver bound. See [Cameras](cameras.md). |
| Chassis temperature sensor | board | An LM75-class part, bound as hwmon `lm75b`. See [Sensors](sensors.md). |
| Head MCU | print head | The head answers I²C with its id and serial. The head-attention line (gpio-keys code 7, `head`) pulses while the head MCU reboots and is **not** a head-present indicator; presence is the head driver having probed. |
| Head accelerometer | print head | An ST LIS2HH12, bound to the mainline `st_accel` driver; its two on-chip interrupt generators are reachable over `i2c-dev`. See [Sensors](sensors.md). |
| PIC analog/digital I/O | board | A register interface of 16-bit values (firmware id 19795) carrying the analog sensors, the button and lid LEDs, and the X/Y stepper currents. See [the kernel module](../forgefirm/kernel-module.md). |

Bus numbers and the remaining addresses are not stated in the public
documents.
