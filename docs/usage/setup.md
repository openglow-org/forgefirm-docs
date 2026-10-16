---
title: Setup
---

# Setup

Setup is the first run of the control panel on a new ForgeFIRM
install. It collects your consent, creates your account, records the
machine's facts, decides whether cloud mode exists, and checks and measures
the machine. The first steps, through the coolant flow calibration, are
required: no controller runs for a Grbl sender until they are done. Every
step after them is recommended, never required. This page describes the steps, the button
press, the record, what the setup recommends, and the gate. It also
describes the way back to the factory firmware.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## The first run

Open `https://<ip>/` after the first boot. The
serial console prints both addresses. The certificate is self-signed, so
the browser warns once; its fingerprint is at `http://<ip>/cert` for anyone
who wants to compare it before accepting
([The control panel](control-panel.md#the-address)). Until the guided run
ends, the panel serves the setup at `/`. Afterward `/` serves the control
panel, the setup lives at `/setup`, and the System tab's **Setup** card
opens it again.

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
   Pro, whether it has the thermoelectric cooler (checked by default). The
   machine cannot detect a TEC, so your answer is `cool_tec_present`. The
   step shows the sheet id ([The sheet id](#the-sheet-id)).
6. **Cloud mode.** Off by default. Turning it on asks you to type
   `I UNDERSTAND` again. Then it asks for the homing choice for GRBL mode
   and an optional identity override ([Cloud mode](cloud-mode.md)).
7. **Intake fans.** The fans run as they do in a cut for about 20 seconds
   while the machine counts its intake fans
   ([One intake fan or two](../technical/machine/coolant-and-airflow.md#one-intake-fan-or-two)),
   and the count is written as `cool_intake_fans`. When intake 2 gives no
   reading, or intake 1 does not come up to speed, the step asks you how
   many intake fans the machine has: look at the back of the machine and
   choose **One** or **Two**. The machine cannot tell one fan from a second
   fan that has stopped, so it asks. When intake 2 gave no reading and you
   choose **Two**, every cut stops with an airflow fault until intake 2
   turns. Nothing moves, and the laser stays locked.
8. **Coolant flow.** The flow calibration, fifteen to twenty-five minutes.
   When the bands are too close to separate, the heater duty steps up from
   40 to 55 to 70 percent and the trial repeats. The threshold and the duty
   it was found at are written together: `cool_flow_rise` and
   `cool_flow_heater_pct`. A calibration that ends before its threshold is
   found, for any reason, a power loss included, leaves
   `cool_flow_heater_pct` as it was.
   The step is required because the coolant's rise differs from machine to
   machine: without it, a machine whose coolant warms more with flow can
   have every cut stopped by the flow check.
9. **Continue or start.** The machine is yours to use from here. Choose
   **Continue the setup**, which we recommend, or **Start using the
   machine**.
10. **The checks.** Seven checks of the machine with the laser locked, eight
    with cloud mode on ([The checks](#the-checks)).
11. **Focus.** The laser burn that measures the head's focus
    ([The laser burns](#the-laser-burns)).
12. **Ready.** What the setup found, the record
    ([The record](#the-record)), and **Open the control panel**.

Steps 2 to 8 are required: no controller runs for a Grbl sender until they
are done, and none of them can be skipped ([The gate](#the-gate)). Every
step after the choice is recommended, and has **Finish later** in its
footer. **Start using the machine** and **Finish later** end the
guided run as **Open the control panel** does: the control panel opens,
and it lists what the setup still recommends
([What the setup recommends](#what-the-setup-recommends)). Open `/setup`
at any time to go on.

A document that changes in a later release must be accepted again, and
until it is, no controller runs for a Grbl sender. A later release can
also ask for a step again. Preferences, Your machine, Cloud mode, and
Coolant flow then hold the controllers until you run them, and `/setup`
opens on the first; any other step is recommended. A step that is open
again is a link in the setup's rail, from any other step, and
`/setup?step=advisories` opens it directly.

## The checks

Each check runs on the machine with the laser latch locked. The page shows
the progress, the log, and a question when the check needs you. A question,
or a wait for you to work a switch (the lid, the button, the interlock
loop), lasts ten minutes; past that the check ends and says so. A check
that fails says why and offers to run again. A check that
measures writes the settings it found, through the ordinary validated path,
and the record keeps the values before and after.

1. **Switches.** Open and close the lid, press the button, and on a Pro open
   and close the interlock loop. The machine watches each switch change and
   reads whether the head answers. About three minutes.
2. **Sensors.** Ten seconds of readings at rest: both coolant temperatures
   within 1.5 C of each other and within 0 to 40 C, the chassis and the
   processor in range, the lid infrared sensors under the fire watch's
   alert tier, no accelerometer event, the laser supply power-good, no HV
   current, the fans turning at idle.
3. **Airflow.** The fans run at the cut profile for 35 s. Each fan's steady
   speed (the median of the last ten seconds) and its time to 90 percent set
   the floors: 55 percent of steady for `cool_tach_exhaust_min_rpm`,
   `cool_tach_intake_min_rpm`, `cool_tach_air_assist_min_rpm`, and
   `cool_purge_min_current`, and the slowest spin-up plus 5 s for
   `cool_fan_grace_s`. A fan under 1000 rpm fails the check. Some machines
   are built with one intake fan
   ([One intake fan or two](../technical/machine/coolant-and-airflow.md#one-intake-fan-or-two)):
   the check goes by the machine's count from the Intake fans step. When
   intake 2 never reads a pulse, a one-fan machine has its intake floor set
   from intake 1, and a two-fan machine fails the check. When both intakes
   turn, the check sets the count to two. The motion controller stops for
   the run.
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
7. **Cloud header.** Only with cloud mode on. The machine starts in cloud
   mode; you place any small design in the Glowforge app and press Print
   there. The check takes the numbers the service sends for this machine,
   cancels the print before it arms, logs the calibration-bearing tags
   beside the machine's own numbers, and returns to GRBL mode. Nothing is
   written to the settings ([Cloud mode](cloud-mode.md)).
8. **Lens travel.** The lens finds its reference on the edge of its hall
   sensor, the one position reference the head has. Then it finds its two
   stops by the head accelerometer, with every fan off: one half-step at a
   time from the reference, listening for the ring of each step, which dies
   the moment the carriage meets a stop, a few steps before the motor could
   slip. The lens backs off at once, and the count back to the reference
   proves nothing slipped. The free half-steps each way are written as
   `lens_stop_below_steps` and `lens_stop_above_steps`. The controller opens
   its Z limit from the same two numbers, and Focus steps its lines inside
   them, so every lens move stays inside the head's free travel. When the
   stops cannot be found on a head (the ring unreadable, no stop within
   reach, or a slip), the check writes a reduced travel that clears the
   stops on any head, says so in its result, and asks you to open an issue
   at github.com/openglow-org/forgefirm or post on community.openglow.org so
   the head can be looked at. About three minutes. However the check ends,
   the lens goes back to its reference
   ([forgectrl](../technical/forgefirm/forgectrl.md#the-setup-burns-and-the-lens)).
   The lens and its travel are on
   [The motion hardware](../technical/machine/motion-hardware.md#the-lens-and-its-travel).

One more check, **Flow check**, is the short form of the flow calibration
(about three minutes) for a re-run; the first run does not need it.

### Bed size

**Bed size** is optional, and you can skip it: the setup never asks for it.
Run it from the list, and only with the
[gantry stops](../install/gantry-stops.md) installed. It measures how far the
head can go from X0 Y0 in X and Y.

Home the machine first, on its gantry stops or with the camera, and close the
lid. The check opens the controller's envelope to the travel plus 30 mm for
the measurement. You jog the head toward the right end in steps of 10, 1,
and 0.1 mm, watching the head and not the page, and press **This is the
end** just short of where it would touch; then the same toward the front.
The check writes `envelope_x_mm` and `envelope_y_mm` 1 mm short of where you
stopped, sets the envelope from them, and jogs the head back to X 10 Y 10.
From then on a job past those edges is refused
([Homing](../technical/forgefirm/homing.md#the-far-edges)).

Keep your Grbl sender quiet while it runs: a line from any client closes the
widened envelope at once, and the check then stops without writing
anything. An abort sets the envelope back as well.

## The laser burns

Two steps fire the laser: **Focus**, which the setup recommends, and
**Laser floor**, which is optional. Each runs on its own scrap of wood, and
you can run it again at any time from the Setup tab. Laser floor needs
Focus to have run first ([Laser floor](#laser-floor)). You need a flat
scrap of any wood, and calipers or a ruler for its thickness.

The laser fires only after your press on the machine's button, every
cooling gate stands, and a lid opened during a burn cancels it. Eye
protection, the exhaust, and an extinguisher in reach are on you. Each
step's page shows a preview of what it burns, and the program behind it.
While a step runs, the page names what the machine is doing and counts the
seconds, prompts the press when the button lights white, and ends with the
result in a sentence; the settings the step wrote, each with its value
before, and the numbers behind the sentence sit under a fold. A question
about the burn waits half an hour for your answer and the page counts that
down, so a careful look never loses a burn. The tube current and the
kernel's LASER_ON samples must both see the beam, or the step fails. The
head's beam sensor is recorded but not required: a head whose sensor gives
no output still runs the step, and the step's log says so.

**The crumb tray must be in.** The scrap goes on the tray, and Focus
measures the height above it. A burn will not start while the panel says
the tray is out: put the tray in and set Tray in on the Machine tab
([The control panel](control-panel.md#machine)).

Each step asks, in order:

1. **The gantry stops.** Say that the
   [gantry stops](../install/gantry-stops.md) are installed. The step goes
   no further without them.
2. **The head at home.** The lens finds its reference, and the step asks
   whether the head is home: the back-left corner, against the gantry
   stops. A burn that ran to its end brings the head back, so after one the
   answer is **The head is home**. When it is not there (a burn stopped part
   way, or the head was moved), choose **Release the motors**: open the lid,
   push the head gently to the back-left corner against the gantry stops,
   keeping the gantry square to the machine, close the lid, and continue.
   The motors hold the head again.
3. **The scrap.** Open the lid and put a flat scrap in the back-left corner
   of the cut area: as far left as it goes, its top edge at the top of the
   cut area. Focus needs at least 78 x 68 mm (3.1 x 2.7 in), Laser floor
   86 x 68 mm (3.4 x 2.7 in). Close the lid.
4. **The thickness.** The scrap's thickness, in your units, as a plain
   number such as `3.2`: not `1/8`, and with no unit after it. It must be
   more than 0 and at most 30 mm (1.18 in). For Laser floor it must also
   be inside the lens's reach: the step names the range and asks again.
5. **The arm.** Continue, then press the button when it lights white.

Each step burns its box 10 mm from the head's home in X and Y. The program
declares X0 Y0 at the head with `G92`, and its last moves bring the head
back home. A burn that gets as far as its program clears any G92 origin
when it ends, also one your sender set, so set yours again after a burn. If
a burn cannot clear it, its log
says so: send `G92.1` before your next job. A burn that stops part way
also puts the lens back on its reference
([forgectrl](../technical/forgefirm/forgectrl.md#the-setup-burns-and-the-lens)).
Open the lid and look at the burn as much as you like, with a loupe if you
have one, but do not move the scrap until the step is done.

### Focus

Twelve lines burn heavy across the box, numbered 1 to 12 from the top, the
lens stepped evenly from the top of the travel the Lens travel check
measured to the bottom ([The checks](#the-checks)). Until that check has
run on this head, or when it could not find the stops, the lines span the
reduced travel instead, and the page says so. Every line marks; pick the
narrowest dark one, with the crispest edges, by its number. The depth of
focus spans a few lines, so several adjacent lines will look the same:
choose every one that does, and the middle of that run is the pick. A pick
on the first or the last line is refused: the focus lies outside the
ladder, and a scrap nearer 1/8 in (3 mm) puts it inside.

The lens is a 2 in lens under a collimated beam, so it moves with its focal
point, and every head's lens screw is the same: the pick's distance from
the reference, over the screw's scale, below the thickness is the focal
height when the lens sits on its reference. That one number is written as
`lens_hall_edge_z_mm`; it is what differs from head to head, and it is
measured above the tray, which is why the step needs the tray in. On the
controller Z is the focal point's height above the tray, so a job on 3 mm
material runs at Z 3; a home puts the lens on its reference, sets Z from
the number, and parks the focus at `lens_park_z_mm` (3 mm by default; yours
to set on the Machine tab). The lens never drives onto a stop; the reach it
has around the reference goes into the record and onto the page. Lengths
on the page are in your units. The lens and its travel are on
[The motion hardware](../technical/machine/motion-hardware.md#the-lens-and-its-travel).

### Laser floor

Run Focus first: the floor burns at the focus that Focus measures. The
step does not start until Focus has run, nor while the setup recommends
Focus again, as it does after a new head or a new tray
([What changed](#what-changed)).

Twelve rungs burn across the box from 2 to 24 percent pulse density, the
floor and the dose curve off for the rungs. Pick the faintest rung that
shows a continuous line; `laser_floor_density` is written two percent
above it. When no rung shows one, answer **None**: nothing is written, and
the tube or the supply needs attention before the floor can be set.

### The other laser numbers

No setup step burns for the rest. The tube's dose curve comes from the
dose-curve recorder on the panel's GRBL tab
([Diagnostics](diagnostics.md#other-measurements-from-the-panel)). The
corner rolloff is the `laser_corner_gamma` setting
([Settings](settings.md#settings-that-affect-motion)). The tube's heat
coefficients, `cool_laser_heat_cw` and `cool_laser_heat_density`, keep
their defaults: no step measures them
([Cooling and fans](cooling-and-fans.md#the-other-gate-settings-on-the-machine-tab)).

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
| Solid white | Press me: a burn's program waits for its arm press (the controller lights it, as for any job) |
| Blinking amber | Attention: a check waits for the lid to close; or the password reset hold at power-on |
| Solid green | The guided run ended with nothing left to recommend; it goes out when the control panel opens. A run set aside with steps left does not light it |
| Dark | Nothing waits for you |

## A second browser

One browser drives a running check or burn; the page that started it holds
the run. A second browser that opens the same step follows it: the same
phase, log, and prompt, with nothing to press. Its banner offers **Take it
over here**, which moves the run to that browser; the first one follows from
then on. A tool that uses the panel token without a login is never held back.

## What the setup recommends

Every step after the choice is recommended, never required: the machine
runs for a Grbl sender without it. The machine recommends a step that has
not run yet, a step that this release asks for again, and a step that
something asks for: a fault or a thin margin the machine saw, a part you
replaced ([What changed](#what-changed)), or a different head at boot. Each
recommendation comes with its reason. The full list of what recommends a
step is on [forgectrl](../technical/forgefirm/forgectrl.md#setup-and-the-gate).

A required step can be recommended again too, for example after a fault or
a part change. It still counts as done: the controllers keep running, and
the setup page does not send you back to it.

Laser floor and Bed size are optional: never recommended for not having
run, only when something asks for them, as a tube change asks for Laser
floor. A run of a step clears its recommendation.

Once the guided run has ended, the control panel shows a **Setup not
finished** banner while anything is recommended. You can dismiss it
([The control panel](control-panel.md#the-page)). The Setup tab lists each
recommended step with its reason
([The control panel](control-panel.md#setup)). When the guided run ends
with nothing recommended, the button lights solid green.

## What changed

A replaced part makes the numbers measured on the old one wrong. The
Setup tab's **What changed?** menu names the change, and the machine
recommends the steps that measure or prove the new part:

| The change | Recommended again |
|---|---|
| The laser tube | Laser floor |
| The coolant pump, or the coolant | Coolant flow |
| A fan | Airflow |
| The head | Your machine, Lens travel, Focus, Motion, Cameras |
| The tray | Focus |
| A cover off (belts, drivers, wiring, switches) | Switches, Motion |

The head change is also found on its own: a machine that boots with a
different head recommends the same steps. It also sets aside the lens
travel the old head measured, so until Lens travel runs, the lens keeps to
the reduced travel that clears the stops on any head
([forgectrl](../technical/forgefirm/forgectrl.md#setup-and-the-gate)).

## The record

The setup writes `/data/forgefirm/setup.json`. The record holds the
accepted advisories with their hashes and times, the account name, and the
machine facts. It also holds each wizard's completed version, its results,
its applied settings (each with the value before), and the flags. The
record is on `/data`, outside the firmware slots, so it survives updates.
It never holds the serial number, a network name, or a credential.

The record leaves the machine three ways, all from the System tab's
**Setup** card and from the setup's last screen:

- **Printable summary**: `GET /wiz/record.html`, a page with no script, to
  print or save with the machine: the machine facts, the acknowledgment
  with each document's hash, and every step with its sentence, the settings
  it wrote, and its numbers.
- **Save the record**: `GET /wiz/record?download=1`, the JSON file itself,
  named after the sheet id. `GET /wiz/record` is the same document as a
  plain read.
- **The log export**: the sanitized bundle carries the record as
  `system/setup.json` ([Logging](logging.md)). Beta testers are
  asked to send that bundle by private message, so the project learns what
  varies from machine to machine.

Both routes take a login or the panel token.

### The sheet id

The sheet id is a code derived from the serial number with a secret salt
kept on the machine (`/data/forgefirm/sheet.salt`). It never reveals the
serial. The Your machine step shows it, and it names the record's download,
so a record matches its machine.

## When the setup will not go on

The setup carries **Download logs** in its header, on every step. It builds
the same sanitized bundle the Logs tab builds
([Logging](logging.md)), so a setup that stops on something the page cannot
explain can still be reported: take the bundle and attach it. The panel's
own Logs tab is reachable once you set the setup aside, which you can do
once the required steps are done (**Start using the machine** or
**Finish later**); before that, the setup's button is the way to the logs.
The machine refuses an export while
it is cutting, and says so on the line under the header rather than leaving
a dead button.

## Running a step again

The System tab's **Setup** card shows the state of the setup and the
certificate fingerprint, with a link to `/setup`. Open it to run any step
again, or one the machine recommends. The Setup tab lists every step, what
the machine recommends and why, and the **What changed?** menu
([The control panel](control-panel.md#setup)).

## Checks your extensions add

An extension package can add a check of its own, listed after the
machine's checks. It runs like any other check, with its log, its
questions, and its result, but it is the package's: nothing of the
machine's setup waits for it, it is never the next step the page opens,
and its result is the package's own, which the package uses to decide what
it may do. See [Extensions](extensions/index.md).

## The gate

No controller runs for a Grbl sender until the required steps are done:
the advisories (every document, then the button press), the account,
Preferences, Your machine, Cloud mode, Coolant flow, and the count of the
intake fans. Coolant flow matters because the coolant's rise differs from
machine to machine (step 8 of [The first run](#the-first-run)). The gate
waits for that step itself: a **Flow calibrate** applied from
[Diagnostics](diagnostics.md) writes the threshold but does not count as
the step. The count matters because a machine built with one intake fan would
otherwise stop every cut with an airflow fault. The Intake fans step
counts them, and so does the Airflow check; setting Intake fans on the
Machine tab gives the count too
([Cooling and fans](cooling-and-fans.md#settings)). Nothing else holds the
controllers. A later release that changes a document, or asks again for
Preferences, Your machine, Cloud mode, or Coolant flow, closes the gate
again until you accept it or
run the step.

While the gate is closed, the panel's Status tab shows a banner that says
what is missing, with a link to the setup. What the machine reports while
the gate is closed, in its own words, is on
[forgectrl](../technical/forgefirm/forgectrl.md#setup-and-the-gate).

## Cloud mode

The setup's cloud step sets `cloud_enabled` (0 or 1, default 0). While it
is 0, the GF Cloud tab, the Factory cloud mode button, and the gfcloud
homing choice do not exist. `controller_mode=cloud` and
`homing_mode=gfcloud` are refused, and nothing contacts the Glowforge
service ([Settings](settings.md)). A tool that writes the key through
`POST /settings` gives the same typed phrase to turn it on, and turning it
off there takes the cloud homing and the cloud boot mode down with it.

Turning cloud mode on also asks how the machine homes in GRBL mode: with the
service's cameras, by hand, or not at all ([Homing](homing.md)). A home by
hand that is already set is where the question starts, so turning cloud mode
on keeps it unless you choose otherwise.

To change the decision later, open the setup from the panel's
Setup card and choose **Cloud mode** in the rail on the left. The
step starts from the current choice. The preferences and the machine
steps run again the same way, and so does any step the record has opened
again, such as the advisories after a document changed. Turning cloud
mode on asks for the typed phrase again; turning it off does not.

## Go back to the factory firmware

Until the guided run ends, every setup screen has a footer link, **Go back
to the factory firmware**. It asks you to confirm. Then it restores the
archived factory image into the other slot, when that slot no longer holds
one, moves the boot selection, and reboots. Afterward the System tab's
**Factory restore** does the same
([Back to the factory firmware](../install/factory-restore.md)).
Reinstalling ForgeFIRM is the install process again from the console
([Install](../install/install.md)).

## A forgotten password

Hold the machine's button while you turn the machine on. Keep it held for
ten seconds, until the button blinks amber. The setup then asks for a new
account.

**The extension packages, when there are any.** The account step offers to
remove every [extension package](extensions/index.md) on the machine, its data,
and every signing key the last owner added, and the offer is ticked. Take
it when the machine is changing hands: a package can hold the last owner's
tokens and credentials, and a key of theirs would go on making their
packages install as trusted rather than as unverified. Clear it when you
are the owner and only forgot the password. The account is made either way:
if the packages cannot be removed, the step says so and the new account
stands.

## The routes

| Endpoint | Purpose |
|---|---|
| `GET /setup` | The setup page (also `/` until the guided run ends) |
| `GET /wiz` | The setup state: `gate` and its `why`, `fans_counted`, `missing` (the required steps the gate waits for, a release's version bump among them), `recommended` (each step's `id` and `reason`), every step with the version it completed at, and the what-changed menu; `extensions` lists the checks packages add (`pkg:<id>`, the title, done) |
| `GET /wiz/record`, `GET /wiz/record?download=1`, `GET /wiz/record.html` | The setup record, the same as a download named after the sheet id, and the printable summary |
| `POST /wiz/changed` | A replaced part or a service (`what`: `tube`, `pump`, `coolant`, `fan`, `head`, `tray`, `service`); the steps it maps to are recommended |
| `GET /advisories/<id>` | The text of one advisory; the `ETag` is its hash |
| `POST /wiz/advisories/accept` | Confirm one document (`doc`, `hash`, `phrase`) |
| `POST /wiz/advisories/press`, `GET /wiz/advisories/press`, `POST /wiz/advisories/press/cancel` | Ask for the button press, poll it, withdraw it |
| `POST /wiz/account` | Create the account (`name`, `password`; `wipe_extensions=1` after a reset also removes every extension package, its data, and the owner's keys) |
| `POST /wiz/preferences` | `ui_units`, `wifi_country`, `clock` |
| `POST /wiz/machine` | `model`, `tec` |
| `POST /wiz/cloud` | `enabled`, `phrase`, `homing_mode` (`gfcloud`, `manual`, or `none`; `gfcloud` when absent), `gfcloud_home_timeout_s`, `gf_serial`, `gf_password` |
| `POST /wiz/<id>/start`, `POST /wiz/<id>/answer`, `POST /wiz/<id>/abort`, `GET /wiz/dark` | A check, a laser burn, or a package's check (`pkg:<id>`): start it, answer its open prompt (`seq`, `value`), stop it, and read its state; the login that started it drives it, and the state says whether the run is `owned` and `mine` |
| `POST /wiz/<id>/takeover` | A second browser takes the running step over |
| `GET /wiz/sheet.svg?card=<id>`, `GET /wiz/sheet.gcode?card=<id>` | A laser burn's preview and its program (`laser.focus` or `laser.floor`) |
| `POST /wiz/complete` | End the guided run, finished or set aside; it needs an open gate (409 otherwise), and `/` serves the control panel from then on |
| `POST /restore/factory-return?confirm=1` | The factory-return exit |
