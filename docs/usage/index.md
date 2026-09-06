---
title: Usage
---

# Usage

This section tells you how to operate a Glowforge that runs ForgeFIRM: the
first boot, the web control panel, the two controller modes, and the machine
functions you use from day to day.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## The first boot

The installer reboots the machine into ForgeFIRM at the end of the install
([Install](../install/install.md)). The factory `/data` partition, with its
settings, credentials, and logs, is untouched, and the factory firmware is
kept in an archive on `/data`
([Back to the factory firmware](../install/factory-restore.md)).
A machine that came from the legacy dual-partition installer reclaims that
partition on its first ForgeFIRM boot
([Upgrading from a legacy install](../install/legacy-migration.md)).

The first visit to the control panel runs the setup: the advisories, your
account, the preferences, the machine facts, and the cloud decision
([Commissioning](commissioning.md)). Until the setup is complete, no
controller runs for a sender.

At boot the machine-services daemon, `forgectrl`, starts. It starts the one
controller that the `controller_mode` setting selects: the GRBL controller
(the default) or the cloud client ([Modes](modes.md)). Before the first
controller start of a session the machine makes a short test move and confirms
it with the accelerometer in the print head. If it sees no motion it reports a
motion fault instead of starting a controller, and the panel offers a retry
([Troubleshooting](troubleshooting.md)).

## Finding the machine on the network

The machine answers to `forgefirm.local` over mDNS, and to its fuse
hostname as `<name>.local`. Its network address is shown in this
documentation as `<machine-ip>`. The serial console prints the addresses.

| Address | Service |
|---|---|
| `https://forgefirm.local/` or `https://<machine-ip>/` | The web control panel, with the HTTP routes behind it |
| `http://<machine-ip>/` | The read-only routes over plain HTTP: status, settings, the cameras ([The control panel](control-panel.md#access)) |
| `<machine-ip>:23` | The Grbl 1.1 protocol, in GRBL mode ([GRBL mode](grbl-mode.md)) |

The panel's header names the machine by its factory identity: the factory
hostname, derived from the serial number burned into the board's fuses. That
name does not change when you set a cloud identity override.

## The control panel in brief

The panel is one self-contained page with a light and a dark theme. It has
seven tabs:

- **Status**: the controller-mode selector, live operational status (motion
  state and position, coolant temperatures and fan tachometers, safety-switch
  states, system summary), and the lid-camera view.
- **Machine**: shared settings: display units, the homing method and the
  post-homing position calibration, and the cooling tunables.
- **GF Cloud**: the Glowforge web-service overrides: machine identity and the
  homing-session timeout.
- **GRBL**: the controller connection information and the GRBL-mode tunables:
  the laser arm window, the laser dose, and the motor-rail settle time.
- **Diagnostics**: tools that take the hardware over: cooling system
  verification and calibration.
- **Logs**: log levels, the remote syslog target, a live log viewer, and the
  log export.
- **System**: firmware slots, ForgeFIRM updates, image install and restore,
  the WiFi regulatory region, remote access (SSH), the commissioning card,
  and reboot.

[The control panel](control-panel.md) describes each tab.

## Where to go next

| Page | What it covers |
|---|---|
| [The control panel](control-panel.md) | The address, the login, every tab, and the HTTP routes an operator uses. |
| [Commissioning](commissioning.md) | The first run: the advisories, your account, the machine facts, the gate, and the way back. |
| [Modes](modes.md) | GRBL mode against cloud mode, and how to switch. |
| [GRBL mode](grbl-mode.md) | Connecting a sender, arming the laser, pausing, stopping, faults. |
| [LightBurn](lightburn.md) | Device setup, job start mode, a good first job. |
| [Cloud mode](cloud-mode.md) | The factory experience through the Glowforge app. |
| [Homing](homing.md) | Camera-referenced homing, and running unhomed. |
| [Cameras](cameras.md) | The lid-closed rule, watching the stream, what you get. |
| [Cooling and fans](cooling-and-fans.md) | The gates as settings, and what the machine does when. |
| [Settings](settings.md) | The machine-settings reference. |
| [Logging](logging.md) | The Logs tab, the export, remote syslog. |
| [Diagnostics](diagnostics.md) | The hardware tests and when to run them. |
| [Troubleshooting](troubleshooting.md) | What to do when something looks wrong. |
