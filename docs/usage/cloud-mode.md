---
title: Cloud mode
---

# Cloud mode

Cloud mode runs the machine under the Glowforge web service, so the Glowforge
phone and web apps drive it as they drive a stock machine. This page tells you
what you need, how the machine connects, what works, and what is different for
the operator.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## What it is

In cloud mode the machine signs in with its own identity, tells the service
that its software is ForgeFIRM (the User-Agent is `ForgeFIRM/<version>`), and
uses the service the way a stock machine does; the app drives it end to end:
connect homing, Set Focus, material imaging, and full
prints (button press, cut, return home). It is optional, off by default, and
kept and maintained on purpose. It is distinct from camera-referenced homing in
GRBL mode, which borrows the service only for a homing cycle
([Homing](homing.md)).

The Glowforge protocol is undocumented and can change without notice. Each
ForgeFIRM release validates cloud mode against one specific factory
service/firmware version, the version it advertises to the service
(`2.6.0-2228`). The panel shows a **compatibility warning** when the live
service has moved past that baseline, and an **upgrade recommendation** only
when a newer ForgeFIRM exists. ForgeFIRM never downloads or installs factory
firmware, and the factory firmware is never offered
([Cloud mode internals](../technical/forgefirm/cloud-mode.md)).

The protocol itself is in [The cloud protocol](../technical/machine/cloud-protocol.md).
The client, its scope, and its handling of a job are in
[Cloud mode internals](../technical/forgefirm/cloud-mode.md).

## Selecting cloud mode

