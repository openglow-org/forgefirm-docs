---
title: Cooling engine
---

# Cooling engine

The cooling engine is the part of forgectrl that owns every piece of thermal
hardware (fans, pump, TEC, and the flow-check heater) and answers one
question at a time for whichever controller is running: *is it safe to fire
right now?* This page describes how it decides: the two client channels, the
fan phases and the airflow gates, coolant flow verification, the temperature
gates, the fire watch, and the gate settings.

What the hardware is (the loop, the fans, the sensors) is on
[Coolant and airflow](../machine/coolant-and-airflow.md). What the operator
sees and tunes (the settings reference, turning a gate off, the quick
reference of what the machine does when) is on
[Cooling and fans](../../usage/cooling-and-fans.md). The operator procedure
for the flow diagnostics is on [Diagnostics](../../usage/diagnostics.md).
The beam itself is gated in hardware
([Safing chain](../machine/safing-chain.md)).

The engine lives in forgectrl (`src/cool.c`, the gates in `src/gates.c`, the
airflow gates in `src/airflow.c`, the crash watch in `src/accel.c`).
Tunables are the `cool_*` keys in the shared machine settings, re-read at
every run start, with `GFCOOL_*` environment overrides for bench work.
`GET /cool/status` reports the engine state for the UI and bench tooling.

## One owner, two clients

The cooling engine is the **only** thing that writes fans, pump, TEC, and
heater. Whichever controller is running, GRBL or cloud, is a client of it,
over two channels:

