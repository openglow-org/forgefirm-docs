---
title: Troubleshooting
---

# Troubleshooting

This page collects what to do when something looks wrong: the machine's
alarms and faults, the cooling verdicts, the motion fault, and the refusals
the panel can give you.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

If anything looks wrong during a job, stop first and diagnose second: open
the lid (the hardware cuts the beam the same instant and the job cancels),
or press Stop in your sender.

## The machine will not start a controller

Before the first controller start of a session the machine makes a short test
move and confirms it with the accelerometer in the print head. If it sees no
motion it powers the motor rail down and retries with progressively longer off
periods. If the stepper drivers still will not wake, it reports a **motion
fault** instead of starting a controller: `GET /mode` reads `motion-fault`,
and the panel offers a retry (`POST /mode`). Retry from the panel. Position
counters advancing are never accepted as proof that the machine moved: the
drivers on this board can latch into a state where the counters count while
the motors produce nothing ([Modes](modes.md)).

## The lid was open at power-on

The test move needs the lid and the interlock closed. With either open when
the machine powers on (or when `forgectrl` restarts), the machine starts no
controller and waits: `GET /mode` reads `waiting` with what is open, the
panel's Status tab shows a banner, and the button blinks amber. Close the
lid (or close the interlock loop). The test move runs at once, the lens takes
its reference, and the controller starts; nothing else to do.

## GRBL mode alarms and refusals

