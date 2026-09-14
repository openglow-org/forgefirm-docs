---
title: Kernel module
---

# Kernel module: glowforge.ko

`glowforge.ko` is the kernel driver for the Glowforge factory control board. It
exposes the machine to userspace as a sysfs tree under `/sys/glowforge/`, a
pulse-stream character device `/dev/glowforge`, and LED class devices. This
page is the interface reference for the sysfs attributes and for the driver's
safety functions. The pulse device, the ring, and the rules a feeder must obey
are on [Pulse feeder contract](pulse-feeder-contract.md).

The driver is the OpenGlow fork of
[Glowforge/kernel-module-glowforge](https://github.com/Glowforge/kernel-module-glowforge)
and differs from the Glowforge original; this reference applies to the fork
only. The source is
[openglow-org/kernel-module-glowforge](https://github.com/openglow-org/kernel-module-glowforge).
This page and [Pulse feeder contract](pulse-feeder-contract.md) are the
module's contract: the module repository carries no separate document.

What a sensor physically is, and how a raw value converts to a temperature or
an RPM, is on [Sensors](../machine/sensors.md). The hardware safing chain that
the readbacks observe is on [Safing chain](../machine/safing-chain.md).

## Overview

The module provides an interface to the Glowforge brand CNC laser hardware:
the Basic, Plus, and Pro models on the factory i.MX6 control board. It owns
the SDMA + EPIT pulse engine, the laser latch, the safety-chain readbacks, the
PIC analog and digital I/O, the thermal outputs, the head peripherals, and the
button and lid LEDs.

### Build assumptions

The target is the factory i.MX6 Solo control board, which is
**uniprocessor**, and the module's locking is written for it: the state
spinlock (`spin_lock_bh()`) serializes the main path against the SDMA and
hrtimer callbacks, which is sufficient when only one CPU can execute kernel
code at a time. Building for a multiprocessor i.MX6 (Dual/Quad) needs that
locking re-reviewed first, in particular every place a callback reads or
writes driver state without taking the lock.

### Fail-safe behavior

On a kernel panic the driver stops the EPIT and drives the output pins safe
directly: the laser FIRE line to high impedance, the charge pump low so the
hardware watchdog stops being fed, the latch reset asserted, and the steppers
de-energized. SDMA and EPIT run without the CPU, so without this the machine
would play out the rest of the pulse ring with no kernel alive. The kernel
configuration turns an oops into a panic so that this notifier runs
([Image and BSP](image-and-bsp.md#kernel-configuration)).

On a dead man's switch trip the head is put in its safe state (measure laser
and UV LED off, lens motor de-energized) and the thermal loop de-energizes its
heat sources (loop heater and TEC). Everything airflow- and
circulation-related is deliberately left as it is: the head fans, the white
LED, the coolant pump, and the exhaust and intake fans belong to the cooling
engine and the camera respectively. Airflow and coolant circulation after an
aborted cut are wanted, and a pump stop/start cycle can airlock the loop.

## Safety functions

Every function below sits in front of the hardware chain. It can only
withhold FIRE, hold the lock, or starve the charge pump. None can produce
emission the hardware would not allow.

- **Laser latch** (`cnc/laser_latch`, write-only): 1 = lock. Locking drives
  LATCH_RESET high (the button latch SETs) *and* puts the FIRE line in high
  impedance, so the SDMA stream physically cannot raise it. **Locked by
  default; the final close of `/dev/glowforge` relocks** (the release of the
  open file, once every inherited copy of the descriptor is gone). Unlocking never restores
  the FIRE drive while a run or ramp is in flight. Only run start does, and
  only if the latch is unlocked at that moment; nothing in the driver writes
  the GPIO data register while the script runs. A resume's laser-off lead
  is the script's own doing: it masks the laser bits out of every word it
  writes until the waypoint byte, then clears the mask itself.
- **Charge pump only while running.** The 200 ms retrigger starts with the
  run, and the callback returns without rearming as soon as the state leaves
  `running` (stop, halt, fault, underrun). The stop, disable, and unload pin
  sets force CHG_PUMP low. A paused job is one of those states, so the chain
  de-energizes itself behind a pause without anyone asking it to. Measured at
  the pads: motion stops 317 ms after the pause command, and HV_ENABLE drops
  with the watchdog 550 ms after it (the feed ends with the run, then t~w~
  expires). A pause shorter than about half a second never drops HV at all.
  On the resume the pump primes with the run and HV_ENABLE is back within
  about 3 ms, while motion restarts at about 219 ms: the chain re-arms about
  216 ms **before** the first step, so a resumed cut never waits on it, and no
  dark dwell is warranted
  ([the grblHAL driver](grblhal-driver.md#faults)). The measurements are
  from the SoC pads, sampled at about 2 kHz across an operator-driven pause
  and resume.
- **FIRE backstop.** At end-of-data and on underrun the SDMA script drops FIRE
  and the step lines within one tick, then publishes end-of-data in a mailbox
  word the driver reads without a channel-0 transfer, so an end-of-data that
  arrives while a waypoint is still pending is decoded as what it is. The
  FIRE line is parked Hi-Z at every run end, and only a latch unlock plus a
  new run restores it.
- **Interlock latch drive.** The board's interlock latch is reset by a closed
  loop but can only be *set* by the SoC's INTERLOCK_RESET line; an open loop
  alone does not trip it. The driver owns that line through an in-kernel
  input handler on the gpio-keys switch device. The line is high (latch set,
  LASER_ON blocked) from probe until the switch device attaches, whenever the
  loop reads open, and again if the switch device goes away: an unobservable
  loop counts as open. Only an attached device that reports the loop closed
  releases it, and the set-dominant latch then clears through its own RESET.
  The policy is host-tested
  ([`tests/interlock_test.c`](https://github.com/openglow-org/kernel-module-glowforge/blob/master/tests/interlock_test.c)).
- **Dead man's switch.** A feeder holds `/dev/glowforge` open with
  `flock LOCK_EX`. If that fd closes while a program runs, the driver performs
  an emergency stop, puts the head in its safe state, and de-energizes the
  thermal-loop heat sources. The flock semantics are on
  [Pulse feeder contract](pulse-feeder-contract.md#the-device-devglowforge).
- **Panic handler.** On a kernel panic the driver stops the EPIT and drives
  the pins safe directly (FIRE Hi-Z, CHG_PUMP low, LATCH_RESET asserted,
  steppers de-energized), because SDMA and EPIT would otherwise keep playing
  the ring with no kernel alive.
- **Readbacks** (`interlock_circuit` bits 0 to 5, `laser_on[_sampled]`,
  `laser_pgood[_sampled]`, `button_latch`, `charge_pump_alive`,
  `interlock_latch_reset`) are monitoring only; the driver enforces nothing
  from them. Bits 1, 3, and 4 are driven outputs read back from the data
  register: bit 3 says what the driver *commanded*, `laser_on` says what the
  chain *did*.

The layers above the kernel (the controller's armed window, the machine
services daemon, cloud mode) are on
[grblHAL driver](grblhal-driver.md), [forgectrl](forgectrl.md), and
[Cloud mode](cloud-mode.md). The operator's view of the gates is on
[GRBL mode](../../usage/grbl-mode.md) and
[Cooling and fans](../../usage/cooling-and-fans.md).

## The sysfs and device tree

```
/sys/glowforge/cnc       <- Motion control, machine state
    |---button_latch:        (RO) Button-latch line state
    |---charge_pump_alive:   (RO) Charge-pump watchdog state
    |---disable:             (WO) Stop all motion and turn off stepper motors and laser
    |---enable:              (WO) Power on steppers and make ready for run
    |---faults:              (RO) Status of stepper axis faults
    |---free:                (RO) Free ring space in bytes (advisory; see the feeder contract)
    |---halt:                (WO) Immediately stop running program (no deceleration)
    |---ignored_faults:      (RW) Stepper axis faults to ignore
    |---interlock_circuit:   (RO) Safety-chain GPIO snapshot (bitmask)
    |---interlock_latch_reset: (RO) Interlock latch-reset line state
    |---laser_enable:        (RO) Laser-enable (FIRE) line state
    |---laser_latch:         (WO) Enable laser
    |---laser_on:            (RO) Gated LASER_ON output state
    |---laser_on_sampled:    (RO) LASER_ON low-sample count (last ~1s)
    |---laser_pgood:         (RO) Laser power-good state
    |---laser_pgood_sampled: (RO) LASER_PGOOD good-sample count (last ~1s)
    |---max_backtrack:       (RO) Longest backward run the ring can still play, in steps
    |---motor_lock:          (RW) Disable step output per motor
    |---position:            (RO) Current axis positions and loaded program size/progress
    |---ramp_rate:           (RW) Accel/decel rate in Hz/s
    |---resume:              (WO) Resume paused program
    |---run:                 (WO) Run loaded program
    |---sdma_context:        (RO) Value of SDMA registers
    |---state:               (RO) Current operating state
    |---step_freq:           (RW) Step frequency
    |---stop:                (WO) Controlled stop of running program (decelerate to idle)
    |---streaming:           (RW) Live-feed mode: end-of-data mid-run is an underrun, not completion
    |---underruns:           (RO) Streaming underruns since module load
    |---x_decay:             (RW) Enable/Disable X-Axis decay
    |---x_mode:              (RW) X-Axis Micro-stepping mode
    |---y_decay:             (RW) Enable/Disable Y-Axis decay
    |---y_mode:              (RW) Y-Axis Micro-stepping mode
    |---z_step:              (WO) Single step Z-Axis

/sys/glowforge/head      <- Laser head hardware
    |---accel_irq:           (RO) Head accelerometer IRQ tripped flag
    |---air_assist_pwm:      (RW) Air Assist fan PWM output setting
    |---air_assist_tach:     (RO) Air Assist fan tachometer reading
    |---beam_detect_analog:  (RO) Current state of beam detector - analog
    |---beam_detect_digital: (RO) Current state of beam detector - digital
    |---hall_sensor:         (RO) Status of lens hall sensor
    |---info:                (RO) Head identity: hardware id, serial, firmware version
    |---measure_laser:       (RW) Output PWM of material height measuring laser
    |---purge_air:           (RW) Purge Air fan on/off
    |---purge_air_current:   (RO) Purge Air fan current
    |---uv_led:              (RW) Output PWM of UV LED
    |---white_led:           (RW) Output PWM of White LED
    |---z_current:           (RW) High/Low Z-Axis current
    |---z_enable:            (RW) Z-Axis driver enable
    |---z_mode:              (RW) Z-Axis Micro-stepping mode

/sys/glowforge/pic       <- PIC analog/digital I/O
    |---button_led_1:        (RW) Output PWM of Button Red LED
    |---button_led_2:        (RW) Output PWM of Button Green LED
    |---button_led_3:        (RW) Output PWM of Button Blue LED
    |---grp_all:             (RO) All register values in binary format
    |---grp_button_leds:     (RW) All button LEDs, in binary format
    |---grp_hv:              (RO) All HV sensors, in binary format
    |---grp_outputs:         (RW) All outputs, in binary format
    |---grp_sensors:         (RO) All inputs, in binary format
    |---hex:                 (RW) Read/Write registers in ASCII Hex
    |---hv_current:          (RO) HV current measurement
    |---hv_voltage:          (RO) HV voltage measurement
    |---id:                  (RO) PIC Firmware ID
    |---lid_ir_1:            (RO) Lid IR sensor 1 measurement
    |---lid_ir_2:            (RO) Lid IR sensor 2 measurement
    |---lid_ir_3:            (RO) Lid IR sensor 3 measurement
    |---lid_ir_4:            (RO) Lid IR sensor 4 measurement
    |---lid_led:             (RW) Output PWM of Lid LEDs
    |---pwr_temp:            (RO) Power supply temperature
    |---raw:                 (RW) Read/Write binary data to/from registers
    |---tec_temp:            (RO) Thermo-Electric Cooler temperature
    |---water_temp_1:        (RO) Coolant temperature, downstream
    |---water_temp_2:        (RO) Coolant temperature, upstream
    |---x_step_current:      (RW) X-Axis stepper driver current
    |---y_step_current:      (RW) Y-Axis stepper driver current

/sys/glowforge/thermal   <- Cooling hardware
    |---exhaust_pwm:         (RW) Exhaust fan PWM output setting
    |---heater_pwm:          (RW) Coolant heater PWM output setting
    |---intake_pwm:          (RW) Intake fan PWM output setting
    |---tach_exhaust:        (RO) Exhaust fan tachometer reading
    |---tach_intake_1:       (RO) Intake fan 1 tachometer reading
    |---tach_intake_2:       (RO) Intake fan 2 tachometer reading
    |---tec_on:              (RW) Enable/Disable Thermo-electric cooler
    |---water_pump_on:       (RW) Enable/Disable water pump

/dev/glowforge:              (RW) Load/Clear program, reset positions

/sys/class/leds/button_led_X  <- Big Button LED interfaces
    |---pulse_off:           (RW) Off time in milliseconds
    |---pulse_on:            (RW) On time in milliseconds
    |---speed:               (RW) Speed to target brightness
    |---target:              (RW) Brightness set-point
    |---(standard LED interfaces not used)

/sys/class/leds/camera_mux_oe  <- Enable output for camera mux
    |---brightness:          (RW) Output level
    |---(standard LED interfaces not used)

/sys/class/leds/lid_led    <- Lid LED interface
    |---pulse_off:           (RW) Off time in milliseconds
    |---pulse_on:            (RW) On time in milliseconds
    |---speed:               (RW) Speed to target brightness
    |---target:              (RW) Brightness set-point
    |---(standard LED interfaces not used)
```

The switch inputs (lid, button, remote interlock, the HV_ENABLE readback, the
interlock latch, the head-attention line) are not module attributes. They are
`gpio-keys` switches on `/dev/input/event0`; the switch map is on
[forgectrl](forgectrl.md#switches-and-button).

## /sys/glowforge/cnc

The run-control attributes `free`, `halt`, `max_backtrack`, `resume`, `run`,
`stop`, `streaming`, and `underruns` are described on
[Pulse feeder contract](pulse-feeder-contract.md#run-control-attributes).

### button_latch

Read, ASCII, 0-1

State of the safety chain's button latch: 1 = set (emission blocked until the
operator presses the button with the lid closed and `laser_latch` unlocked),
0 = cleared (armed).

### charge_pump_alive

Read, ASCII, 0-1

Logical state of the charge-pump watchdog: 1 = the retriggerable one-shot fed
by the driver's charge-pump pulses is still within its period (the HV_ENABLE
path is alive), 0 = it has timed out. The line is active low on the board;
this attribute reports the logical state. Monitoring only.

### disable

Write, ASCII, 1

Writing "1" switches the device to the "disabled" state.

### enable

Write, ASCII, 1

Writing "1" switches the device to the "enabled" (idle) state. From
"disabled" this powers the steppers on. From "fault" this is the explicit
recovery lever: it clears the latched faults and returns to idle, but only
once every non-ignored fault line has physically cleared. A still-asserted
line refuses with EPERM.

The rail policy (who writes `enable` and `disable`, and why the 40 V rail
stays up while the machine is on) is on
[forgectrl](forgectrl.md#pulse-device-ownership).

### faults

Read, ASCII, 0-7

Indicates any faults that have been set by the stepper drivers.
Bits: 0: X Axis, 1: Y1 Axis, 2: Y2 Axis

### ignored_faults

Read/Write, ASCII, 0-7

Sets which stepper driver faults to ignore.
Bits: 0: X Axis, 1: Y1 Axis, 2: Y2 Axis

### interlock_circuit

Read, ASCII, 0-63

Raw snapshot of the laser-safety-chain GPIOs as a bitmask. Monitoring only;
enforcement is in the hardware AND-gate.

| Bit | Line | Note |
|---|---|---|
| 0 | LASER_ON | raw pin, active low |
| 1 | LASER_ENABLE | driven output (FIRE) |
| 2 | BUTTON_LATCH | |
| 3 | LASER_LATCH | driven output; the driver's commanded lock state |
| 4 | INTERLOCK_LATCH_RESET | driven output |
| 5 | CHARGE_PUMP_ALIVE | raw pin, 0 = alive |

Bits 1, 3, and 4 are driven outputs: mainline gpio-mxc reads output lines
back from the data register, so those bits report the value the SoC last
drove, not a sense of the pad. Bit 3 is therefore the authoritative view of
what the driver commanded the latch to do (`laser_latch` is write-only) and
not evidence that the latch hardware responded. The physical proof is
`laser_on` and `laser_on_sampled`, which read the gated output of the safety
AND-gate. forgectrl's `/status` reports bit 3 as `laser_locked`.

### Debug surface

Eleven attributes have no consumer in ForgeFIRM and no acceptance test:
`cnc/interlock_latch_reset` (the same line as bit 4 of `interlock_circuit`),
`head/accel_irq`, and the PIC `id`, `hv_voltage`, `grp_all`, `grp_sensors`,
`grp_hv`, `grp_outputs`, `grp_button_leds`, `raw` and `hex`. They are a
debug surface for the bench; the `raw` and `hex` writers reach every PIC
register, as root.

### interlock_latch_reset

Read, ASCII, 0-1

State of the interlock latch-reset line, the SoC's SET input to the safety
chain's interlock latch (read back from the data register, that is, the
value last driven). The driver owns this line: it is 1 (latch set, LASER_ON
blocked in hardware) whenever the remote-interlock loop reads open, and also
from probe until a switch device reporting the loop has attached. An
unobservable loop is treated as open. It is 0 only while an attached switch
device reports the loop closed. The loop state comes from the gpio-keys
switch device (EV_SW code 5, `interlock`, active = open) through an
in-kernel input handler, so no userspace round trip is involved and the GPIO
stays owned by gpio-keys. Because the interlock latch is set-dominant, it
stays set until this line is released *and* the loop is closed. The latch's
own state is the `interlock_latch` switch (EV_SW code 6).

The line is not writable from userspace.

### laser_enable

Read, ASCII, 0-1

State of the laser-enable (FIRE) drive line.

### laser_latch

Write, ASCII, 0-1

Laser lockout latch. 1 = LOCK: the LASER_ON drive line is put in high
impedance (the SDMA stream cannot enable the laser). 0 = UNLOCK: the line is
restored as a driven output under SDMA control. Lock it whenever no print is
in progress; the driver locks it automatically when `/dev/glowforge` is
closed.

### laser_on

Read, ASCII, 0-1

Logical state of the gated LASER_ON output of the hardware safety AND-gate
(the line is active low; 1 = laser on).

### laser_on_sampled

Read, ASCII, 0-255

Number of samples in the last ~1 second window (255 samples, one every
~3.9 ms) in which the LASER_ON line read low. Updated once per window.

### laser_pgood

Read, ASCII, 0-1

Logical state of the laser supply's power-good line (active high; 1 = the
supply reports its outputs within spec). The supply drives the line high the
whole time it is healthy: it does not follow HV_ENABLE or emission, and it
reads 1 at idle, through an HV enable, and through a cut. It is a supply-fault
witness, not an emission witness.

### laser_pgood_sampled

Read, ASCII, 0-255

Number of samples in the last ~1 second window (255 samples) in which the
LASER_PGOOD line read good (high). 255 on a healthy supply. Updated once per
window.

### motor_lock

Read/Write, ASCII, 0-15

Sets axis lock. If the axis bit is set, that axis does not move when running
a program. This does not prevent the Z axis from moving when commanded by
`z_step`.
Bits: 0: X Axis, 1: Y1 Axis, 2: Y2 Axis, 3: Z Axis

The factory's idle posture is 8 (the lens locked out of the pulse path), and
both ForgeFIRM controllers take that posture at their start. A program that
moves the lens needs the bit clear for its run: the cloud client clears it for
every motion and puts it back after, and a setup card that steps the
lens clears it for its session. A print streamed with the bit set burns every
line at one height and counts the Z steps it never made.

### position

Read, Binary, 32 bytes (little-endian)

Current axis position and program size and position.

| Bytes | Value |
|---|---|
| 00-03 | X position in steps |
| 04-07 | Y position in steps |
| 08-11 | Z position in steps |
| 12-15 | Program bytes processed (a 32-bit SDMA counter: wraps modulo 4 GiB under a long live stream) |
| 16-19 | Program size in bytes (a 64-bit host tally, saturates at 4 GiB under a long live stream) |
| 20-31 | Reserved |

Under a live feed the two byte counters diverge past 4 GiB (one wraps, one
saturates). A controller that compares them for progress must track the wrap
itself, or use its own count of bytes written.

Position counters are not proof of physical motion: the step-stream drives
are open loop. The head accelerometer is the motion witness
([The accelerometer path](#the-accelerometer-path)).

### ramp_rate

Read/Write, ASCII, 10000-500000

Controlled acceleration/deceleration rate in Hz/s: how fast the step
frequency is ramped up or down during a controlled accel/decel (for example
`stop`, `resume`). Default is 125,000. Independent of `step_freq`; the rate
is constant rather than scaling with the target speed. Cannot be changed
while a program is running (returns -EBUSY).

### sdma_context

Read, ASCII, (formatted)

Dumps internal registers and status of the CNC SDMA context.

### state

Read, ASCII, CNC State

The current CNC state:

| State | Meaning |
|---|---|
| `idle` | Steppers are on but no program is in progress |
| `running` | A program is in progress |
| `disabled` | Steppers are disabled, no program in progress |
| `fault` | Stepper driver fault. Recoverable via `enable` once every non-ignored fault line has physically cleared |
| `underrun` | A streaming feeder (see `streaming`) let the pulse buffer run dry mid-run. The stop is instantaneous (no deceleration), so steps may have been skipped at speed and the reported position can no longer be trusted. New runs are refused until the underrun is acknowledged by writing "1" to `stop`; the feeder should treat this as an alarm and re-home before continuing |

### step_freq

Read/Write, ASCII, 1000-200000

Step frequency in Hz. Default is 10,000. Immutable while running (-EBUSY);
see [Pulse feeder contract](pulse-feeder-contract.md#fixed-byte-density).

### x_decay

Read/Write, ASCII, 0-2

Sets the current decay mode for the X axis.
0: Slow (fast stop, slow response)
1: Mixed (decay pin Hi-Z)
2: Fast (fast response, slow stop)

### x_mode

Read/Write, ASCII, [1, 2, 4, 8, 16, 32]

Microstepping mode for the X axis. 1 = full steps.

### y_decay

Read/Write, ASCII, 0-2

Sets the current decay mode for the Y axis.
0: Slow (fast stop, slow response)
1: Mixed (decay pin Hi-Z)
2: Fast (fast response, slow stop)

### y_mode

Read/Write, ASCII, [1, 2, 4, 8, 16, 32]

Microstepping mode for the Y axis. 1 = full steps.

### z_step

Write, ASCII, 0-1

Moves the Z axis one step in the requested direction (direct GPIO pulse, not
via the pulse stream).
0: Negative, toward the bed
1: Positive, away from the bed

## /sys/glowforge/head

### accel_irq

Read, ASCII, 0-1

Indicates if the head accelerometer set its IRQ.

### air_assist_pwm

Read/Write, ASCII, 0-1023

Air assist fan PWM period. 0: Off, 1023: Full speed. The factory firmware
never sets this below 204, so the fan is never off.

### air_assist_tach

Read, ASCII, 64-bit

Period between tach pulses, in nanoseconds (0 when no pulse has arrived).
The RPM conversion is on
[Sensors](../machine/sensors.md).

### beam_detect_analog

Read, ASCII, 0-65535

Analog output from the beam detector. How it operates is not characterized.
forgectrl uses it as the live emission witness and the dose-curve recorder
samples it ([forgectrl](forgectrl.md#the-dose-curve-recorder)).

### beam_detect_digital

Read, ASCII, 0-1

Digital output from the beam detector. How it operates is not characterized.

### hall_sensor

Read, ASCII, 0-1

Output from the lens position sensor.
0: Not at home position
1: At home position

Home reads 1 from an edge partway up the lens's travel to the top stop. Where
that edge sits differs from head to head, and it is the one per-head number
for Z. The Glowforge service's "hunt" program steps the lens 4 full steps down
from the edge; that point is its zero, and its prints count full steps up from
there. The lens, its travel, and how the edge is referenced are on
[The motion hardware](../machine/motion-hardware.md#the-lens-and-its-travel).

### measure_laser

Read/Write, ASCII, 0-1023

Measurement laser PWM. 0: Off, >0: On. Any value above 0 turns the head
measurement laser on.

### purge_air

Read/Write, ASCII, 0-1

Turns the purge air fan on or off. 0: off, 1: on. This fan purges smoke from
the lens cavity.

### purge_air_current

Read, ASCII, 0-1023

The current being drawn by the purge fan. The meaning of the values is not
characterized. Observed values are 1 when off and 628 when on.

### uv_led

Read/Write, ASCII, 0-1023

Head UV illumination LED PWM. 0 = Off, 1023 = 100 %.

### white_led

Read/Write, ASCII, 0-1023

Head white illumination LED PWM. 0 = Off, 1023 = 100 %.

### z_current

Read/Write, ASCII, 0-1

Z stepper drive current. 0: high, 1: low. The lens rises only at the high
current; the low current is a hold current, at which the motor stalls two
steps into a move up at the service's rate. Set 0 before a Z move and 1
after.

### z_enable

Read/Write, ASCII, 0-1

Enable or disable the Z driver. 0: enabled, 1: disabled.

### z_mode

Read/Write, ASCII, 0-1

Z axis microstepping. 0: Full, 1: 2 (half-step). The service's pulse headers
carry `ZSmd` 0, so its Z steps are full steps; ForgeFIRM's own lens moves use
half-steps, about 0.34 mm each.

## /sys/glowforge/pic

The PIC (a PIC16F1713) converts its analog inputs in a free-running loop,
about 25 µs a channel, and a read returns the last conversion of that
channel, at most one loop (about 0.35 ms) old; a read never triggers a
conversion. What a conversion counts depends on the SoC's load at that
moment: the PIC converts against its own supply while the sensor dividers
hang on the board's reference, and the CPU's idle-to-busy step moves the
count by about 6 on the coolant thermistors (both regimes tight). A reader
that wakes and reads at once gets an idle-regime value; one that has been
busy gets the other. So the module keeps the CPU busy for `pic_settle_us`
microseconds (a module parameter, 500 by default, writable at runtime under
`/sys/module/glowforge/parameters/`) before every transaction, longer than
one PIC loop, and the value read was converted under the same load whoever
the reader is and whatever it was doing: the cooling engine, `/status`, a
diagnostic and a bench sampler read the same value. Zero turns it off.

### button_led_1, button_led_2, button_led_3

Read/Write, ASCII, 0-1023 (0 = OFF, 1023 = FULL)

Red (1), Green (2), and Blue (3) LEDs in the big button. These are not
intended to be set directly. Set them through the
`/sys/class/leds/button_led_X` interface instead ([LEDs](#leds)).

### grp_X

Read/Write, Binary, varies

Used to read and write data in groups. From `pic.h`:

> Register groups. These allow reading or updating multiple registers at
> once. Input/output is a sequence of 16-bit binary little-endian values.
> When writing to a register group file, the number of bytes written must
> exactly match the number of registers in the group times 2. (because each
> register is 2 bytes in size.)

### hex

Read/Write, ASCII, varies

For reading and writing multiple registers. From `pic.h`:

> To write a set of registers:
> `echo 18=0123,19=4567,1a=89ab,1b=cdef > /sys/glowforge/pic/hex`
> The string must be a comma-separated list of register=value pairs.
> To read a set of registers:
> `echo 18,19,1a,1b > /sys/glowforge/pic/hex && cat /sys/glowforge/pic/hex`
> The string must be a comma-separated list of register numbers.
> Reading from this file returns the register values transmitted by the PIC
> during the previous write transaction. The string is a comma-separated
> list of register values, each exactly 4 hex characters long.

### hv_current

Read, ASCII, 0-1023

HV current. The exact meaning of this value is not characterized. It is the
only live HV telemetry; the cooling engine ranges it per job and uses it in
the flow check's tube-share compensation
([Cooling engine](cooling-engine.md#coolant-flow-verification)).

### hv_voltage

Read, ASCII, 0-1023

HV voltage. Every power supply examined ties the input of this A/D to
ground.

### id

Read, ASCII, 19795

Firmware ID of the PIC analog/digital I/O.

### lid_ir_1, lid_ir_2, lid_ir_3, lid_ir_4

Read, ASCII, 0-1023

Output of the four IR sensors on the lid. The cooling engine's fire watch
reads them ([Cooling engine](cooling-engine.md#the-fire-watch)).

### lid_led

Read/Write, ASCII, 0-1023 (0 = OFF, 1023 = FULL)

Lid LEDs. Not intended to be set directly. Set it through the
`/sys/class/leds/lid_led` interface instead ([LEDs](#leds)).

### pwr_temp

Read, ASCII, 0-1023

Power supply temperature, as a raw count. The conversion is a best guess
and unverified; the value is published as a raw count. See
[Sensors](../machine/sensors.md).

### raw

Read/Write, Binary, varies

For reading and writing binary values to the PIC. From `pic.h`:

> Write to this file to send a chunk of raw binary data to the PIC. The
> number of bytes written must be a multiple of 3.
> Read from this file to obtain the binary data transmitted by the PIC
> during the previous write transaction.

### tec_temp

Read, ASCII, 0-1023

Thermoelectric cooler temperature, Pro machines only. The conversion is not
characterized, and on a machine with no TEC fitted the reading rails; see
[Sensors](../machine/sensors.md#power-supply-and-tec-temperatures-picpwr_temp-pictec_temp).

### water_temp_1

Read, ASCII, 0-1023

Water temperature, downstream of the heater. The conversion (the factory
beta-equation NTC formula, with reference points) is on
[Sensors](../machine/sensors.md).

### water_temp_2

Read, ASCII, 0-1023

Water temperature, upstream of the heater. Same conversion.

### x_step_current

Read/Write, ASCII, 0-1023 (a 10-bit DAC value; the module refuses more)

X stepper drive current. 0 = minimum. The factory runs 135, 33 at hold.

### y_step_current

Read/Write, ASCII, 0-1023 (a 10-bit DAC value; the module refuses more)

Y stepper drive current. 0 = minimum; the Y DAC scale differs from X by
design. The factory runs 22, 5 at hold.

## /sys/glowforge/thermal

The cooling engine in forgectrl is the only writer of this group
([Cooling engine](cooling-engine.md)).

### exhaust_pwm

Read/Write, ASCII, 0-65535

Exhaust fan PWM period. 0: Off, 65535: Full speed.

### heater_pwm

Read/Write, ASCII, 0-65535

Water heater PWM period. 0: Off, 65535: Full power. The heater sits in the
coolant loop between the two water temperature sensors, so heat it puts in
shows up as a difference between them. The cooling engine uses it for flow
verification.

### intake_pwm

Read/Write, ASCII, 0-65535

Intake fans PWM period. 0: Off, 65535: Full power. This controls the output
for both intake fans.

### tach_exhaust

Read, ASCII, 0-65535

Period between exhaust fan tach pulses, in nanoseconds. The RPM conversion
is on [Sensors](../machine/sensors.md).

### tach_intake_1

Read, ASCII, 0-65535

Period between intake fan 1 tach pulses, in nanoseconds.

### tach_intake_2

Read, ASCII, 0-65535

Period between intake fan 2 tach pulses, in nanoseconds.

### tec_on

Read/Write, ASCII, 0-1

Turns the thermoelectric cooler on or off. 0: off, 1: on. Pro machines
only. Basic and Plus have no TEC fitted, and writing here does nothing on
those. The output has no readback.

### water_pump_on

Read/Write, ASCII, 0-1

Turns the water pump on or off. 0: off, 1: on.

## LEDs

### /sys/class/leds/button_led_X, /sys/class/leds/lid_led_X

Interface to control the button LEDs and the lid LEDs. From
`ledtrig_smooth`:

> target: (range: [0, 255]) The new brightness set-point. The LED fades
> from its current value to the target value. May be changed while the LED
> is already fading.
> speed: (range: [1, 160]) The speed at which the LED seeks its target
> brightness. The default is 64.
> pulse_on: (milliseconds)
> pulse_off: (milliseconds)
> When both values are > 0, the LED's target will alternate between minimum
> and maximum brightness automatically.
> The delay between target=255 and target=0 is specified by pulse_on.
> The delay between target=0 and target=255 is specified by pulse_off.
> Both values are internally truncated to multiples of MSECS_PER_UPDATE.

### /sys/class/leds/camera_mux_oe

This controls the output enable of the camera multiplexer. Set `brightness`
to 255. A value of 0 shuts the output off. There is no reason to ever shut
the output off.

## The accelerometer path

The head carries an ST LIS2HH12 accelerometer on I²C. It binds to the
mainline `st_accel` IIO driver, not to `glowforge.ko`; the module exposes
only its IRQ flag as `head/accel_irq`. forgectrl reads it in two ways: the
motion-liveness probe reads the part through `st_accel` in unarmed sessions
to prove that a commanded move physically happened
([forgectrl](forgectrl.md#mode-supervision)), and the crash watch arms the
part's two on-chip interrupt generators over i2c-dev while `st_accel` stays
bound ([Cooling engine](cooling-engine.md#the-fire-watch)). Position
counters are never accepted as proof of motion; the accelerometer is.