- **The controller reports its job state** about once a second: idle,
  running, or cooling down, whether the laser is armed, and (in cloud mode)
  the fan duties and the limits the job asks for. The reports are
  level-triggered, so a lost one corrects itself on the next
  ([Job-state reports](#job-state-reports)).
- **The engine publishes a verdict** the controller reads and enforces in
  its own process: may the laser fire, should the job hold, may it resume
  ([The verdict file](#the-verdict-file)).

Both controllers write no thermal hardware except through the emergency
fallback described under the verdict file. Properties of that split:

**A missing verdict is a bad verdict.** If the verdict is absent or more
than two seconds old, a controller treats it as *fire blocked, hold*. The
engine going away looks exactly like a fault, never like permission.

**Arming requires being seen.** The engine only grants fire when it is
receiving fresh job reports. A controller about to fire is, by contract, one
that is reporting. An armed window the engine cannot see never gets a green
light.

**If a controller goes silent** past five seconds, the engine blocks fire
immediately and stands the machine down through the normal cooldown, because
a smoke clear is the right physical response to a job that died mid-cut. If
the silence happens while the laser is armed, or while the pulse engine
still says a program is playing, the engine additionally stops motion and
locks the laser latch itself. It also refuses to let exhaust and intake drop
below cooldown duty while a program is still running. A controller the
supervisor stops on purpose does not count as silent: the supervisor clears
the last report at the stop, and the engine has no reporter until the next
controller speaks, so the supervisor's own liveness probe plays unwatched.

**A cloud job brings its own envelope.** The pulse file the Glowforge
service sends opens with the job's operating limits, and the cloud client
hands the ones the engine has a use for along with every report: the coolant
window and the fans' minimum speeds. The engine takes each only where it is
stricter than the setting on the Machine tab: a ceiling can only come down
for a job, a floor can only go up, a looser value is noted in the log and
ignored, and a gate the operator turned off stays off whatever the job says.
The coolant ceiling is the one limit a job tightens in practice (the service
sends 33 °C on a cut, which is also the shipped default); the fan floors
feed the airflow gates. The effective set shows in the log as
`effective limits:` and in `/cool/status` as `limits`. A GRBL job has no
header and runs on the settings alone.

**If a diagnostic takes the hardware over**, the engine suspends its own
writes and publishes fire-blocked until the diagnostic finishes
([Diagnostics: verifying and calibrating flow](#diagnostics-verifying-and-calibrating-flow)).

**If the engine itself is provably gone** while the laser is armed, the
controller writes the factory run duties to the fans once, holds the job,
and stands down. That is the single sanctioned exception to single-owner
control, and the duties are compiled in so that a lost configuration file
cannot take the fans with it.

## What the fans do, and when

The engine runs in phases. Duties are the factory machine's own values.

| Phase | Pump | Air assist | Exhaust | Intake | Heater |
|---|---|---|---|---|---|
| **Idle** | on | 204 | off | off | off |
| **Warm-up hold** (a session opened under `cool_temp_start`) | on | idle | off | off | on |
| **Run** (or armed, whatever the reported mode) | on | 1023 | 65535 | 43278 | flow checks only |
| **Cooldown, smoke clear** (15 s) | on | run duty | run duty | run duty | off |
| **Cooldown, thermal** | on | idle | 32768 | 21639 | off |
| **Over-temp or fault hold** | on | run duty | forced | forced | off |

Notes on the phases:

- **The pump runs whenever the machine is on**, including at idle.
  Circulation is cheap; a stagnant loop with a warm tube is not. The one
  exception is the quiet hold below, an idle-only listening with the laser
  latched.
- **The heater is off at idle by design.** An always-on flow heater
  measurably warms the loop within minutes, eating headroom below the start
  gate for no benefit while nothing can fire. The warm-up hold is the one
  phase that runs it for heat
  ([Low temperature](#low-temperature-the-floor-and-the-warm-up-hold)).
- **Being armed counts as running.** If the laser is armed, the engine
  forces the run profile and the flow checks regardless of what mode the
  controller reported. Fire never happens without cut airflow and active
  flow verification.
- **Cooldown has two stages**: a smoke clear at full run duty, then reduced
  airflow (the radiator cools the loop measurably) until the upstream
  coolant temperature is back under the resume gate or the cooldown budget
  expires. A run session that never had the armed window open (a homing
  motion, a hunt, a dark job) has no smoke to clear: its smoke phase is zero
  length and the cooldown goes straight to the thermal gate and the idle
  profile.
- **The TEC** is driven only when the operator declares one present
  ([The TEC](#the-tec)).

In **GRBL mode** the run profile follows the sender's `M8`/`M9` (LightBurn's
per-layer Air Assist), OR'd with the armed window. In **cloud mode** the
job's own header carries the duties and the client passes them through, so a
print gets the fan profile the service designed for it and a lens hunt stays
quiet.

**The quiet hold.** A listening to the head accelerometer wants the machine
quiet, because a running fan or pump is in the reading. The commissioning
focus card's stop finder takes the engine's quiet hold for its listening:
the air assist, exhaust, intake and purge fans off whatever the phase says,
the pump still running (the finder was proven that way). The bench tools
take the same hold through `POST /cool/quiet?on=1`, and with `pump=1` the
coolant pump and the TEC go off as well, so the machine is silent: the one
pump-off state besides the heater-only flow diagnostics, and a dry one,
since the laser stays latched at idle. Release with `on=0`;
`GET /cool/status` shows the hold as `quiet_hold`. The hold is taken only
from an idle machine with no diagnostic running, and the engine releases it
itself the moment a run session opens or after 600 s, so a job never runs
with the machine held quiet and a listener that died cannot leave it so.

### Airflow gates: a fan that is not moving the air

Commanding a fan and getting airflow are two different things, and the
machine can tell them apart: the exhaust, the two intakes, and the air assist
carry tachometers, and the purge-air fan in the head reports its current.
While the run profile is applied, the engine holds every one of them to a
floor, each floor the effective one (a header's tach window can raise it for
a job).

- **The floors** are settings: `cool_tach_exhaust_min_rpm`,
  `cool_tach_intake_min_rpm` (either intake), `cool_tach_air_assist_min_rpm`,
  and `cool_purge_min_current`. Each ships at 55 percent of the steady speed
  that fan reaches at the cut profile on the bench reference (the measured
  speeds and spin-up times are on
  [Coolant and airflow](../machine/coolant-and-airflow.md#what-the-fans-actually-reach)),
  with a recommended band of 50 to 60 percent. The commissioning airflow check
  measures a machine's own and writes them. A cloud job's header can raise a
  tach floor for that job, never lower it.
- **A fan is judged at the operating point where its floor is measured.**
  While the laser is armed every fan is judged, and a job's own fan profile
  (a cloud header's run duties, via `POST /cool/state`) may raise a fan
  above the cut profile but never lower it while armed. Unarmed, a fan is
  judged whenever it is commanded at or above the cut profile (a bare `M8`
  from a GRBL job), and a fan the job runs slower is measured, published as
  `unjudged`, and not judged: the factory's hunts and homing moves run with
  the exhaust and the intakes off and the air assist at idle, and nothing
  can fire during them. The purge fan has no duty (it is on whenever the
  machine is not held quiet for a listening) and is judged in every run.
- **A spin-up grace** (`cool_fan_grace_s`) runs from the moment the run
  profile is written, and again when a fan is commanded faster mid-run (the
  armed window opening raises a lowered fan). Nothing counts inside it,
  because the big exhaust fan takes seconds to reach speed.
- **Every fan duty written is read back.** The head's air-assist register
  and the two thermal PWMs report the duty in force, so the engine reads
  each write back, tries a write that did not take three times, and names
  one that never took in the log. Once a tick it reads the three duties
  back against what it commanded and puts back a duty a device lost (a
  head reset, a dropped transaction), with the spin-up grace again for a
  fan raised back, up to three times a session. A device that keeps
  losing its duty is judged at its tach like any other fan. The airflow
  fault names the duty commanded and the duty in force beside the reading,
  so a fan that never got its duty reads as that, not as a slow fan.
- **The first fire waits for the fans.** The engine acknowledges the
  armed window (`armed` in the verdict) only once every gated fan reads at
  or above its floor, and the controller waits for that acknowledgment
  before it opens the window: the button lights, the fans come up, then
  the beam. The controller's wait is the grace plus 5 s; an
  acknowledgment that never comes refuses the arm (`ALARM:3`, "the
  cooling service did not take the job"), which is what a fan that cannot
  reach its floor looks like.
- **Three consecutive 1 Hz ticks under the floor trip the gate**, and a
  single reading at or above it in between clears the count, so a tach
  reading that wanders does not end a job.
- **A trip is a fault, not a pause.** The verdict goes `AIRFLOW`,
  `fire_ok=false`, `hold=true`, and there is no `resume_ok` for the rest of
  that run session: a fan that has stopped moving air is not a condition to
  cut through. The fans stay at run duty (a stalled extraction fan needs
  every other fan around it running), and the reason names the fan, the
  reading, and the floor. The fault ends with the session (logged): at idle
  the verdict is `OK` again (a standing hold would cancel jogs and refuse
  the next job before it could re-prove the fan), and the next session
  judges every fan afresh after the grace.
- **A floor of zero is that gate off.** It still measures: the first
  reading in a job that would have tripped the shipped default is logged.

Outside a run the gates read `idle`. `/cool/status` carries each fan's
`reading`, `floor`, and `state` (`grace`, `ok`, `under`, `TRIPPED`, `off`,
`unjudged`, or `idle`) as `fan_gates`.

## Coolant flow verification

### The problem

A pump can stop, an impeller can slip, a line can airlock, and none of it
shows up in a temperature reading until the tube is already in trouble.
Absolute coolant temperature only tracks a loop that is *circulating*, and
"coolant should warm up while cutting" is not a usable signal either: a
light engrave may add no measurable heat at all.

### The method

The small heater sits between the two thermistors. Each check runs it at a
fixed duty for a fixed window and watches how far the **downstream** sensor
climbs:

- **flowing coolant carries that heat away**: the downstream sensor rises a
  little;
- **a stagnant loop cooks the sensor**: the downstream sensor rises a lot.

The discriminator is the rise, not the difference between sensors, and the
operating point is measured rather than assumed:

| Parameter | Value | Why |
|---|---|---|
| Heater duty | 40 % | Below about 40 %, natural convection sheds the heat well enough to *mimic* flow: dead-pump trials have looked healthier than a working pump. At 40 % heat input outruns convection, and it is the cheapest duty that does. |
| Window | 50 s | Long enough for the bands to separate cleanly. |
| Fault threshold | 14.4 °C rise | Midway between the observed flowing band and the observed stagnant band. |
| Re-check interval | 150 s | A pump that stops mid-job is invisible otherwise. |

The derivation of the operating point, from a 60-run design matrix, is on
[The bench](../../developers/bench.md#how-the-coolant-flow-fire-gate-threshold-was-derived).

Each check costs the loop under a degree of heating, and with cut-profile
fans running the loop still nets cooler over a long job.

**The record behind the operating point**, all on the bench reference: 25 of
25 correct classifications at 40 percent duty, plus all three settle cases.
The bands hold across the loop temperatures a real machine sees, with the
margin widening as the loop warms:

| Baseline | Flowing, worst | Stagnant, worst | Gap |
|---|---|---|---|
| 19 to 23 C | 12.75 C | 16.04 C | 3.3 C |
| 24 to 25 C | 12.15 C | 18.07 C | 5.9 C |
| 26 to 27 C | 11.89 C | 18.00 C | 6.1 C |

A warmer loop sheds the heater's heat no worse with the pump on and holds it
better with the pump off, so the threshold needs no warm-end value through
27 C. Above that only a running tube warms this loop, and the check takes the
tube's share off (below).

### Checks start from a settled loop

Measuring a rise from a baseline captured while the loop is still cooling
from earlier heat produces garbage, and it fails in the dangerous direction:
it can report flow with the pump stopped. So a check is *requested*, and
starts only once the two sensors agree within 1.5 °C **and** the downstream
reading has stopped drifting.

Stationarity is judged by comparing the mean of the first half of a
15-second window against the second half, not by peak-to-peak spread. On a
settled loop, peak-to-peak noise is about 0.5 °C while the split-half
difference is about 0.1 °C. Any peak-to-peak threshold tight enough to catch
real drift would sit below the noise floor and never open the gate.

### The tube's share of the rise

Under laser load the tube itself heats the coolant, and that heat would read
as a stagnant loop. It is the right size to matter: on the bench reference a
**fully lit 50 s check window adds about 1.5 C** to the rise, against a margin
of about 1.6 C, and about 0.46 C at 45 percent density. The heat arrives 10 to
20 seconds after the first emission, as a smooth ramp on both sensors
together, never as a step at fire start. Left uncorrected, a check that
overlaps a cut reads about 14 C where the same loop reads 11.7 to 12.1 C dark,
which is a hair from a false suspicion.

Two tunables ride with the flow gate and are not gates:
`cool_laser_heat_cw` and `cool_laser_heat_density`, the tube's share of a
heater rise in °C per raw-second of `pic/hv_current` under each power model
(defaults 3.06e-5 and 2.36e-5, legal 0 to 2e-4; the commissioning sheet's
flow-load card measures them, with the check held for the card so the
heater does not swamp the tube's share: `cool_flow_check_hold`, released
at the run's end or after ten minutes whatever happens). The model the controller
reports with its job state selects which applies (density, on every
machine), and density is assumed when the report carries none. The check
reads its baseline as the mean of the settled window the gate verified and
its end as the mean of its last 5 s, never single samples. It counts the
tube current from 15 s before the window to 15 s before its end (the heat's
lag to the sensor), subtracts that share from the rise, at most 3 °C, and
judges the remainder against `cool_flow_rise`. The verdict line carries the
share taken off and the raw rise.

### The air-assist offset on the coolant readings

A third tunable rides with the coolant readings themselves:
`cool_aa_offset_counts` (ADC counts, default 0, legal 0 to 60). It corrects
the shift the air-assist fan's return current puts on both coolant sensors,
about 20 counts or 1.2 °C at the run duty on the bench reference; the
mechanism and its measurement are on
[Sensors](../machine/sensors.md#three-things-that-move-a-coolant-reading-and-are-not-temperature).
The engine commands that fan, takes the setting's
share off both raw readings before the conversion at every tick (more counts
read colder, so the lift reads as a drop), and `/status` applies the same
correction, so the over-temperature gates and the panel read the coolant as
it is. The value is the machine's own: the `aa-offset-calibrate` diagnostic
(the fan stepped idle to run and back three times, tube dark, heater off,
the step on both sensors at every edge read as the difference of two 3 s
windows, each the interquartile mean of 48 samples, so the rare excursion
a sample carries falls out; the module itself keeps the CPU busy before
every PIC transaction, so a reading no longer depends on whether the reader
had just woken) recommends it and the panel's Apply writes it. Zero, the default, is the factory behavior, which
never corrected the shift.

### One bad reading is a suspicion, not a fault

Transients happen: cycling the pump by hand can burp an airlock that clears
itself within minutes. So the engine runs a two-step decision:

1. **First over-limit check: `COOLANT FLOW SUSPECT`.** A warning, a hold
   request, and an immediate re-check, with no waiting for the normal
   cadence.
2. **The next completed check decides.** Over-limit again, with no clean
   check in between: `COOLANT FLOW FAULT`. Clean: the suspicion clears and
   the job continues.

Two more rules close the loopholes:

- **A suspicion that cannot resolve escalates.** If no verdict can be
  produced within the confirmation budget (default 480 s), it becomes a
  fault: a loop that will not settle after a fault-level reading has shown
  no evidence of health.
- **Cleared suspicions still count.** Three of them in one job earn an
  aggregated "check your coolant" warning; the counter resets when cooldown
  reaches idle.

A clean check from the fault state logs a recovery.

Expect a legitimate suspicion on the first checks after manually stopping
and starting the pump. That is an airlock, the machinery above absorbs it,
and it clears on its own.

### What the verdicts do

| Verdict | Effect |
|---|---|
| `OK` | Fire permitted. |
| `SUSPECT` | Hold requested, cut airflow held; auto-resumes on a clean re-check. |
| `FAULT` | Fire gated and the hold stands, for the operator to resolve. |
| `OVERTEMP` | Hold with forced cooling airflow; auto-resumes below the resume gate. |
| `COLD` | The coolant under `cool_temp_min`: fire blocked, hold; back a degree above it. |
| `WARMUP` | A session opened under `cool_temp_start`: held with the loop heater on and the fans idle until the gate is reached, then run with the flow check requested. |
| `CRITICAL` | The coolant at or over the critical line in a run session: fire blocked, hold, no resume this job. |
| `SENSOR` | A coolant sensor unreadable for two ticks in a row: fire blocked, hold, heater off; released the moment both sensors read again. The other coolant gates keep their state while the engine is blind. A flow check in flight is abandoned and asked for again; a warm-up gets its heater back. |
| `AIRFLOW` | A fan under its floor: fire blocked, hold, no resume this job. |
| `FLAME` | The fire watch's pause tier: hold, fire blocked; released when the reading clears. |
| `FIRE` | The fire watch's fail tier: motion stopped, latch locked, hold until the next run session. |
| `BUMP` | The crash watch's pause tier: hold, fire blocked; released once the head sits quiet. |
| `CRASH` | The crash watch's fail tier: motion stopped, latch locked, hold for the rest of the run session. |

## Over-temperature

The engine uses the factory's coolant windows:

- **Run ceiling 33 °C** (`cool_temp_max`): above this, the verdict goes
  `OVERTEMP` with a hold request and cooling airflow forced on.
- **Resume gate 31 °C** (`cool_temp_resume`): below this, recovery is
  signaled and the controller resumes automatically. It is always kept
  below the ceiling, and when a header tightens the ceiling the resume gate
  follows it down by the configured gap.
- **Critical line 38 °C** (`cool_temp_critical_c`): a second tier above the
  ceiling, and a different kind. At or over it during a run session the
  verdict goes `CRITICAL`, fire is blocked, the job holds, and there is no
  resume for the rest of that session, because a loop that ran through the
  pause tier and kept climbing is not a condition to cut through. The fault
  ends with the session; the ceiling's pause keeps holding while the loop is
  hot, and the next session judges the line afresh. A cloud job's header
  carries no critical line for the coolant, so this one is always the local
  setting. The settings API keeps it above the ceiling while the ceiling is
  a gate (a ceiling at its off end leaves the line standing alone), and at
  its top (70 °C) it is the gate turned off.

The **upstream** sensor gates, because it reads the coolant actually
entering the tube.

What the operator sees depends on what the machine is doing. A running
cycle takes a feed hold and resumes by itself once the loop recovers; the
sender shows the hold state and a warning message. A jog is canceled instead
(a jog cannot be held). Fire stays gated for the whole excursion.

## Low temperature: the floor and the warm-up hold

Two gates sit below the operating window:

- **The floor** (`cool_temp_min`, default 5 °C) is a fire gate: coolant
  under it reads `COLD`, fire blocked, hold; the gate clears 1 °C above
  itself. A header floor can only raise it. At 0 the gate is off.
- **The warm-up gate** (`cool_temp_start`, default 16 °C, kept above the
  floor): a session that opens under it holds with the loop heater on and
  the fans idle until the gate is reached (verdict `WARMUP`, phase `warm-up`
  in `/cool/status`), then runs with the flow check requested. At 0 the gate
  is off.

  **The release judges a one-minute rolling minimum of the upstream reading,
  not the instant one.** With the pump running, a slug of the heater's output
  reaches the upstream sensor within seconds and lifts the instant reading by
  a degree, while the bulk warms about half a degree a minute; releasing on
  the instant reading let a hold end in eleven seconds with the loop still
  cold. Between slugs the rolling minimum falls back to the bulk, which is
  the number that matters.

  The hold has no time limit by design. The heater plateaus 8 to 9 C over
  ambient, so a loop that stops warming short of the gate is named once and
  keeps holding: a shop more than about 8 C below the gate needs the gate
  lowered or the room warmed.

### The TEC

`thermal/tec_on` is a bare output with no readback, so presence cannot be
detected. The TEC is driven only when `cool_tec_present` is `1` (the
Machine tab's "TEC (Pro chiller)"; default `0`, and ForgeFIRM never touches
the line otherwise). It is the operator's word, which also covers retrofits.
When present: hysteresis on the upstream reading, on above `cool_tec_on_c`
(default 20 °C), off below `cool_tec_off_c` (default 18 °C), and only while
the fans run (the run, smoke-clear, and thermal phases, or a forced
cooldown), because the cooler's heat sink sits in their airflow. Off at
idle, off in the warm-up hold, off within a degree of the coolant floor.
Turning off is immediate; turning on waits a 30 s dwell after the last
switch so sensor noise cannot chatter the part. The factory drives a Pro's
TEC above its own threshold on the filtered upstream reading; what a Pro
sets is unknown (no Pro capture), so the defaults here are chosen, not
inherited.

## Diagnostics: verifying and calibrating flow

The web panel's **Diagnostics** tab runs the two cooling tools. The
operator procedure is on [Diagnostics](../../usage/diagnostics.md); this
section is the method.

Both tools take the hardware over: the active controller is suspended for
the duration, the engine stands aside, and the controller is restored on
every exit path (completion, error, or Abort). The laser stays latched
throughout. Progress, both coolant temperatures, and a scrolling log stream
to the page while a tool runs.

A diagnostic owns the thermal hardware between `cool_diag_take` and
`cool_diag_release`. Take succeeds only from an idle engine, every tool
write goes through the engine's guarded diag helpers (one owner), the tick
publishes phase `diag` with `fire_ok=false, hold=true` and touches nothing,
and the release reasserts the idle posture in one place.

Both tools run at the *configured* duty, window, and threshold, so the
verdict applies to the check the machine actually performs, and both use
cut-profile chassis fans, the condition under which the numbers are
characterized. Any pump-off window aborts immediately if the downstream sensor
passes 48 °C.

**Flow verify** runs one check with the pump running and one with it
commanded off, and passes when the threshold separates the two readings.
**Flow calibrate** runs three trials of each case, alternating, with settle
gates between them, and recommends a threshold midway between the highest
flowing reading and the lowest stagnant one; it refuses to recommend anything
when the gap between the bands is under 3 °C, because a threshold in a narrow
gap is a threshold that will misclassify.

The operator's procedure, what each result means and when to run either is on
[Diagnostics](../../usage/diagnostics.md).

## The fire watch

Alongside the flow work, the engine runs the physical-evidence witnesses at
its 1 Hz tick.

- **Emission evidence.** `cnc/laser_on_sampled` counts the last ~1 s
  window's emitting samples on the gated output of the hardware AND-gate:
  evidence, not a commanded state. Emission with no armed window in the
  recent past gets the hung-controller treatment (`cnc/stop` +
  `cnc/laser_latch=1`, repeated while the evidence persists).
- **Laser supply power-good** is watched during an armed window: when fewer
  than half of the last second's samples read good, the engine warns once per
  session. On a healthy supply the line is good in every sample, so the
  warning means the supply's supervisor reported a fault.
- **Lid IR fire watch.** The four `pic/lid_ir_*` channels are polled every
  tick; each job logs its baseline and peaks (the characterization dataset).
  The channels are first of all a photometer for the lid lamp, and a cut and
  a candle move them by the same few counts, which is what shapes this watch:
  the measurements are on
  [Sensors](../machine/sensors.md#lid-ir-sensors-piclid_ir_1-to-piclid_ir_4).
  Through the run, smoke, and
  thermal phases the four readings sorted ascending (the quartiles, the
  factory's statistic) are judged against two tiers per quartile, the
  factory's own shape. A first or second quartile over its alert threshold
  for two ticks is the pause tier (verdict `FLAME`, `hold`, fire blocked;
  released once the reading is back under the alert for five ticks). Over
  its critical threshold is the fail tier (motion stopped, latch locked,
  verdict `FIRE` with `hold` until the next run session, smoke-clear airflow
  held). The defaults are the thresholds the factory ships in every pulse
  header (quartiles three and four it leaves at zero). They sit far above a
  fully lit lid lamp, so the lamp never trips them, and a candle-sized flame
  stays under them too: this catches a developed fire. Zero turns a tier
  off. The header's own `IR??` values stay declared-ignored by the cloud
  client; the knobs are local. `/cool/status` carries the watch state as
  `fire_watch: watch | armed | alert | ALARM`.
- **Head-accelerometer crash watch** (`src/accel.c`): the factory's own
  mechanism, the head LIS2HH12's two on-chip interrupt generators, armed
  over i2c-dev (`I2C_SLAVE_FORCE`) while `st_accel` stays bound and polled
  at the 1 Hz tick (the sources latch, so a poll misses nothing). IG1 takes
  the per-axis X and Y alert thresholds (the pause tier: verdict `BUMP`,
  hold, fire blocked; released after five quiet polls). IG2 takes the shared
  abort threshold (the fail tier: motion stopped, latch locked, verdict
  `CRASH` with `hold` for the rest of the run session). Thresholds are IG
  register units at the ±4 g run full scale, so 1 g is about 64; the defaults
  are the factory's own header values, about 2 g, far above normal commanded
  motion. Z is never armed: gravity rides it, and the factory ships Z zero
  too. The registers, the threshold scale and the factory's own values are on
  [Sensors](../machine/sensors.md#the-head-accelerometer).
  The watch arms only inside the laser's armed window. The liveness probe and
  cloud homing read the accelerometer through `st_accel` in unarmed sessions,
  and the armed watch owns the part's ODR and full scale (`st_accel` leaves it
  powered down between one-shots; the watch sets 800 Hz and ±4 g, re-asserts
  them every poll, and restores what it found on disarm). A head that stops
  answering stands the watch down for the session, said once.
  `/cool/status` carries the watch state as
  `accel_watch: off | watch | armed | alert | ALARM` (`off` = the part
  absent or not answering; `watch` = thresholds set, window not armed).
- **Telemetry.** `cnc/faults` transitions to nonzero during a run window
  are warned; `pic/hv_current` (the only live HV telemetry) is ranged per
  job in the same log line. The chassis, SoC die, and supply temperatures
  are ranged over every run session and named once at its end
  (`cool: temps this job: chassis 24.1..31.8 C, soc 42.8..61.0 C, supply raw 401..455`,
  with `CPU THROTTLED for N s` appended when the kernel's thermal governor
  throttled the CPU during the job). No gate stands behind any of them
  ([Planned](#planned)). The SoC guards itself: the i.MX6 thermal zone
  throttles the CPU (and the GPU) at its passive trip and powers the board
  off at its critical one; the engine names a throttle when it starts and
  when it ends (`SoC throttled: CPU cooling state N (die T C)`). `/status`
  exposes the sampled laser evidence, faults, HV, and lid IR values.

!!! danger "The fire watch is not a fire alarm"

    The lid IR tiers catch a developed fire, not a small flame. Never leave
    a running laser unattended.

## Gate settings: range, band, off end

A gate is a comparison the engine makes against a setting. Every gate
setting is a plain number on the Machine tab, and there is no separate
switch for any gate: the one table in `src/gates.c` gives each its **legal
range** (wide on purpose), its **recommended band** (the shipped default
with the margin one machine's loop needs), and its **off end**,
the end of the legal range at which the gate never trips. A value outside
the band is legal and warned about; a value at the off end is legal and
reported as the gate being off. The validators, the engine, the settings
reply, and the panel all read that table. The operator's settings reference
is on [Cooling and fans](../../usage/cooling-and-fans.md).

| Key | Gate | Default | Legal | Recommended | Off at |
|---|---|---|---|---|---|
| `cool_temp_max` | `coolant_max` (the run ceiling) | 33 °C | 5 to 60 °C | 25 to 38 °C | 60 °C |
| `cool_temp_resume` | (follows the ceiling; kept below it) | 31 °C | 5 to 59 °C | 20 to 36 °C | never |
| `cool_temp_critical_c` | `coolant_critical` (the fail tier above the ceiling; kept above it while the ceiling gates) | 38 °C | 6 to 70 °C | 36 to 45 °C | 70 °C |
| `cool_temp_min` | `coolant_min` (the floor, a fire gate; clears 1 °C above itself; a header floor can only raise it) | 5 °C | 0 to 40 °C | 3 to 8 °C | 0 |
| `cool_temp_start` | `warm_up` (a session opening under it holds with the heater on until it is reached; kept above the floor) | 16 °C | 0 to 40 °C | 12 to 20 °C | 0 |
| `cool_tec_on_c` | (the TEC's on threshold; kept above `cool_tec_off_c`) | 20 °C | 6 to 32 °C | 18 to 24 °C | never |
| `cool_tec_off_c` | (the TEC's off threshold; the runtime clamp holds the TEC off within a degree of the floor) | 18 °C | 5 to 31 °C | 16 to 22 °C | never |
| `cool_fire_q1_alert` | `flame_q1_alert` (lowest sorted lid-IR reading; pause tier) | 275 | 0 to 1023 | 250 to 450 | 0 |
| `cool_fire_q1_critical` | `flame_q1_critical` (fail tier; kept above the alert) | 688 | 0 to 1023 | 500 to 1023 | 0 |
| `cool_fire_q2_alert` | `flame_q2_alert` (second-lowest sorted reading; pause tier) | 374 | 0 to 1023 | 300 to 500 | 0 |
| `cool_fire_q2_critical` | `flame_q2_critical` (fail tier; kept above the alert) | 1022 | 0 to 1023 | 500 to 1023 | 0 |
| `cool_accel_x_alert` | `crash_x_alert` (head-accel X high event; pause tier) | 132 | 0 to 255 | 100 to 170 | 0 |
| `cool_accel_y_alert` | `crash_y_alert` (head-accel Y high event; pause tier) | 112 | 0 to 255 | 85 to 145 | 0 |
| `cool_accel_abort` | `crash_abort` (head-accel shared abort; fail tier) | 133 | 0 to 255 | 100 to 170 | 0 |
| `cool_flow_check_s` | `flow` (flow verification) | 50 s | 0 to 300 s | 30 to 120 s | 0 |
| `cool_flow_rise` | (tunes `flow`; set from flow calibrate) | 14.4 °C | 1 to 40 °C | 8 to 16 °C | never |
| `cool_tach_exhaust_min_rpm` | `exhaust` | 6400 rpm | 0 to 20000 | 5800 to 7000 | 0 |
| `cool_tach_intake_min_rpm` | `intake` (either tach) | 2290 rpm | 0 to 20000 | 2100 to 2500 | 0 |
| `cool_tach_air_assist_min_rpm` | `air_assist` | 6000 rpm | 0 to 30000 | 5500 to 6600 | 0 |
| `cool_purge_min_current` | `purge` (current, raw) | 300 | 0 to 1023 | 150 to 500 | 0 |
| `cool_fan_grace_s` | (the spin-up window, no gate) | 15 s | 0 to 120 s | 5 to 30 s | never |

**What an off gate does:** the engine skips the comparison (no verdict, no
hold from it) and keeps measuring. With `coolant_max` off, the first reading
in a run session over the shipped default is logged once as what the gate
would have done; with a fan floor off, the first reading under the shipped
default likewise; with `flow` off there is no heater interrogation at all
and the run start says so. A header limit never overrules an off gate.

**What an off gate is not:** a way to reach anything that is not a thermal
gate. The hardware chain, the laser latch, the emission witness, the
controller-silence dead-man, and the motion-liveness gate are not numbers on
the Machine tab (the fire watch's thresholds are; its actions are not).

**Where it shows:** at every run start the engine logs one line per gate
setting (`cool: gate coolant_max OFF: cool_temp_max = 60 ...`,
`cool: cool_temp_max = 45 is outside the recommended 25 to 38 ...`, or the
plain value). `GET /settings` carries a `gates` object (per key: `gate`,
`def`, `lo`, `hi`, `band`, `off`, `value`, `state` of `ok | warn | off`,
classified from the stored value). `GET /cool/status` and `GET /status`
carry `gates_off`, the gate names at their off end as the engine resolved
them at the last run start. The panel classifies the stored values it gets
from `GET /settings`, which the engine adopts at the next run start, so
between a save and that start, or under a `GFCOOL_*` override, the banner
and `gates_off` can differ. The panel warns beside a field outside its band,
says "this gate is OFF" at the off end, and shows a standing banner on the
Status tab while any gate is off. None of it is reported to the cloud.

## Job-state reports

The controller reports to forgectrl with `POST /cool/state`, query or form
parameters:

```
mode=idle|run|cooldown & armed=0|1 [& model=density|analog]
    [ & air_assist=0..1023 & exhaust=0..65535 & intake=0..65535 ]
    [ & coolant_max_c=<C> & coolant_min_c=<C>
      & exhaust_min_rpm=<rpm> & intake_min_rpm=<rpm> & air_assist_min_rpm=<rpm> ]
```

- **Level-triggered, repeated at ~1 Hz** while the controller runs, not
  edge-triggered events. A lost report self-heals on the next one.
- `armed` = the laser is armed (fire possible). The engine forces the run
  fan profile and flow interrogation whenever `armed` is true, whatever
  `mode` says.
- The duty parameters are the optional per-job run fan profile (cloud mode
  passes the factory pulse-header duties; GRBL mode omits them, so the
  configured/factory defaults apply). Out-of-range values fall back to
  defaults.
- The limit parameters are the job's envelope: the pulse header's `CMrx` and
  `CMrn` (millidegrees, sent as degrees) and the tach maximum periods
  `EFrx`, `IFrx`, and `AArx` (sent as the minimum speed they mean in the
  kernel's units: ns at 2 pulses/rev for exhaust and intake, µs at 8 for the
  air assist). The client drops a tag that is absent, a sentinel (0, 1023,
  the signed extremes, the unsigned rail), or absurd. **Tighten only:** the
  engine resolves each limit as the stricter of its own configured value
  and the header's. A ceiling only ever comes down and a floor only ever
  goes up, a looser header value is named once per run session and ignored,
  and a gate the operator set to its off end stays off whatever a header
  says. When a header tightens the coolant ceiling the resume gate follows
  it down by the configured gap; the fan floors feed the airflow gates; the
  coolant critical line is local only, since no header carries one. The
  effective set is resolved, logged, and published. Level-triggered like
  the duties: the limits ride every report while the job is loaded and
  leave with it. The engine logs `cool: effective limits: ...` whenever the
  effective set changes and carries it in `GET /cool/status` as `limits`
  (`coolant_max_c`, `coolant_resume_c`, `coolant_source` of
  `local | header`, and the floors).
- **Silence:** if the active controller stops reporting past a timeout
  (5 s), the engine publishes `fire_ok=false` immediately and stands down
  through the normal cooldown path (smoke clear is the right physical
  behavior for a job that died mid-cut), ending at the idle profile (pump
  on, fans idle, heater off). `GET /cool/status` shows `armed` false from
  that point (`report_age_s` tells the age of the last report).
- Silence with the armed window open, or with `cnc/state` still reading
  `running` (cloud mode preloads whole jobs, so the ring can play for
  minutes with no live feeder), is the **hung-controller dead-man**: the
  engine itself writes `cnc/stop` + `cnc/laser_latch=1` (the supervisor
  safes controller *deaths*; this covers *hangs*), and exhaust and intake
  never drop below cooldown duty while the kernel still reports a run in
  progress.

## The verdict file

`/run/forgefirm/cooling.state`, JSON, **atomically replaced** (write-temp
plus rename) at ~1 Hz and on every verdict change:

```json
{ "seq": 1234, "ts_mono": 5678.9,
  "fire_ok": true, "verdict": "OK",
  "hold": false, "resume_ok": true, "armed": true,
  "reason": "", "down_c": 21.3, "up_c": 21.1 }
```

- `ts_mono` is `CLOCK_MONOTONIC` seconds. **Readers must treat a missing
  file or `ts_mono` older than 2 s as `fire_ok=false, hold=true`.** A body
  without its closing brace is a torn read, not a verdict; an absent
  `fire_ok`, `hold`, `resume_ok`, or `armed` key takes the fail-safe value
  (`false`, `true`, `false`, `false`). The publisher never writes a document
  longer than its buffer.
- `armed` is the engine's own view of the armed window, and it is what makes
  a verdict an answer to the session it is read against. **A controller must
  not fire inside its armed window on a verdict whose `armed` is false.** The
  window opens before the engine has seen the job-state report, and the
  verdict standing on file until then was computed for the idle session that
  preceded the arm: at idle nothing is wrong, so it reads `fire_ok=true`
  while the fans are still at their idle duty. The engine sets `armed` from
  the reported window before it applies the run profile and before it
  publishes, so a verdict carrying `armed=true` was computed with the run
  session open. A controller waits for it at the arm rather than firing, and
  refuses the job if it does not arrive.
- `verdict` is one of `OK`, `SUSPECT`, `FAULT`, `OVERTEMP`, `COLD`,
  `WARMUP`, `CRITICAL`, `SENSOR`, `AIRFLOW`, `FLAME`, `FIRE`, `BUMP`, `CRASH`
  ([What the verdicts do](#what-the-verdicts-do)). `hold=true` asks the
  active controller for a feed hold, and for it again if the job is
  resumed under it; `resume_ok=true` signals recovery (auto-resume is the
  controller's call). `OVERTEMP`, `COLD`, `WARMUP`,
  `SENSOR`, `FLAME`, and `BUMP` are pause tiers. `CRITICAL`, `AIRFLOW`, `CRASH`, and
  `FIRE` are the fail tier: they hold for the rest of the run session and
  never offer a resume in it; `CRITICAL`, `AIRFLOW`, and `CRASH` end with
  the session (the ceiling's pause tier keeps holding while the loop is
  hot), `FIRE` holds until the next one starts. Controllers key on the
  flags, not the name; an unknown name with `hold=true` holds.
- **Enforcement stays in the controller.** The fire gate and hold/resume
  issuance run in-process in each controller (the GRBL controller as a feed
  hold and cycle start, the cloud client as its laser-off pause and retraced
  resume, bounded by `cloud_hold_max_s`); the verdict file is an input
  they must survive losing. The channel is not fast enough for anything
  safety-critical. The hardware AND-gate is the safety boundary; this is
  equipment protection.
- `fire_ok` additionally requires a fresh job-state report: an armed window
  the engine cannot see never reads `fire_ok=true`, and never reads
  `armed=true` either. A controller about to fire is, by this contract,
  reporting at 1 Hz.
- **Emergency fallback:** if the verdict goes stale while the laser is
  armed, the controller (besides gating fire and holding) writes the run fan
  duties directly once, compiled-in factory values with no config
  dependency, then stands down. The one sanctioned exception to
  single-writer, taken only when the single writer is provably absent.

## Planned

- **Chassis, SoC, and supply ceilings.** Three temperatures are measured and
  not gated: the chassis LM75 and the SoC die in degrees, the supply sensor
  as a raw count, in `/status` as `temps` (with the kernel's CPU throttle
  state beside them), on the Status tab, and ranged over every job in one
  log line. The SoC already guards itself (the kernel throttles the CPU at
  85 °C and powers the board off at 90 °C on this part). A ceiling for each
  is planned once the record says where one belongs. The supply's
  conversion stays unverified by decision (its heatsink is not reachable
  with a thermometer while the machine runs), so its reading stays a raw
  count and any ceiling for it would be set in raw counts too.
- **Fan floors measured on more than one machine.** The shipped floors are
  a fraction of the bench reference's run-duty speeds; a machine whose
  fans read differently sets its own, and a floor of zero turns that gate
  off while it does.
