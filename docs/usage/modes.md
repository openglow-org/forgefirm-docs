---
title: Modes
---

# Modes

ForgeFIRM runs the machine in one of two controller modes: GRBL mode or cloud
mode. This page tells you what each mode is for, what each needs, and how to
switch between them.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## Two controllers, one at a time

Exactly one controller runs at a time. The machine-services daemon,
`forgectrl`, starts the one that the `controller_mode` setting selects, and
switching is a live operation from the panel's Status tab.

=== "GRBL mode"

    GRBL mode turns the machine into a standard Grbl-speaking laser cutter. It
    is the default, and the one to use for your own designs. grblHAL runs on
    the machine and speaks Grbl 1.1 over TCP port 23, so LightBurn, UGS, cncjs,
    and any other Grbl sender drive the laser directly. Motion runs on the
    board's own hardware step engine, fed live by the local planner.

    It needs: a sender on your network, and nothing else. The one GRBL-mode
    function that reaches the Glowforge service is camera-referenced homing
    (`$H`), which needs a Glowforge account and a live service session
    ([Homing](homing.md)). Everything else in GRBL mode runs without them.

    See [GRBL mode](grbl-mode.md) and [LightBurn](lightburn.md).

=== "Cloud mode"

    Cloud mode runs the factory experience: the machine signs in to the
    Glowforge web service as itself, names its software as ForgeFIRM, and uses
    the service the way a stock machine does, so the phone and web apps
    work as they do on factory firmware: the camera bed image, the lens hunt,
    "push the button to print". It is optional, off by default, and kept and
    maintained on purpose.

    It needs: internet access, a Glowforge account, and the machine's cloud
    identity (the identity in the factory fuses, by default). The cameras only
    capture with the lid closed, so the lid must be shut before the app
    focuses or prints ([Cameras](cameras.md)).

    See [Cloud mode](cloud-mode.md).

## Which mode to use

- You design in LightBurn or another G-code tool, and you want the machine to
  work without the internet: **GRBL mode**.
- You want the Glowforge app, its material catalog, and its camera placement:
  **cloud mode**.
- You want the laser armed by your own button press for each job: both modes
  do this. The button press is part of every job in either mode
  ([GRBL mode](grbl-mode.md#arming-the-button-press-is-part-of-every-job)).
- Job length: GRBL mode has no limit. In cloud mode the ring buffer holds
  about 56 minutes of a job at once, and the client tops it up as the job
  plays.

[ForgeFIRM, the software](../technical/forgefirm/index.md) holds the full
side-by-side comparison of the two modes.

## Switching modes

Switch from the panel's Status tab, with the controller-mode selector. The
Factory cloud choice exists only once the setup's cloud step turned cloud
mode on (`cloud_enabled=1`, [Commissioning](commissioning.md#cloud-mode)).
The switch is allowed only when the machine is idle and no diagnostic is
running.
It stops the active controller, persists `controller_mode`, starts the other
controller, and waits for that controller's first job-state report to reach the
cooling engine. The setting persists across reboots: the machine boots into the
mode you last selected.

Switching never closes the pulse device and never cycles the 40 V motor rail.
`forgectrl` holds the device for its lifetime and the controllers inherit it.

**Coordinates do not survive a switch.** Connecting to the Glowforge service
zeroes the machine's counters at the head's current position, so GRBL-mode
coordinates are gone after a switch to cloud mode and back. Re-home after
switching ([Homing](homing.md)).

The route behind the selector is `POST /mode?controller=grbl|cloud`, and
`GET /mode` reports the supervisor state: the mode, the controller state
(`running`, `stopped`, `standby`, or `motion-fault`), the controller's pid, and
the motion-liveness verdict (`verified`, `unverified`, or `fault`)
([The control panel](control-panel.md)).

## What the supervisor does for you

- **A crashed controller is restarted.** The supervisor safes the machine
  first (motion stopped, laser latch locked), then respawns the controller.
- **Motion is proven before the first start of a session.** Before the first
  controller start, the machine makes a short test move and confirms it with
  the accelerometer in the print head. If the stepper drivers do not wake, the
  controller stays down, `GET /mode` reports `motion-fault`, and the panel
  offers a retry ([Troubleshooting](troubleshooting.md)).
- **A busy controller survives a daemon restart.** If `forgectrl` itself
  stops while a job runs, the controller is left running rather than
  stopped mid-job; the returning daemon retakes supervision once the machine
  is idle.
- **The manual emergency lever.** `POST /controller/stop` halts the active
  controller at once (it is not idle-gated) and holds supervision suspended;
  `POST /controller/start` resumes supervision of the selected mode. The
  controller init scripts route here.

The mechanism, the pulse-device broker, and the safing rules are in
[forgectrl](../technical/forgefirm/forgectrl.md).
