---
title: LightBurn
---

# LightBurn

This page sets up LightBurn for a machine in GRBL mode and walks through the
operating basics: job start mode, power, air assist, dry runs, and a good first
job.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

Jobs sent from LightBurn fire the laser. [Safety](../safety/index.md) has the
rules that apply to every job. The operator-armed window that every firing job
passes through is under
[GRBL mode](grbl-mode.md#arming-the-button-press-is-part-of-every-job).

## One-time device setup

Prerequisite: the machine is in GRBL mode ([Modes](modes.md)); the controller
listens on TCP port 23 at your machine's address, shown below as
`<machine-ip>`.

1. **Laser window, Devices, Create Manually** (skip auto-find; it scans serial
   ports).
2. Device type: **grblHAL** if your LightBurn version lists it, otherwise
   **GRBL**. Both speak the right protocol.
3. Connection: **Ethernet/TCP**. IP address: **`<machine-ip>`** (LightBurn
   uses TCP port 23 for GRBL devices, which is exactly where the controller
   listens).
4. Name: for example `Glowforge ForgeFIRM`. Work area: **X 495 mm, Y 279 mm**.
5. **Origin**: pick the corner where the head sits after parking at home:
   **rear-left as you face the machine** (the top-left dot in the selector).
   This is what keeps jobs un-mirrored: machine +X runs right, +Y runs from the
   rear rail toward you.
6. **Auto-home on startup: NO**. LightBurn would issue `$H` at every connect,
   and the camera homing method runs a session of a minute or more. `$H`
   itself works and is selected by the `homing_mode` setting in the machine's
   web control panel: `gfcloud` (Glowforge web-service vision homing; X/Y home
   to the factory corner, Z to the hall sensor; requires a signed-in Glowforge
   session), `switches` (physical limit switches, planned), or `none` (`$H` is
   rejected). Run `$H` deliberately from the Console tab when you want a true
   machine origin ([Homing](homing.md)). Z is the focal point's height above
   the tray: a Z of 3 focuses on the top of 3 mm material, and the job's Z
   moves the lens. The lens never moves without a reference: before a home,
   any Z move is refused (a jog with an error, a job with the soft-limit
   alarm), and after one, a Z beyond the lens's free travel is refused the
   same way. The reach is on the control panel's Machine tab, under Lens.
7. Finish. If a stale device profile already exists, edit its IP instead of
   creating a new one.
8. Device Settings (wrench icon): **S-Value Max = 1000** (matches `$30`).
9. Optional backup: File, Export Devices saves a `.lbdev` you can re-import
   later (the format is not editable text; export is the way to make one).

## Job start mode

This matters on an unhomed machine. In the Laser window set **Start From:
Current Position**, and set the **Job Origin** dot to the same corner as the
machine origin (top-left dot). The job then runs into the bed from wherever the
head currently sits. Absolute machine zero never matters, which is the
forgiving mode when you have not homed.

`Absolute Coords` also works after a successful `$H`, or if the head was parked
at the home corner when the controller started. After any Stop or alarm the
absolute frame is stale until you re-home with `$H` or restart the controller
with the head re-parked.

## Operating basics

- **Frame** traces the job's bounding box at travel speed. Do it before every
  Start. There are **no limit switches**: framing is your crash protection.
- **Start** runs the job. Travels run up to 200 mm/s; anything faster in a
  layer is clamped by the controller (`$110`/`$111` = 12000 mm/min).
- **Pause** = Grbl feed hold: motion parks within about 0.4 s (0.2 s stream
  queue plus deceleration); Resume continues exactly. **The big button does
  the same**: one press while a job runs pauses it (LightBurn shows Hold), the
  next press resumes it: the factory's pause and resume, on the machine. Two
  things to know before you pause a cut. **Resume where it stopped:** there is
  no backtrack in GRBL mode, so the beam restarts from where the deceleration
  ended and accelerates away from a standstill. At constant power (`M3`) that
  leaves a deeper spot you can see, while `M4` scales power with speed and
  mostly hides it. **Do not leave it paused:** the armed window has an idle
  grace (`laser_disarm_s`, default 60 s) that counts down through a hold, so a
  job left paused disarms itself and the resume asks for the button again
  before it can fire.
- **Opening the lid (or a Pro's interlock loop) during a job cancels it**, as
  the factory firmware does: the head parks with a controlled deceleration
  (the hardware cut the beam the instant the lid moved), the console reports
  the reason, the job ends for LightBurn (the controller resets; position is
  kept, no alarm), and the head returns on its own to where the job started,
  lid open or not. Close the lid and start again from LightBurn; the next job
  asks for the button, which is also what re-arms the machine's hardware
  button latch. The `lid_policy` setting on the control panel's GRBL tab can
  select the stock Grbl behavior instead (Door hold, Resume once closed). At
  idle, while jogging, or during homing the lid is yours to open and close
  freely. The controller does nothing there (the hardware blocks the beam
  anyway), so a lid cycle while loading material never leaves LightBurn
  waiting.
- **Stop** = soft reset: motion aborts with a controlled deceleration and
  grblHAL raises an alarm with **position declared lost** (the stream queue
  means up to about 40 mm of in-flight difference). It leaves the head where
  it stopped. The return to the job start belongs to the lid and interlock
  policy alone, so Stop never moves the machine on its own. Recovery: unlock
  (`$X` in Console or LightBurn's prompt), jog the head clear, and carry on in
  Current Position mode. Restart the controller with the head re-parked if you
  want a clean absolute frame.
- **Flow control.** The controller answers every line with `ok`, and its
  status report carries `Bf:` with the room left in its buffer. A line sent
  past that room is dropped whole and the job is aborted, so leave
  LightBurn's buffered streaming on. On connect the Console shows the
  controller's banner (`GrblHAL 1.1f`).
- **Two long waits are normal.** The `ok` for the line that arms the laser
  arrives after your press, and the `ok` for `$H` after the homing session.
  The status reports keep coming meanwhile, and LightBurn does not time out
  on them. Machine Settings reads `$$` whole; `$I+` in the Console lists the
  controller's build and its axes.
- **A stalled connection is dropped after a second** without progress, and
  a drop counts as a change of sender: a running job holds where the cut
  stopped and the armed window closes. Reconnect, and the resume asks for the
  button.
- **After an error, send an empty line.** The controller answers the lines
  after a refused one (a jog past the bed, a bad word) with the same error
  until an empty line or a `$` command clears it.
- **Move tab**: jogging (set a sane speed, for example 6000 mm/min), Get
  Position, distance buttons.
- **Console tab**: raw Grbl: `?` status, `$$` settings, `$X` unlock,
  `$J=G91X10F1200` jog.

## The camera

LightBurn can show the lid camera behind your design. Add it in LightBurn's
camera setup as a custom camera with the stream URL from the panel: open the
Status tab, press **Camera URL** on the lid camera card, and paste the
stream line. It reads `http://<machine-ip>/?action=stream&key=<key>`, with
no port. The key lets LightBurn read the camera without a login, whether or
not the reads are closed to the network. The camera works only with the lid
closed ([Cameras](cameras.md#watching-it)).

## Power

The controller drives the tube the way the factory does: every pulse fires at
full power, and the power setting decides how many ticks of each 710 us period
fire. Every power level marks, low levels included, because no pulse is ever
too weak to strike. The raw response is not linear (80 % of the pulses deliver
about half the light), so the controller maps your power setting through a
measured dose curve: 50 % commands half the light, not half the pulses. The
machine ships with a measured default curve; record your own tube's from the
control panel (GRBL tab, "Dose-curve recorder": download the ladder file,
press Record, run the file from LightBurn on scrap, press the button, Apply the
fit). Grayscale images fade cleanly into the shadows (a low level becomes
sparse full-power pulses), and 254 to 508 DPI rasters hold their tonal steps.

`$35`, the power floor, is set by the controller from the machine config (the
control panel's GRBL tab, "Laser dose"): do not type it, it is overwritten at
every job.

S-value scale: `$30` defaults to 1000, so set LightBurn's S-max to 1000.
100 % power = S1000. Use M4 (variable/dynamic) mode for cuts and engraves.

## Air assist and fans

Each cut or engrave layer has an **Air Assist** toggle (in the layer's cut
settings). Turning it on makes LightBurn emit `M8`/`M9` around that layer,
which drives the machine's full cut-profile ventilation: air assist to full,
exhaust and intake fans to factory run speeds, then a cooldown of about 15 s
after the layer before returning to idle. Leave it ON for anything that will
eventually involve the beam; expect real fan noise.

The machine forces the cut fan profile on while armed and continuously
verifies coolant flow; a flow fault or over-temperature pauses or blocks
firing, and the messages appear in LightBurn's console
([Cooling and fans](cooling-and-fans.md)).

## Dry runs (motion only, no fire)

**Setting a low power value does NOT make a job inert. Any laser layer prompts
for the arm button and then fires.** The motion-only modes are:

- **Frame** and jogging: they never fire.
- A job whose layers emit no laser-on command: turn the layer's **Output** off
  in the cut settings, or send G-code that stays in `M5`.
- A job run with the laser latch left locked (never press the arm button): the
  job pauses at the white-button prompt and aborts after
  `laser_button_timeout_s`. Useful only to confirm the prompt itself.

If the white arm prompt appears and you did not intend to fire, press **Stop**
in LightBurn.

## A good first job

First a dry run, then a light cut on scrap:

1. Draw a rectangle (about 100 × 60 mm) with a circle inside.
2. Double-click the layer color bar (bottom): mode **Line**, speed **50 mm/s**
   (= 3000 mm/min; check Edit, Settings for your speed units). For the dry run
   turn the layer's **Output** off.
3. Park the head where the job's rear-left corner should be (or leave it at
   home), **Frame**, watch the perimeter trace, then **Start**.

Expected behavior: darting travels at up to 200 mm/s, smooth 50 mm/s tracing
of the shapes, silky and near-silent motion (factory currents and decay mode),
and the head finishing per the job's return setting.

4. For the live pass: put scrap material on the bed (never an empty honeycomb
   over the fan grill), re-enable the layer's **Output**, set power to **20 %**
   (any nonzero power marks; 20 % is a light pass on scrap), turn the layer's
   **Air Assist** on, close the lid, **Frame**, **Start**, and press the white
   button when it lights. Watch the whole job.
