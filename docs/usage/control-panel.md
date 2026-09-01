---
title: The control panel
---

# The control panel

The web control panel is the machine's local user interface, served by the
machine-services daemon `forgectrl` on HTTP port 8080. This page describes its
tabs and the HTTP routes an operator uses.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## The page

Open `http://<machine-ip>:8080/`. The panel is a self-contained single page
(no external assets) on Bootstrap, carrying the OpenGlow visual identity in a
light and a dark theme (the header toggle: light, dark, or the system
preference). Every settings field on every tab shares one save bar: it appears
while anything is unsaved, posts every change in one request, and leaving a tab
or the page with unsaved changes asks first. Each card and field has a "?" that
opens its help, with a link into this documentation site.

All settings controls disable, with a banner, while the machine is not idle or
while a diagnostic is running. The header identifies the machine by its factory
identity (the factory hostname derived from the serial in the fuses), whatever
cloud identity override is set.

**Units** are a display-only preference (`ui_units`): the machine stores and
exchanges metric values, and the panel converts at its edge.

## The tabs

### Status

The live controller-mode selector (it switches through the supervisor, and the
setting persists for boot; see [Modes](modes.md)), live operational status
(motion state and position, coolant temperatures and fan tachometers,
safety-switch states, system summary), plus a scaled lid-camera snapshot that
switches to the live stream on demand ([Cameras](cameras.md)).

Position always shows. It is painted red while the machine is unreferenced and
shown normally once a homing cycle anchors it ([Homing](homing.md)). The laser
latch row is labeled *commanded*, with the sensed emission row beside it: the
latch is the commanded state of the kernel lock, and the emission line is what
the beam sensor sees. The switch card shows the safety-chain readbacks; HV
enable is the readback of the chain's HV_ENABLE output, on only while a run
feeds the charge-pump watchdog with the lid closed
([The safing chain](../technical/machine/safing-chain.md)).

The Status tab shows a standing banner while any cooling gate is turned off
([Cooling and fans](cooling-and-fans.md)), and a compatibility warning when the
Glowforge service has moved past the firmware version cloud mode is tested
against ([Cloud mode](cloud-mode.md)).

### Machine

Shared settings: display units, the homing method and the post-homing position
calibration, and the cooling tunables. The cooling cards are the coolant loop,
flow verification, and the airflow gates ([Cooling and fans](cooling-and-fans.md)).

### GF Cloud

Glowforge web-service overrides: machine identity (serial and password; blank
means the factory fuse identity), the homing-session timeout, the print-pause
counts, and the job-size guards ([Cloud mode](cloud-mode.md)).

### GRBL

Controller connection information and the GRBL-mode tunables the controller
reads from the shared settings: the laser arm window (button wait, disarm
grace), the laser dose and the dose-curve recorder, the lid and interlock
policy, the motor-rail settle time, and the lid lamp
([GRBL mode](grbl-mode.md), [Settings](settings.md)).

### Diagnostics

Tools that take the hardware over (the active controller is suspended through
the supervisor for the duration): cooling system verification and calibration
([Diagnostics](diagnostics.md)).

### Logs

Per-logger disk and remote log levels (applied at the next reboot), the remote
syslog target, a live log viewer, and the log export (sanitized by default) for
issue reports ([Logging](logging.md)).

### System

Firmware slots (A/B boot selection), ForgeFIRM updates, image install and
restore, the WiFi regulatory region (power save is kept off), and reboot.
[Updating](../install/updating.md),
[Back to the factory firmware](../install/factory-restore.md), and
[Recovery](../install/recovery.md) describe the update and restore tools.

The WiFi region (`wifi_country`) sets the radio's allowed channels and
transmit power. Automatic follows the country the access point advertises,
else the world rules; a selected country pins it. The setting applies
immediately and at every boot.

The design intent: every machine tunable, shared, cloud-override, and
GRBL-mode, has a home in one of these tabs.

## The routes an operator uses

| Endpoint | Purpose |
|---|---|
| `GET /status` | Machine operational status as JSON (state, position when homed, fans, coolant, switches, `gates_off`, the `grbl` state block while a GRBL controller runs, the `diag` flag) |
| `GET /settings` | Current settings as JSON (plus the system hostname, firmware version, and the `gates` table: range, recommended band, off end and state per gate setting) |
| `POST /settings?key=value&...` | Set any subset of known keys ([Settings](settings.md)) |
| `GET /mode` | Supervisor state: mode, controller (`running`, `stopped`, `standby`, `motion-fault`), pid, motion verdict |
| `POST /mode?controller=grbl\|cloud` | Live idle-gated mode switch; also the retry lever after a motion fault |
| `POST /controller/stop`, `POST /controller/start` | The manual emergency lever: stop halts the active controller and holds supervision suspended; start resumes it ([Modes](modes.md)) |
| `GET /cool/status` | Cooling-engine state: phase, verdict, temps, report age, `gates_off`, the effective `limits`, `fan_gates` |
| `GET /grbl/settings` | The GRBL controller's `$$` view, while a GRBL controller runs |

`POST /cool/state` is the active controller's job-state report to the cooling
engine, not an operator route; it accepts loopback connections only.

Position in `/status` comes from the kernel step counters anchored at the last
completed homing. The Grbl TCP socket is never queried, because a connection
there would displace the sender's session.

Other route families have their own pages: the camera routes
([Cameras](cameras.md)), the log routes ([Logging](logging.md)), the
diagnostics routes ([Diagnostics](diagnostics.md)), and the update and slot
routes ([Updating](../install/updating.md)).

### Access

Every route that changes machine state needs the panel token. The panel page
carries the token, so the browser needs nothing more. A script of your own
reads it from `/data/forgefirm/panel.token` on the machine and sends it as a
bearer token. State-changing requests must also address the machine by its
address literal, and a browser request must not be cross-site; that is what
stops a hostile page in another tab from reaching your machine. It is not
protection against other people on your network.

Two things need the physical button held as well as the token: reading the
fuse identity (`GET /fuse-identity`, which returns the serial, the derived
hostname, and the password) and installing an unsigned firmware image.