| You see | What it means | What to do |
|---|---|---|
| The button lights white and the job waits | The job's first laser-on is waiting for your press: the armed window ([GRBL mode](grbl-mode.md)) | Check the bed and the lid, then press the button. Press Stop in your sender if you did not mean to fire. |
| Alarm 3 at the button prompt, "laser fire blocked: no head detected" | No print head is present; the machine refuses to arm without one | Seat the head, then start the job again. |
| Alarm 3 at the button prompt, a coolant message | A flow fault or an over-temperature condition stands, and arming is refused | Resolve the cooling verdict (below), then start again. |
| Alarm 3 after a long wait at the prompt | Nobody pressed within `laser_button_timeout_s` (default 300 s) | `$X` to clear, then start again. |
| The job ends with a lid or interlock message, no alarm | The lid or the interlock loop opened during the job or the button wait; the job is canceled and the head returns to where the job started | Close the lid, start the job again; the next job asks for the button. |
| The resume asks for the button again | The job sat paused past `laser_disarm_s` (default 60 s) and disarmed itself | Press the button. |
| Alarm 3 mid-job with a cooling message (`FIRE`, `CRASH`, `AIRFLOW`, `CRITICAL`) | The cooling engine's fail tier ended the job: laser locked, job reset | Resolve the verdict ([Cooling and fans](cooling-and-fans.md)), `$X`, start again. |
| The job pauses with a cooling message and resumes by itself | A pause-tier verdict held the job under the armed window and cleared | Nothing; the resume needs no press. |
| Alarm 2 before a move, after `$H` | The move would leave the bed; the limits are on after a home | Fix the job's origin or size; `^X` then `$X` clears the alarm ([Homing](homing.md)). |
| Error 15 on a jog | The jog would leave the bed after a home, or Z is unreferenced | Jog the other way; send an empty line before the next command. |
| Alarm 17, "late events while the laser is armed" | The controller fell behind real time during an armed job and stopped it rather than play the burst | `$X`, re-home, start again. If it repeats, note what else the machine was doing (a camera stream, a diagnostic). |
| The console repeats the same error for every line | After a refused line the controller answers the next lines with that error until an empty line or a `$` command clears it | Send an empty line. |
| Error 8 | A `$` command sent while the machine is busy | Wait for Idle. |
| Error 20 | The controller refuses the value or the setting | Check the setting's range; the derived settings (`$100`, `$101`, `$102`, `$32`) are not yours to type ([Settings](settings.md)). |
| Error 53 on `$H` | `homing_mode` is `switches`, which is planned | Set `homing_mode` to `gfcloud` ([Homing](homing.md)). |
| Alarm after Stop, position declared lost | A soft reset aborts with a controlled deceleration; up to about 40 mm of in-flight difference | `$X`, jog the head clear, carry on in Current Position mode; re-home for a clean absolute frame ([LightBurn](lightburn.md)). |
| Alarm with the latch relocked mid-job, "underrun" | The stream ran dry while armed: a hard fault; position is invalidated | `$X`, then re-home before you trust coordinates ([Homing](homing.md)). |
| ALARM:18 after `$H` | The homing session failed or ran past `gfcloud_home_timeout_s` (default 300 s) | Check the lid is closed and the machine has a signed-in service session; `$X` and try again. |
| Error 5 on `$H` | `homing_mode` is `none` | Set `homing_mode` to `gfcloud` or `manual` on the Machine tab ([Homing](homing.md)). |
| ALARM:11, every move refused, and `$X` answers error 9 | The X and Y motors are released (`$MD`) | Send `$ME` to energize them, or put the head in the home corner and send `$H` with `homing_mode = manual` ([Manual homing](homing.md#manual-homing)). |
| The panel's position is red | The machine is unreferenced; coordinates are relative to where the head was | Normal. Use Current Position mode, or `$H` ([Homing](homing.md)). |
| Your sender disconnects when another program connects | Only one Grbl connection is meaningful; a second one displaces the first | Close the other client. Never point a status poller at port 23. |
| Your sender is dropped mid-job | It stopped reading for a second (a busy network, a frozen program); a drop is a sender change, so a laser job holds and the window closes | Reconnect; `~` lights the button and a press resumes the job. |
| The controller exits when you send `^F` | `^F` (0x06) asks the controller to shut down cleanly: it stops motion, relocks the laser and exits, and the daemon starts it again | Nothing; wait for the reconnect. |
| The controller does not start, and the sender cannot connect | The machine is in cloud mode, or a motion fault stands | Check the Status tab's controller mode and state ([Modes](modes.md)). |

A spindle `$` setting that does not seem to take: the mapping in force is the
one loaded at controller start; `$$` reports the new value at once. Restart
the controller (a mode switch away and back, or a reboot). A baked default that
does not appear: stored settings win; `$RST=$` restores the defaults
([Settings](settings.md)).

## Cooling verdicts

The cooling engine publishes one verdict at a time, and the active controller
enforces it. Your sender shows the hold state and a warning message; the panel's
Status tab and `GET /cool/status` show the verdict.
[Cooling and fans](cooling-and-fans.md) has the table of what the machine does
when; this is what you do.

| Verdict | What you see | What to do |
|---|---|---|
| `SUSPECT` | A warning and a hold; the machine re-checks flow at once | Wait. A clean re-check resumes the job by itself. Expect one on the first checks after you stop and start the pump by hand: that is an airlock, and it clears. |
| `FAULT` | Fire gated, the hold stands | Check the pump, the lines, and the coolant level. Run **flow verify** on the Diagnostics tab; if the threshold no longer suits the loop, run **flow calibrate** ([Diagnostics](diagnostics.md)). |
| `OVERTEMP` | A hold with the cooling airflow forced on | Wait. The job resumes by itself once the upstream coolant is under the resume gate (31 °C by default). A jog is canceled instead of held. |
| `CRITICAL` | Fire blocked, hold, no resume for the rest of the job; a resume under it is held again | Reset the job and let the loop cool. The next job judges the line afresh. A loop that ran through the pause tier and kept climbing needs looking at. |
| `COLD` | Fire blocked; the coolant is under the floor | Let the room and the machine warm up. The gate clears a degree above the floor. |
| `WARMUP` | The job holds with the loop heater on and the fans idle | Wait for the coolant to reach the warm-up gate; the job then runs and verifies flow. |
| `SENSOR` | Fire blocked, hold; the reason names the coolant sensor the machine cannot read | Wait a moment: a passing read failure clears by itself and the job resumes. One that stands means the sensor or its wiring needs looking at; the coolant readings on the Status tab show which one is missing. |
| `AIRFLOW` | Fire blocked, hold, no resume for the rest of the job; a resume under it is held again; the reason names the fan, the reading, and the floor | Reset the job and check that fan. The next job judges every fan afresh after the spin-up grace. A fan that reads differently from the shipped floor on a healthy machine gets its own floor on the Machine tab. |
| `FLAME` | Hold, fire blocked, while a lid-IR reading is over its alert | Look at the bed. The hold releases when the reading is back under the alert. |
| `FIRE` | Motion stopped, laser locked, the smoke airflow held; no resume until the next job | Deal with the fire. The fire watch is not a fire alarm: never leave a running laser unattended. |
| `BUMP` | Hold, fire blocked, after a knock past the head accelerometer's alert | Check that the head is clear; the hold releases once the head sits quiet. |
| `CRASH` | Motion stopped, laser locked, for the rest of the job | Check the head and the gantry for a collision before the next job. |

Three cleared suspicions in one job earn an aggregated "check your coolant"
warning: look at the loop before the next job.

## The panel refuses something

| You see | Why | What to do |
|---|---|---|
| Settings cannot be saved (409); the controls are disabled with a banner | The machine is not idle, or a diagnostic is running | Finish or stop the job, or wait for the diagnostic to end. |
| The mode switch is refused | The switch is idle-gated: no job, no diagnostic | Wait for idle. |
| A standing banner says a gate is off | A cooling gate setting sits at the off end of its range | Intended if you set it. Otherwise set the value back ([Cooling and fans](cooling-and-fans.md)). |
| A field is flagged outside its recommended band | The value is legal but outside the band measured on the bench reference | Fine if your machine's loop or fans read that way. |
| A compatibility warning in cloud mode | The Glowforge service has moved past the firmware version cloud mode is tested against | Cloud mode may still work; watch for changed behavior. Update ForgeFIRM when a newer release exists. |

## Cloud mode

- **The app cannot focus, or homing fails.** The lid is open. With the lid
  open nothing moves and nothing captures. Close the lid
  ([Cameras](cameras.md)).
- **The service stalls silently mid-sequence.** After an abnormal end of an
  earlier session the service can stall in the next one. A fresh session
  recovers it: stop and start the controller (a mode switch away and back does
  it).
- **The machine hunts every time it connects.** That is the service's
  connect-time hunt; it is deliberate on a fresh start
  ([Cloud mode](cloud-mode.md)).
- **The socket drops about once an hour.** Routine; the client reconnects on
  its own.
- **Coordinates are wrong after switching back to GRBL mode.** Connecting to
  the service zeroed the counters. Re-home ([Homing](homing.md)).

## Cameras

[Cameras, When something looks wrong](cameras.md#when-something-looks-wrong)
covers a 409 that names the lid, a black picture, a stream that stops, a
camera switch timeout, a 503 on a snapshot, and an unknown sensor.

## Getting help

Export a **sanitized log bundle** from the Logs tab and attach it to your
report ([Logging](logging.md)); skim it first. The community forum is at
[community.openglow.org](https://community.openglow.org).
