---
title: The control panel
---

# The control panel

The web control panel is the machine's local user interface, served by the
machine-services daemon `forgectrl` over HTTPS. This page describes its
address, the login, its tabs, and the HTTP routes an operator uses.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## The address

Open `https://<ip>/`. The serial console prints the addresses at its login
banner, and your router lists the machine by the name it sends with its
DHCP request: `forgefirm-<xxxx>`, where `xxxx` is the last four hex digits
of its WiFi MAC address.

A network that publishes DHCP names in its own DNS also answers
`https://forgefirm-<xxxx>/`. Use the bare name. The panel refuses a name
that carries your network's domain, because a name with a domain on it can
be registered by anyone, and refusing it is what stops a DNS-rebinding
attack ([Access](#access)).

The panel is served over HTTPS with a certificate the machine makes at its
first start. The browser warns once; accept the warning. The certificate's
SHA-256 fingerprint is on the System tab's Setup card. Compare it
with what the browser shows. To check
it before you accept the warning, open `http://<ip>/cert` (plain HTTP, no
login, no redirect): the page shows the fingerprint, the names on the
certificate, and its validity, and offers the certificate itself at
`http://<ip>/cert.pem` for a browser or a device that should trust it. The
certificate lives under the machine's data directory and survives
updates.

Plain HTTP on port 80 serves only the read-only routes, for LightBurn's
camera and other readers ([Access](#access)).

## Login

The first run of the panel creates one account, a name and a password
([Setup](setup.md)). After that the panel asks for a login.
The session is a cookie, sent over HTTPS only, and it expires after 12
hours idle. Five wrong attempts from one address lock the login for 30 s.
The **Sign out** button in the header ends the session. The same name and
password open SSH ([System](#system)).

Forgot the password? Hold the machine's button while you turn the machine
on, for ten seconds, until the button blinks amber. The setup then asks for
a new account ([Setup](setup.md#a-forgotten-password)).

## The page

The panel is a self-contained single page
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
against ([Cloud mode](cloud-mode.md)). While the setup gate holds
the machine, the tab shows a banner with a link to continue the setup
([Setup](setup.md#the-gate)). While the motion check waits
for the lid or the interlock to close, the tab shows a banner that says so,
and the button blinks amber ([Modes](modes.md#what-the-supervisor-does-for-you)).

### Machine

Shared settings: display units, the homing method and the post-homing position
calibration, the lens, the stepper drive (the X and Y microstep mode,
[Settings](settings.md#settings-that-affect-motion)), and the cooling
tunables. The cooling cards are the coolant loop, flow verification, and the
airflow gates ([Cooling and fans](cooling-and-fans.md)).

### GF Cloud

The tab exists only while cloud mode is turned on (`cloud_enabled`,
[Setup](setup.md#cloud-mode)). Glowforge web-service
overrides: machine identity (serial and password; blank
means the factory fuse identity), the homing-session timeout, the print-pause
counts, and the job-size guards ([Cloud mode](cloud-mode.md)).

### GRBL

Controller connection information and the GRBL-mode tunables the controller
reads from the shared settings: the laser arm window (button wait, disarm
grace), the laser dose and the dose-curve recorder, the lid and interlock
policy, the motor-rail settle time, and the lid lamp
([GRBL mode](grbl-mode.md), [Settings](settings.md)).

### Setup

The checks the setup ran, with the version each completed at and what the
machine asks for again (required or recommended, with the reason), and a
link to the setup to run one again ([Setup](setup.md)). The
**What changed?** menu names a replaced part or a service, and the checks
that depend on it are asked for again
([What changed](setup.md#what-changed)). Below them, the cooling
tools that take the hardware over (the active controller is suspended
through the supervisor for the duration): verification and calibration
([Diagnostics](diagnostics.md)).

### Logs

Per-logger disk and remote log levels (applied at the next reboot), the remote
syslog target, a live log viewer, and the log export (sanitized by default) for
issue reports ([Logging](logging.md)).

### System

Firmware slots (A/B boot selection), ForgeFIRM updates, image install and
restore, the WiFi regulatory region (power save is kept off), and reboot.
A newer ForgeFIRM release shows an alert above every tab, with the release
dialog behind it. [Updating](../install/updating.md),
[Back to the factory firmware](../install/factory-restore.md), and
[Recovery](../install/recovery.md) describe the update and restore tools.

Two more cards. **Remote access** turns SSH on until the next reboot: SSH
is off at every boot, and a development image keeps it on. It opens with
the panel account's name and password; root has no password and works at
the serial console only. The machine's SSH host keys are made at the first
start and kept on `/data`, so its fingerprint stays the same across
updates. **Setup** shows the state of the setup and
the certificate fingerprint, with a link to run a step again, the printable
summary of the record, and the record itself as a download
([Setup](setup.md#the-record)).

The WiFi region (`wifi_country`) sets the radio's allowed channels and
transmit power. Automatic follows the country the access point advertises,
else the world rules; a selected country pins it. The setting applies
immediately and at every boot.

Every machine tunable, shared, cloud-override, and GRBL-mode, has a home in
one of these tabs, with three exceptions: `cool_laser_heat_cw` and
`cool_laser_heat_density` are bench-measured coefficients set by hand in the
settings file, and `cool_aa_offset_counts` is written by the air-assist
offset diagnostic's Apply button.

## The routes an operator uses

| Endpoint | Purpose |
|---|---|
| `GET /status` | Machine operational status as JSON (state, position when homed, fans, coolant, switches, `gates_off`, the `grbl` state block while a GRBL controller runs, the `diag` flag) |
| `GET /settings` | Current settings as JSON (plus `machine_id`, the fuse-derived identity, the firmware version, `tls_fingerprint`, and the `gates` table: range, recommended band, off end and state per gate setting) |
| `POST /settings?key=value&...` | Set any subset of known keys ([Settings](settings.md)) |
| `GET /mode` | Supervisor state: mode, controller (`running`, `stopped`, `standby`, `waiting` with `why` naming what is open, `motion-fault`, or `gated` with `why`), pid, motion verdict |
| `POST /mode?controller=grbl\|cloud` | Live idle-gated mode switch; also the retry lever after a motion fault |
| `POST /controller/stop`, `POST /controller/start` | The manual emergency lever: stop halts the active controller and holds supervision suspended; start resumes it ([Modes](modes.md)) |
| `GET /cool/status` | Cooling-engine state: phase, verdict, temps, report age, `gates_off`, the effective `limits`, `fan_gates` |
| `GET /grbl/settings` | The GRBL controller's `$$` view, while a GRBL controller runs |
| `GET /login`, `POST /login`, `POST /logout` | The login page, the login (`name`, `password`), and the sign-out |
| `GET /setup`, `GET /wiz`, `GET /wiz/record`, `GET /wiz/record.html`, `GET /advisories/<id>`, `POST /wiz/...` | The setup, its record (as JSON, a download, or the printable summary), and the what-changed menu ([Setup](setup.md#the-routes)) |
| `GET /system/ssh`, `POST /system/ssh?enable=0\|1` | SSH state, and the switch that turns it on until the next reboot |
| `GET /system/camera-key`, `POST /system/camera-key?rotate=1` | The camera key with the URLs that carry it, and a new key ([Cameras](cameras.md#watching-it)) |
| `GET /cert`, `GET /cert.pem` | The certificate page (fingerprint, names, validity) and the certificate in PEM form; on plain HTTP too, no login, no redirect, so the fingerprint can be checked before the browser's warning is accepted |
| `GET /licenses` | The Licenses page every panel page links in its footer: the manifest of every installed package with its license, and the bundle download |
| `GET /system/licenses`, `GET /system/licenses/manifest` | The image's license bundle (`tar.gz`: the manifest and the full license texts), and the manifest alone as text |
| `POST /restore/factory-return?confirm=1` | The setup's factory-return exit ([Setup](setup.md#go-back-to-the-factory-firmware)) |

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

The panel has two listeners. HTTPS on port 443 serves everything. HTTP on
port 80 serves only the read-only routes to your network. Those are
`GET /status`, the camera routes, `/settings`, `/grbl/settings`, `/mode`, `/cool/status`,
`/diag/status`, `/curve/status`, `/curve/ladder.gcode`, `/slots`,
`/update/status`, `/wiz`, `/wiz/advisories/press`, and `/advisories/<id>`.
A request over HTTP that changes state is answered only from the machine
itself; every other client is redirected to HTTPS.

Every route that changes machine state needs a login session, and a browser
request must not be cross-site. That is what stops a hostile page in
another tab from reaching your machine. The panel also answers only to its
own addresses and to its own bare name (`forgefirm-<xxxx>`), never to a
name with a domain on it: a hostile page that points its own domain at your
machine gets nothing back. The read-only routes answer any
client on your network by default, so LightBurn can read the camera without
a login. The setting `panel_open_reads=0` closes them to logged-in sessions
and to the machine itself ([Settings](settings.md)).

A script that runs on the machine can use the panel token instead of a
session. It reads `/data/forgefirm/panel.token` and sends it in the
`X-ForgeFIRM-Token` header. A script on the network needs a login session
too, except on a development image.

Two things need the physical button held as well as the login: reading the
fuse identity (`GET /fuse-identity`, which returns the serial, the derived
hostname, and the password) and installing an unsigned firmware image.
