---
title: Commissioning
---

# Commissioning

Commissioning is the first run of the control panel on a new ForgeFIRM
install. It collects your consent, creates your account, records the
machine's facts, and decides whether cloud mode exists. This page describes
the steps, the button press, the record, and the gate that holds the
machine until the setup is complete. It also describes the way back to the
factory firmware.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## The first run

Open `https://<ip>/` after the first boot. The
serial console prints both addresses. The certificate is self-signed, so
the browser warns once; its fingerprint is at `http://<ip>/cert` for anyone
who wants to compare it before accepting
([The control panel](control-panel.md#the-address)). Until the setup is
complete, the panel serves it at `/`. Afterward the setup lives at `/setup`,
and the System tab's **Commissioning** card opens it again.

The setup runs in these steps:

1. **Welcome.** The machine id and the firmware version.
2. **Advisories.** Four documents: Safety and risk, Licenses and notices,
   Privacy, and The Glowforge cloud service. Read each one to the end. The
   safety document asks you to type `I UNDERSTAND`; the others ask for a
   checkbox. Then press the machine's button once. The press is the
   acceptance ([The button press](#the-button-press)).
3. **Your account.** A name and a password. This account opens the panel
   and SSH ([Login](control-panel.md#login)).
4. **Preferences.** The display units, the WiFi region, and the clock. An
   unset clock can be set from the browser. The step also checks for a
   newer release.
5. **Your machine.** Detected: the firmware, the build kind, the camera
   sensor, and the head. Asked: the model (Basic, Plus, or Pro) and, on a
   Pro, whether it has the thermoelectric cooler. The step shows the sheet
   id ([The sheet id](#the-sheet-id)).
6. **Cloud mode.** Off by default. Turning it on asks you to type
   `I UNDERSTAND` again. Then it asks for the homing choice for GRBL mode
   and an optional identity override ([Cloud mode](cloud-mode.md)).
7. **The checks.** Eight checks of the machine with the laser locked
   ([The checks](#the-checks)).
8. **Ready.**

A document that changes in a later release must be accepted again. A later
release can also require a step again. The panel then shows the gate banner
until you complete that step ([The gate](#the-gate)). A step that is open
again is a link in the setup's rail, from any other step, and
`/setup?step=advisories` opens it directly.

## The checks

Each check runs on the machine with the laser latch locked. The page shows
the progress, the log, and a question when the check needs you. A check
that fails says why and offers to run again. A check that measures writes
the settings it found, through the ordinary validated path, and the record
keeps the values before and after.

1. **Switches.** Open and close the lid, press the button, and on a Pro open
   and close the interlock loop. The machine watches each switch change and
   reads whether the head answers. About three minutes.
2. **Sensors.** Ten seconds of readings at rest: both coolant temperatures
   within 1.5 C of each other and within 0 to 40 C, the chassis and the
   processor in range, the lid infrared sensors under the fire watch's
   alert tier, no accelerometer event, the laser supply power-good, no HV
   current, the fans turning at idle. Optional: a room thermometer reading
   sets `cool_temp_offset_c`, the coolant sensors' per-machine offset.
3. **Airflow.** The fans run at the cut profile for 35 s. Each fan's steady
   speed (the median of the last ten seconds) and its time to 90 percent set
   the floors: 55 percent of steady for `cool_tach_exhaust_min_rpm`,
   `cool_tach_intake_min_rpm`, `cool_tach_air_assist_min_rpm`, and
   `cool_purge_min_current`, and the slowest spin-up plus 5 s for
   `cool_fan_grace_s`. A fan under 1000 rpm fails the check. The motion
   controller stops for the run.
4. **Motion.** The rail comes up and the liveness probe runs. The lens finds
   its reference on the hall sensor, five passes that must agree. Then the
   controller starts in loopback posture and the head jogs 50 mm each way on
   X and on Y at 3000 mm/min, the accelerometer as the witness and the crash
   watch armed. Each move is judged once the pulse engine has played it to
   the end. Keep the bed clear.
5. **Cameras.** With the lid closed, a snapshot from the lid camera and one
   from the head camera. You confirm each view.
6. **Coolant offset.** The air-assist offset diagnostic
   ([Diagnostics](diagnostics.md)), about six minutes, writes
   `cool_aa_offset_counts`.
7. **Coolant flow.** The flow calibration, fifteen to twenty-five minutes.
   When the bands are too close to separate, the heater duty steps up from
   40 to 55 to 70 percent and the trial repeats. The threshold and the duty
   it was found at are written together: `cool_flow_rise` and
   `cool_flow_heater_pct`.
8. **TEC.** On a Pro with the thermoelectric cooler: sixty seconds of drive
   with the fans on; the cold side must fall by 1 C relative to the coolant,
   or `cool_tec_present` is cleared with a warning.

9. **Cloud header.** Only with cloud mode on. The machine starts in cloud
   mode; you place any small design in the Glowforge app and press Print
   there. The check takes the numbers the service sends for this machine,
   cancels the print before it arms, logs the calibration-bearing tags
   beside the machine's own numbers, and returns to GRBL mode. Nothing is
   written to the settings ([Cloud mode](cloud-mode.md)).

A tenth check, **Flow check**, is the short form of the flow calibration
(about three minutes) for a re-run; the first run does not need it.

## The sheet

The last part of the setup measures the machine's own numbers on a sheet of
wood. It needs a piece at least 200 x 150 mm (8 x 6 in), any kind of wood,
any thickness you can measure, and calipers or a ruler for the thickness.
Each card is one press of the machine's button; the laser fires only after
your press, every cooling gate stands, and a lid opened during a card
cancels it. Eye protection, the exhaust, and an extinguisher in reach are on
you. Every card's page shows a preview of what it burns, and the program
behind it; the placement page shows the whole sheet with every card on
it. The sheet carries the patterns you judge; the numbers they yield
go into the record and show on the page and the Commissioning tab, not on
the wood. While a card runs the page names what the machine is doing and
counts the seconds (the lens reference, the controller start, the coolant
settle, the burn, the dark tail), prompts the press when the button lights
white, and ends with the result in a sentence; the settings the card wrote,
each with its value before, and the numbers behind the sentence sit under a
fold. A question about the sheet waits half an hour for your answer and the
page counts that down, so a careful look never loses a burn.

**Do not move the sheet between the cards.** The placement sets one datum
for every card, and each card is drawn from it. Open the lid and look as
much as you like, with a loupe if you have one, but leave the sheet where
it is until the last card is done; a sheet that moved needs the placement
and every card again.

1. **Place the sheet.** The lens finds its reference. The arrows move the
   head to the back-left, where the machine normally homes. Open the lid,
   push the sheet as far left as it goes with its top edge on the top of the
   cut area, close the lid, and set the origin. The head's position is the
   sheet's datum. Say whether this is the full sheet or a small piece for
   one card, and enter the thickness. Nothing fires.
2. **First fire.** The frame (180 x 130 mm) and the header band burn at the
   mark dose. The tube current, the head thermopile, and the kernel's
   LASER_ON samples must all see the beam, or the step fails. Say whether
   the frame is on the sheet, square, and visible, or ask for it lighter or
   darker; the dose that satisfied you is the sheet's mark dose.
3. **Focus.** The lens finds its reference on the edge of its hall sensor,
   the one position reference the head has. Then it finds its two stops
   by the head accelerometer: one half-step at a time from the reference,
   listening for the ring of each step, which dies the moment the carriage
   meets a stop, a few steps before the motor could slip; the lens backs
   off at once and the count back to the reference proves nothing slipped.
   That is the head's free travel, written as `lens_stop_below_steps` and
   `lens_stop_above_steps` before the ladder burns: the controller opens
   its Z limit from the same two numbers when it starts for the card, so
   the ladder and the limit are one window, and every lens move afterward
   stays inside it.
   When the stops cannot be found on a machine (the ring unreadable, no
   stop within reach, or a slip), the card keeps a reduced travel that
   clears the stops on any head, says so in its result, and asks you to
   open an issue at github.com/openglow-org/forgefirm or post on
   community.openglow.org so the head can be looked at. Then twelve lines
   burn heavy across the card, the lens stepped evenly from the top of its
   free travel to the bottom, numbered 1 to 12 from the top. Every line
   marks; pick the narrowest dark one, with the crispest edges, by its
   number, and confirm the thickness. The depth of focus spans a few
   lines, so several adjacent lines will look the same: choose every one
   that does, and the middle of that run is the pick. A pick on the first
   or the last line is refused: the focus lies outside the ladder, and a
   sheet nearer 1/8 in (3 mm) puts it inside.
   The lens is a 2 in lens under a collimated beam, so it moves with its
   focal point, and every head's lens screw is the same: the pick's
   distance from the reference, over the screw's scale, below the
   thickness is the focal height when the lens sits on its reference. That
   one number is written as `lens_hall_edge_z_mm`; it is what differs from
   head to head. On the controller Z is the focal point's height above the
   tray, so a job on 3 mm material runs at Z 3; a home puts the lens on its
   reference, sets Z from the number, and parks the focus at
   `lens_park_z_mm` (3 mm by default; yours to set on the Machine tab). The
   lens never drives onto a stop; the reach it has around the reference
   goes into the record and onto the page, and every later card runs at
   the focus for this sheet. Lengths on the page and the card are
   in your units. The lens and its travel are on
   [The motion hardware](../technical/machine/motion-hardware.md#the-lens-and-its-travel).
4. **Laser floor.** Twelve rungs across the card from 2 to 24 percent pulse density,
   the floor and the dose curve off for the rungs. Pick the faintest
   rung that shows a continuous line; `laser_floor_density` is written two
   percent above it.
5. **Dose curve.** The recorder's seven 100 mm rungs, the thermopile
   reading each. The curve fits itself and, when it rises rung by rung, is
   written as `laser_dose_curve`. The page shows the fit.
6. **Corner rolloff.** The same corner-heavy pattern five times at rolloff
   exponents 1.0 to 2.0, under velocity-scaled power at 30 percent, in one
   press: the machine rewrites `laser_corner_gamma` and reloads it inside
   the job ahead of each pattern. Pick the most even one by eye.
7. **Flow under load.** First the coolant loop settles, the page counting
   the seconds and the drift. Then one press: the card's box, and a
   60 x 15 mm patch that keeps the tube lit for about a minute, both
   coolant sensors read for 100 s after. The engine's flow check is held
   for this card (its heater would swamp the tube's share); every other
   gate stands. The downstream rise per raw-second of tube current is the
   tube's heat coefficient: `cool_laser_heat_density` and
   `cool_laser_heat_cw`. About four minutes.

The sheet is done after the flow card. Keep it with the machine: the
header names the sheet, the build, and the start time, and the record
holds every number.

A card run again later, on its own, wants a piece the size of the card plus
10 mm on each side: run **Place the sheet** first and answer "One card".

The machine asks for a check again on its own: a fan that starts a job
within 10 percent of its floor recommends Airflow; a coolant flow fault
twice in a row requires Coolant flow; a thin margin on the flow check
recommends it; a different head at boot requires Your machine. The panel's
Commissioning tab lists the checks and what is asked
([The control panel](control-panel.md#commissioning)).

## The button press

The advisories step ends with one press of the machine's button. The panel
asks for the press, and the button breathes teal while it waits. One press
accepts every document you confirmed on the screen. The press proves that a
person stands at the machine.

## What the button says

The button's light is the machine's voice during the setup:

| The light | What it means |
|---|---|
| Breathing teal | Press me: the acceptance of the documents |
| Breathing white | The machine is working on a check with no controller running (a calibration, the lens reference, the fans) |
| Solid white | Press me: a card's program waits for its arm press (the controller lights it, as for any job) |
| Blinking amber | Attention: a check waits for the lid to close; or the password reset hold at power-on |
| Solid green | The setup is complete; it goes out when the control panel opens |
| Dark | Nothing waits for you |

## A second browser

One browser drives a running check or card; the page that started it holds
the run. A second browser that opens the same step follows it: the same
phase, log, and prompt, with nothing to press. Its banner offers **Take it
over here**, which moves the run to that browser; the first one follows from
then on. A tool that uses the panel token without a login is never held back.

## What changed

A replaced part makes the numbers measured on the old one wrong. The
Commissioning tab's **What changed?** menu names the change, and the checks
that depend on it are asked for again:

| The change | Required again | Recommended |
|---|---|---|
| The laser tube | Laser floor, Dose curve, Flow under load | Corner rolloff |
| The coolant pump, or the coolant | Coolant flow | |
| A fan | Airflow | |
| The head | Your machine, Focus | Motion, Cameras |
| The tray | | Focus |
| A cover off (belts, drivers, wiring, switches) | | Switches, Motion |

A required check closes the gate until it has run, as a release that
requires a step does ([The gate](#the-gate)); the override lifts it the same
way. A recommended check leaves the machine as it is. The head change is
also found on its own: a different head at boot requires **Your machine**.

## The record

The setup writes `/data/forgefirm/commissioning.json`. The record holds the
accepted advisories with their hashes and times, the account name, and the
machine facts. It also holds each wizard's completed version, its results,
its applied settings (each with the value before), and the flags. The
record is on `/data`, outside the firmware slots, so it survives updates.
It never holds the serial number, a network name, or a credential.

The record leaves the machine three ways, all from the System tab's
**Commissioning** card and from the setup's last screen:

- **Printable summary**: `GET /wiz/record.html`, a page with no script, to
  print or save beside the sheet: the machine facts, the acknowledgment
  with each document's hash, and every step with its sentence, the settings
  it wrote, and its numbers.
- **Save the record**: `GET /wiz/record?download=1`, the JSON file itself,
  named after the sheet id. `GET /wiz/record` is the same document as a
  plain read.
- **The log export**: the sanitized bundle carries the record as
  `system/commissioning.json` ([Logging](logging.md)). Beta testers are
  asked to send that bundle by private message, so the project learns what
  varies from machine to machine.

Both routes take a login or the panel token.

## When the setup will not go on

The setup carries **Download logs** in its header, on every step. It builds
the same sanitized bundle the Logs tab builds
([Logging](logging.md)), so a setup that stops on something the page cannot
explain can still be reported: take the bundle and attach it. The panel's
own Logs tab is not reachable until the setup is complete, which is exactly
when the bundle is hardest to get and most worth having. The machine
refuses an export while it is cutting, and says so on the line under the
header rather than leaving a dead button.

### The sheet id

The sheet id is a code derived from the serial number with a secret salt
kept on the machine (`/data/forgefirm/sheet.salt`). It never reveals the
serial. It is burned into the sheet's header, so a sheet matches its
machine.

## Running a step again

The System tab's **Commissioning** card shows the state of the setup and the
certificate fingerprint, with a link to `/setup`. Open it to run a step
again, or to complete a step that a release requires again. The
Commissioning tab lists every check with the version it completed at, what
the machine asks for again and why, and the **What changed?** menu
([What changed](#what-changed)).

## The gate

Until the first run is complete, no controller runs for a sender. The same
holds while a required step is out of date, or while a required flag is
raised. `GET /mode` reports the controller as `gated`, with a `why` field.
The panel's Status tab shows a banner with a link to continue the setup.

The override, for a person at the machine: create the file
`/run/forgefirm/commissioning-override` as root, at the console or over
SSH. It lifts the hardware gate until the next reboot. It never lifts the
advisories or the account, and the panel says so.

## Cloud mode

The setup's cloud step sets `cloud_enabled` (0 or 1, default 0). While it
is 0, the GF Cloud tab, the Factory cloud mode button, and the gfcloud
homing choice do not exist. `controller_mode=cloud` and
`homing_mode=gfcloud` are refused, and nothing contacts the Glowforge
service ([Settings](settings.md)). A tool that writes the key through
`POST /settings` gives the same typed phrase to turn it on, and turning it
off there takes the cloud homing and the cloud boot mode down with it.

To change the decision later, open the setup from the panel's
Commissioning card and choose **Cloud mode** in the rail on the left. The
step starts from the current choice. The preferences and the machine
steps run again the same way, and so does any step the record has opened
again, such as the advisories after a document changed. Turning cloud
mode on asks for the typed phrase again; turning it off does not.

## Go back to the factory firmware

Every setup screen has a footer link, **Go back to the factory firmware**.
It asks you to confirm. Then it restores the archived factory image into
the other slot, when that slot no longer holds one, moves the boot
selection, and reboots. Reinstalling ForgeFIRM is the install process again
from the console ([Install](../install/install.md)).

## A forgotten password

Hold the machine's button while you turn the machine on. Keep it held for
ten seconds, until the button blinks amber. The setup then asks for a new
account.

## The routes

| Endpoint | Purpose |
|---|---|
| `GET /setup` | The setup page (also `/` until the setup is complete) |
| `GET /wiz` | The setup state |
| `GET /wiz/record`, `GET /wiz/record?download=1`, `GET /wiz/record.html` | The commissioning record, the same as a download named after the sheet id, and the printable summary |
| `POST /wiz/changed` | A replaced part or a service (`what`: `tube`, `pump`, `coolant`, `fan`, `head`, `tray`, `service`); the checks it maps to are flagged |
| `GET /advisories/<id>` | The text of one advisory; the `ETag` is its hash |
| `POST /wiz/advisories/accept` | Confirm one document (`doc`, `hash`, `phrase`) |
| `POST /wiz/advisories/press`, `GET /wiz/advisories/press`, `POST /wiz/advisories/press/cancel` | Ask for the button press, poll it, withdraw it |
| `POST /wiz/account` | Create the account (`name`, `password`) |
| `POST /wiz/preferences` | `ui_units`, `wifi_country`, `clock` |
| `POST /wiz/machine` | `model`, `tec` |
| `POST /wiz/cloud` | `enabled`, `phrase`, `homing_mode`, `gfcloud_home_timeout_s`, `gf_serial`, `gf_password` |
| `POST /wiz/<id>/start`, `POST /wiz/<id>/answer`, `POST /wiz/<id>/abort`, `GET /wiz/dark` | A check or a sheet card: start it, answer its open prompt (`seq`, `value`), stop it, and read its state; the login that started it drives it, and the state says whether the run is `owned` and `mine` |
| `POST /wiz/<id>/takeover` | A second browser takes the running step over |
| `GET /wiz/sheet.svg?card=<id>`, `GET /wiz/sheet.gcode?card=<id>` | A sheet card's preview and its program |
| `POST /wiz/complete` | Mark the setup complete |
| `POST /restore/factory-return?confirm=1` | The factory-return exit |