Select **Factory cloud** with the controller-mode selector on the panel's
Status tab, while the machine is idle ([Modes](modes.md)). The choice exists
only once the setup's cloud step turned cloud mode on (`cloud_enabled=1`,
[Setup](setup.md#cloud-mode)); while it is off, nothing
contacts the Glowforge service. The setting persists across reboots.
Switching back to GRBL mode is the same selector.

## Credentials

The machine signs in to the service with a serial number and a password. By
default it uses the identity burned into the board's factory fuses, so a
machine running under its own account needs nothing configured.

The **GF Cloud** tab holds the overrides. They exist for one job: putting a
machine's own identity back after a control board is replaced.

The identity is fused into the board, not the chassis. A board that comes from
another machine - a donor board from a unit scrapped for a dead tube or power
supply, which is how most replacements are obtained - carries that machine's
serial. Left alone, the machine signs in as the donor, and the service applies
the donor's stored calibrations for the laser, the camera and the optics to
hardware they were never measured on. The overrides set the serial and password
back to the ones the machine had before the repair, so the service serves the
calibrations that belong to the hardware in front of it.


| Setting | Meaning |
|---|---|
| `gf_serial` | Cloud sign-in serial override (digits). A serial override re-derives the service hostname. |
| `gf_password` | Cloud sign-in password override (64 hex digits). Write-only: `GET /settings` reports `gf_password_set`. A blank password field keeps the current override. |

Blank fields mean the factory fuse identity.

!!! warning "Keep the serial and password secret"

    They cannot be changed. Do not share them, and do not post them in an
    issue report; the log export masks them by default ([Logging](logging.md)).

### Reading your machine's identity

!!! tip "Record the identity while the board still works"

    The serial and password live in the control board's fuses and are
    readable only from a board that runs. A board that has failed takes them
    with it, and there is no way to recover them from it afterward - which
    leaves a repair with no way to put the machine's own identity back on a
    replacement board, and the service serving the donor's calibrations for
    good.

    Read them once, now, and keep the pair somewhere safe and private: a
    password manager, or paper away from the machine. Treat them like a
    password, because the second one is one ([Keep the serial and password
    secret](#credentials) above).

The panel can show it: `GET /fuse-identity` returns the serial, the derived
hostname, and the password. It needs a login and the physical button held
while the request is made, and it is fetched on demand only.

At a console ([Serial access](../install/serial-access/index.md)) the identity comes
from the i.MX6 OCOTP fuses: the serial from `HW_OCOTP_MAC0`, the password from
`HW_OCOTP_SRK0..7`. The hostname is the identifier shown at the command prompt,
in capitals. In a Python shell on the machine:

```python
def read_file(filename):
    with open(filename) as f:
        return f.read()

# the serial
int(read_file('/sys/fsl_otp/HW_OCOTP_MAC0'), 16)

# the password
password = ''
for x in range(8):
    password += "%08x" % int(read_file('/sys/fsl_otp/HW_OCOTP_SRK%d' % x), 16)
print(password)
```

## Configuration

Everything you would normally change is on the panel's **GF Cloud** tab, and
you can leave all of it alone:

- **Machine identity**: blank means the machine's own, which is what you want
  unless this machine is standing in for another one (above).
- **The homing-session timeout**: how long a camera homing cycle may take
  before the machine gives up on it.
- **Print pause**: how far the machine rewinds when you pause a print and how
  far it leads back in when you resume, so the resumed cut overlaps what it
  already burned instead of starting cold. The factory's own values, and there
  is rarely a reason to change them.
- **Job size**: two limits on how big a job the machine will accept. A cloud
  print arrives as one compressed file that the machine holds in memory while
  it plays, so these bound *memory*, not how long a job may be. It warns above
  32 MiB and refuses above 128 MiB, and nothing anyone has printed comes near
  either.

[Settings](settings.md) lists every key. The client's own configuration file
and the rest of its options are on
[Cloud mode internals](../technical/forgefirm/cloud-mode.md#configuration);
you do not normally touch it.

## Connecting

The client signs in, opens the service's WebSocket, and answers the service's
actions from then on. Two things you will see:

- **The service drops the socket on its own schedule**, roughly hourly in a
  long idle session. That is routine: the client reconnects and signs in
  again, and the machine stays signed in and serving actions with no operator
  involvement.
- **The service runs a hunt when the machine connects.** On a fresh start the
  client reports its values and the service answers with its connect-time
  hunt, a lens hunt and head positioning, because a print placed on a stale
  head position can run the gantry into a rail.

A restart within a session, where the service already knows where the head is,
can skip that hunt: start the client with `--no-hunt`, or with the marker file
`/run/gfcloud-nohunt` present, and the first settings report goes out in the
reconnect form the factory client itself uses on every reconnect. The log
carries `NO-HUNT:` at the start. The marker is under `/run`, so a reboot never
comes up with it; the client that starts reads it and takes it down, so it
applies to that one start and never to a respawn after it.

## What works

The full factory workflow: sign-in, camera homing, Set Focus, material imaging,
prints with the button press, pause and resume, cancel, and the return home.
Also covered: the lid and interlock aborts, a cancel during the button wait, a
paused print canceled by the lid, and a print longer than the ring with a
cancel from the app. The app's progress bar works: the machine sends the
progress frame the app reads, every 30 s during a job.

What the machine does not do for the service:

- It sends no continuous sensor telemetry; on-demand requests (the settings
  report, image captures, the action handshake) are answered.
- It refuses a factory reset and a laser-head firmware update from the
  service, and it answers an update check without installing anything.

The scope and its reasons are in
[Cloud mode internals](../technical/forgefirm/cloud-mode.md).

## The cameras only work with the lid closed

Neither camera captures while the lid is open, and in cloud mode the service
asks for images on its own schedule. A refused image is reported back to the
service as a failed action, so it resolves rather than hanging. One
consequence: the factory ran its focus hunt with the lid open, and a hunt
includes a head capture, so **a hunt attempted with the lid open fails**. Close
the lid before you let the app focus or print. [Cameras](cameras.md) has the
rule in full.

## Pause, cancel, and park

- **The button pauses and resumes a print**, exactly as the factory does. A
  press stops the head under control and rewinds a little way with the laser
  off; the next press runs forward and lights the beam slightly *before* the
  point it stopped at, so the resumed cut overlaps what it already burned
  instead of starting cold and leaving a mark. Both distances are settings on
  the GF Cloud tab, at the factory's own values
  ([Factory firmware](../technical/machine/factory-firmware.md#pause-cancel-and-park-in-the-factory)).
  Motions and hunts do not pause.
- **The cooling engine can pause a print too.** A hold from it (a warm-up
  on a cold machine, coolant over the ceiling, a suspected flow fault) pauses
  the print the same way, laser off, and the print resumes by itself when the
  engine clears it. A print that arms on a cold machine waits for the
  warm-up before it starts. A hold that lasts longer than `cloud_hold_max_s`
  (30 minutes by default) cancels the print instead.
- **A lid or interlock open, or a cancel from the app, ends the job.** Motion
  stops, whatever remains in the ring is dropped so nothing can play later,
  and the head parks back at the job's starting point, ignoring the lid, as
  the factory does. The job is reported as canceled.
- **The service dead-reckons position**, so the park after every print,
  finished or aborted, matters: cutting it short would offset everything until
  the next camera home. That is why the park ignores the lid and the cancel
  flag.

A lid or interlock open during the pre-print button wait cancels the job, and
a press with the lid open never arms.

## Homing and hunts

Cloud homing is camera-based: the service takes a lid image, moves the head,
takes another, and computes where it is. The lens hunt references Z against the
hall sensor. Hunt motion is not lid-gated, but the head capture inside a hunt
is, so the lid must be closed for a hunt to complete.

Connecting also resets where the machine thinks it is, so **re-home after you
switch back to GRBL mode** ([Homing](homing.md#homing-in-cloud-mode)).

## Fans and cooling

A cloud job brings its own fan profile: the job's header carries the run fan
duties, and the client passes them to the cooling engine, so a print gets the
fan profile the service designed for it and a lens hunt stays quiet. The
header can tighten the coolant ceiling and the fan floors for that job; it can
never loosen a local setting, and a gate you turned off stays off whatever the
job says ([Cooling and fans](cooling-and-fans.md)).
