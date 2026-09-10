---
title: Buses and the serial console
---

# Buses and the serial console

This page describes the control board's serial console port and the I²C
devices the public documents name.
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

## I²C devices

| Device | Bus and address | What it is |
|---|---|---|
| Camera sensor (OV5648 or OV8856) | camera bus, 0x36 | Both sensors share one device-tree node, `camera@36`; the capture path follows whichever driver bound. See [Cameras](cameras.md). |
| Chassis temperature sensor | board | An LM75-class part, bound as hwmon `lm75b`. See [Sensors](sensors.md). |
| Board accelerometer | i2c-3, 0x1d | An ST LIS2HH12. Static; nothing in ForgeFIRM reads it. |
| Lid accelerometer | i2c-0, 0x1e | The same part. |
| Head accelerometer | i2c-3, 0x1e | The same part, bound to the mainline `st_accel` driver; its two on-chip interrupt generators are reachable over `i2c-dev` while the driver stays bound. It is the machine's motion witness. See [Sensors](sensors.md#the-head-accelerometer). |
| Head MCU | i2c-3, 0x47 | A Kinetis KL17, I²C-slave-only to the SoC. It answers with its id and serial, carries the head's flag and interrupt registers, and holds the beam detector's own processing. See [Sensors](sensors.md#the-head-mcu-and-what-the-head-irq-really-is). |
| PIC analog/digital I/O | board, on eCSPI2, not I²C | A PIC16F1713 behind a register interface of 16-bit values (firmware id 19795) carrying the analog sensors, the button and lid LEDs, and the X/Y stepper currents. See [the kernel module](../forgefirm/kernel-module.md). |

Three accelerometers of one part number sit on two buses, so **resolve an IIO
device by its bus path, never by its index**. Probe order decides the index.

**Head presence is the head answering at address 0x47**, never the
head-attention line (gpio-keys code 7, `head`), which pulses while the head
MCU reboots and floats to the SoC's pull-up with no head at all
([Sensors](sensors.md#the-head-mcu-and-what-the-head-irq-really-is)).

## The Wi-Fi bus

The WL1805 rides **uSDHC1** as `mmc0`: 4-bit, SD high speed at 49.5 MHz, with
`no-1-8-v` (the part is 3.3 V only here). Its interrupt is GPIO6_04 and its
enable GPIO5_26.

The pad configuration is the factory's, and it matters. ForgeFIRM's device
tree carries the factory-exact values:

| Bus | Data and command pads | Clock pad |
|---|---|---|
| uSDHC1 (Wi-Fi) | `0x17069` | `0x10069` |
| uSDHC2 (SD card) and uSDHC3 (eMMC) | `0x17059` (SD2_DAT3 `0x13059`) | `0x10059` |

The Wi-Fi bus runs SPEED_MED with a 48 Ω drive strength, fast slew and
hysteresis, and a 47 kΩ pull-up on the command and data lines only, not on the
clock. The other two buses run 80 Ω.

Softer edges than these produced an occasional SDIO CRC error at the same
50 MHz clock, which surfaces as `sdio write failed (-84)` in the kernel log
and costs about a second of Wi-Fi while the wlcore firmware recovers. Nothing
safety-relevant crosses Wi-Fi, so the cost of one is a brief sender stall, but
with the factory pad values it does not recur.
