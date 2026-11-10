---
title: Cooling engine
---

# Cooling engine

The cooling engine is the part of forgectrl that owns every piece of thermal
hardware (fans, pump, TEC, and the loop heater) and answers one
question at a time for whichever controller is running: *is it safe to fire
right now?* This page describes how it decides: the two client channels, the
fan phases and the airflow gates, the temperature gates, the fire watch, the
gate settings, and how a failure reaches the operator (the red flash, the
acknowledgment, and the notices). ForgeFIRM has no coolant flow verification
([Coolant flow](#coolant-flow)).

What the hardware is (the loop, the fans, the sensors) is on
[Coolant and airflow](../machine/coolant-and-airflow.md). What the operator
sees and tunes (the settings reference, turning a gate off, the quick
reference of what the machine does when) is on
[Cooling and fans](../../usage/cooling-and-fans.md). The operator procedure
for the diagnostics is on [Diagnostics](../../usage/diagnostics.md).
The beam itself is gated in hardware
([Safing chain](../machine/safing-chain.md)).

The engine lives in forgectrl (`src/cool.c`, the gates in `src/gates.c`, the
airflow gates in `src/airflow.c`, the crash watch in `src/accel.c`, the
coolant flow watch in `src/flowrun.c` and `src/flowwatch.c`).
Tunables are the `cool_*` keys in the shared machine settings, re-read at
every run start (the flow watch's `cool_flow_*` keys every 5 s), with
`GFCOOL_*` environment overrides for bench work.
`GET /cool/status` reports the engine state for the UI and bench tooling.

## One owner, two clients

The cooling engine is the **only** thing that writes fans, pump, TEC, and
heater. The one sharer is its own coolant flow watch: when an owner turns it
on, it borrows the heater while the engine does not need it, and gives it
back first whenever the engine does ([Coolant flow](#coolant-flow)).
Whichever controller is running, GRBL or cloud, is a client of the engine,
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
([Diagnostics](#diagnostics)).

**If the engine itself is provably gone** while the laser is armed, the
controller writes the factory run duties to the fans once, holds the job,
and stands down. That is the single sanctioned exception to single-owner
control, and the duties are compiled in so that a lost configuration file
cannot take the fans with it.

## What the fans do, and when

The engine runs in phases. Duties are the factory machine's own values.

| Phase | Pump | Air assist | Exhaust | Intake | Heater |
|---|---|---|---|---|---|
| **Idle** | on | 204 | off | off | off (the flow watch's hold, if on) |
| **Warm-up hold** (a session opened under `cool_temp_start`) | on | idle | off | off | 40 %, within the warm-up's limits |
| **Run** (or armed, whatever the reported mode) | on | 1023 | 65535 | 43278 | off (the flow watch's hold, if on) |
| **Cooldown, smoke clear** (15 s) | on | run duty | run duty | run duty | off (the flow watch's hold, if on) |
| **Cooldown, thermal** | on | idle | 32768 | 21639 | off |
| **Over-temp or fault hold** | on | run duty | forced | forced | off (over the ceiling, at the critical line, under the floor, or with a coolant sensor unreadable); the flow watch's hold, if on, under any other fault |

Notes on the phases:

- **The pump runs whenever the machine is on**, including at idle.
  Circulation is cheap; a stagnant loop with a warm tube is not. The one
  exception is the quiet hold below, an idle-only listening with the laser
  latched.
- **The engine's heater runs only in the warm-up hold**
  ([Low temperature](#low-temperature-the-floor-and-the-warm-up-hold)). The
  flow watch, when an owner turns it on, holds it at a few percent
  ([Coolant flow](#coolant-flow)). The warm-up's duty, left on, measurably
  warms the loop within minutes. Every writer writes the heater again every
  second, because the kernel holds a write above zero only for its lease
  (`heater_lease_ms`, 5 s by default), so a forgectrl that stops ticking
  leaves the heater off
  ([Kernel module](kernel-module.md#heater_pwm)).
- **Being armed counts as running.** If the laser is armed, the engine
  forces the run profile regardless of what mode the controller reported.
  Fire never happens without cut airflow.
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
quiet, because a running fan or pump is in the reading. The setup's
Lens travel check takes the engine's quiet hold for its listening:
the air assist, exhaust, intake and purge fans off whatever the phase says,
the pump still running (the finder was proven that way). The bench tools
take the same hold through `POST /cool/quiet?on=1`, and with `pump=1` the
coolant pump and the TEC go off as well, so the machine is silent: the one
pump-off state, and a dry one, since the laser stays latched at idle. Release with `on=0`;
`GET /cool/status` shows the hold as `quiet_hold`. The hold is taken only
from an idle machine with no diagnostic running, and `pump=1` only while the
engine's own phase is idle (409, "the cooling engine is not idle: the pump
stays on", under a warm-up, a run, or a cooldown). The engine releases the hold itself the moment a
run session opens or after 600 s, so a job never runs with the machine held
quiet and a listener that died cannot leave it so.

### Airflow gates: a fan that is not moving the air

Commanding a fan and getting airflow are two different things, and the
machine can tell them apart: the exhaust, the intakes, and the air assist
carry tachometers, and the purge-air fan in the head reports its current.
While the run profile is applied, the engine holds every one of them to a
floor, each floor the effective one (a header's tach window can raise it for
a job).

- **The floors** are settings: `cool_tach_exhaust_min_rpm`,
  `cool_tach_intake_min_rpm` (each intake fitted), `cool_tach_air_assist_min_rpm`,
  and `cool_purge_min_current`. Each ships at 55 percent of the steady speed
  that fan reaches at the cut profile on the bench reference (the measured
  speeds and spin-up times are on
  [Coolant and airflow](../machine/coolant-and-airflow.md#what-the-fans-actually-reach)),
  with a recommended band of 50 to 60 percent. The setup airflow check
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
  before it opens the window: the button breathes white, the fans come up,
  then the beam. The controller's wait is the grace plus 5 s; an
  acknowledgment that never comes refuses the arm (`ALARM:3`, "the
  cooling service did not take the job"), which is what a fan that cannot
  reach its floor looks like. The cloud client waits for the same
  acknowledgment before it unlocks the latch and asks for the press
  ([Cloud mode](cloud-mode.md#how-a-job-runs)).
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
- **A machine built with one intake fan** has nothing on the second intake
  tach ([One intake fan or two](../machine/coolant-and-airflow.md#one-intake-fan-or-two)).
  With `cool_intake_fans` at `1`, which the setup writes when it counts one,
  intake 2 is measured and published as `not fitted` with no floor, and
  never judged; intake 1 holds the intake floor alone, and every run start
  logs the one intake fan. Any other value judges both intakes.

Outside a run the gates read `idle`. `/cool/status` carries each fan's
`reading`, `floor`, and `state` (`grace`, `ok`, `under`, `TRIPPED`, `off`,
`unjudged`, `not fitted`, or `idle`) as `fan_gates`.

## Coolant flow

ForgeFIRM has no coolant flow verification: nothing checks that the coolant
is moving, before a job or during one. A pump can stop, an impeller can
slip, or a line can airlock, and none of it shows in a temperature reading
until the tube is already in trouble. The pump runs whenever the machine is
on, and the coolant gates that stand are the temperature ones
([Over-temperature](#over-temperature),
[Low temperature](#low-temperature-the-floor-and-the-warm-up-hold)).

An owner can turn on a **coolant flow watch** (`cool_flow_watch 1`; off by
default). It logs what it sees and stops nothing, and it never touches the
pump. It exists to learn from machines other than the bench reference
whether a stopped pump can be told apart reliably on them.

- **The hold.** The watch uses the loop's inline heater, which sits between
  the two coolant sensors
  ([Coolant and airflow](../machine/coolant-and-airflow.md#the-coolant-loop)).
  After a rest with the heater off (until the heater has been off 60 s, and
  at least 10 s; the difference between the sensors over the rest's last
  10 s is the rest difference), the heater holds the downstream sensor a
  step over the upstream one (`cool_flow_hold_c`, 1 °C by default, between
  `cool_flow_duty_min` and `cool_flow_duty_max`; a change starts the hold
  over), and the duty it costs is the signal: moving coolant carries the
  heat away, so it costs more. On the bench reference it cost about 3.3 %
  at the idle fans with the pump running and about 1.5 % with it stopped,
  and it warmed an idle loop about 0.5 °C over 90 minutes.
- **The idle reference.** Each idle stretch's settled duty, taken from its
  own 60 to 90 s at the idle fans. The first one is the idle reference; each
  later one is logged as a share of it. A job that starts before the first
  one leaves the reference to the idle after the job. A settled duty at or
  under zero is no reference, since nothing can be measured against zero:
  the watch logs `flow: no idle reference: the hold settled at no duty at
  the idle fans`, the floor judges nothing, and a job's summary says
  `no idle reference`, until a later idle stretch gives one.
- **The fall detector.** The 10 s duty 15 % or more under its own level 60
  to 90 s earlier, blind for 150 s after the hold starts or the fans change.
  On the bench reference it named a pump stopped with the tube dark within
  18 to 20 s.
- **The floor**, under a job at the run fans: the 10 s duty under the idle
  reference, judged from 30 s after the run fans start. Before then the 10 s
  duty is still the idle fans' and sits on the reference; by 30 s the run
  fans have lifted a flowing duty about 13 % over it on the bench reference.
  It covers the rest of the fall detector's blind start; on the bench
  reference it named a pump stopped during a dark job 27 s after the pump
  stopped.
- **What it cannot see:** a pump that has not moved since the machine
  started. The duty means something only as a change on the same machine,
  because what flowing costs differs from machine to machine.

**Its readings.** The watch reads the kernel sampler's one-second means of
the two coolant channels (`pic/means`,
[Kernel module](kernel-module.md#the-sampler)) and corrects them as the
engine corrects its own readings: the air-assist shift
([below](#the-air-assist-offset-on-the-coolant-readings)) taken off, then
the per-machine `cool_temp_offset_c` added. A one-second window is a
reading only when it holds at least half the sampler's rate of reads on
both channels: the mean of a window's first reads is not a second's mean.
With the setting off the watch does not read the sampler at all. With no
readings from the sampler it holds no heat. In the rest it rests again, logs
`flow: the sampler gives no readings (pic/means); the hold waits for them`
once, and `GET /cool/flow`'s `why` says the sampler gives no readings; in
the hold, readings lost for more than 2 s put its duty to 0 until they
come back.

**Its limits on the heater.** The hold puts its duty to 0 while the
corrected downstream reading is at or over 45 °C. A hold that sits at
`cool_flow_duty_max` for 20 s means a frozen or dead reading or no heater:
the heater goes off and the watch stops until forgectrl restarts. It writes
its duty again every second while it holds above zero, for the kernel's
lease ([Kernel module](kernel-module.md#heater_pwm)). It gives the heater
back, off, whenever the engine needs it or has called the loop unfit to
heat. Under a diagnostic it yields, and the engine's tick has nine causes
of its own: a warm-up, an unreadable sensor, a quiet hold, coolant
over the ceiling (`OVERTEMP`), coolant under the floor (`COLD`), coolant at
the critical line, while the TEC runs, upstream coolant over the shipped
33 °C ceiling while the ceiling gate is turned off, and
while the engine cools the loop (the thermal cooldown, or the cooling
airflow an over-temperature forces). Under the floor the reason is the
heater's place: it sits between the two coolant sensors, and in a loop
that is still or slow its heat reaches the upstream one, the reading that
releases the floor. Every engine path that writes the heater takes it back first. The
engine hands the watch its state at every tick; when that state is more
than 3 s old, the watch counts it as the engine taking the heater: it turns
the heater off itself, pauses, and says "the cooling engine stopped
ticking". The watch starts over after a 60 s rest once it has the
heater again. At a forgectrl start the rest is 10 s when the watch's own
stamp in the run directory (`flow-heater-off`, which stands only while the
heater has stayed off since the watch turned it off) is 60 s old or more,
and what is left of the 60 s, at least 10 s, when it is younger. With no stamp (a boot, a
daemon killed in a hold, heat that was the engine's) the watch takes the
heater as just off and rests the full 60 s.

Its results are `flow:` lines in the forgectrl log, which a log export
carries: the idle reference, an idle summary every 10 minutes (the duty's
mean, its 10 s range and the largest fall seen), the first time the fall
detector or the floor would have held a job, and a summary at the end of
each job it held under (a job it did not hold under, while on, gets one
line saying so; with the watch off, a job writes no `flow:` line). The
Status tab's Cooling card shows whether it is running (and why
not, when paused or stopped), its heater duty, the fall, the idle reference
and the settings in force; `GET /cool/flow` gives the same, its `duty` the
duty commanded ([forgectrl](forgectrl.md)).

## The air-assist offset on the coolant readings

A tunable rides with the coolant readings themselves:
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
every PIC transaction, so a reading does not depend on whether the reader
had just woken) recommends it and the panel's Apply writes it. Zero, the default, is the factory behavior, which
never corrected the shift.

## What the verdicts do

| Verdict | Effect |
|---|---|
| `OK` | Fire permitted. |
| `OVERTEMP` | Hold with forced cooling airflow; released below the resume gate. |
| `COLD` | The coolant under `cool_temp_min`: fire blocked, hold; back a degree above it. |
| `WARMUP` | A session opened under `cool_temp_start`: held with the loop heater on and the fans idle until the gate is reached, then run. |
| `CRITICAL` | The coolant at or over the critical line in a run session: fire blocked, hold, no resume this job. |
| `SENSOR` | A coolant sensor unreadable for two ticks in a row: fire blocked, hold, heater off; released the moment both sensors read again. The other coolant gates keep their state while the engine is blind; a warm-up gets its heater back. |
| `AIRFLOW` | A fan under its floor: fire blocked, hold, no resume this job. |
| `FLAME` | The fire watch's pause tier: hold, fire blocked; released when the reading clears. |
| `FIRE` | The fire watch's fail tier: motion stopped, latch locked, the controller stopped and started again (the home is dropped), hold through the session's smoke and thermal phases. It ends when the engine is back at idle, or when a run session opens; `ACK` stands after it. |
| `BUMP` | The crash watch's pause tier: hold, fire blocked; released once the head sits quiet. |
| `CRASH` | The crash watch's fail tier: motion stopped, latch locked, the controller stopped and started again (the home is dropped), hold for the rest of the run session. |
| `EXT` | An extension package's hold stands ([An extension's hold](#an-extensions-hold)): fire blocked, hold; released at the tick after the hold clears. The reason names the package and carries its words. |
| `ACK` | A failure that waits for the operator's acknowledgment after its own verdict has gone ([The operator's attention](#the-operators-attention)): fire blocked, hold only while an armed window is open, motion free; released by the acknowledgment, or by a restart. The reason is the failure's. |

### An extension's hold

A package with the operator's `hold` grant may withhold fire and never
permit it. Its hold joins the pause tier under every verdict of the
engine's own: `EXT` is the name only when nothing else is, so a hold can
neither hide a verdict nor outrank one, and a fail tier under a hold is
still a fail tier. It is never a fail tier itself.

The [extension host](extensions.md#the-extension-host) owns the holds,
and a package that is frozen for the job changes nothing about them. The
host keeps one file per package under `/run/forgefirm/holds/`,
`<id>.json`, and rewrites it with a fresh monotonic timestamp for as long
as it runs:

```json
{"id": "org.example.badge", "required": true, "raised": false,
 "reason": "no badge presented", "ts_mono": 1234.567}
```

The engine reads the directory once a tick:

| A hold file that is | Means |
|---|---|
| fresh (`ts_mono` within 2 s, the rule the controllers apply to the verdict) and `raised` | The hold stands, with the reason `<id>: <reason>` |
| fresh and not `raised` | Nothing |
| stale and `required` | The hold stands whatever the file last said, with the reason `<id>: the extension host is not answering` |
| stale and not `required` (advisory) | Dropped, and logged once |
| missing, for a package named under `/data/forgefirm/ext/required-holds/` | The hold stands, with the same reason: the files are on a tmpfs and gone with a reboot, and a host that never came up wrote none. The host keeps one empty file there per required hold; only the names are read |
| not readable as a hold file, or one of more than 32 | The hold stands: what it meant is not known |

The first hold that stands, by file name, gives the reason. A package's
words are cut to printable ASCII without the quote and the backslash
before they go into the verdict. The rising edge, a change of the standing
hold, and the clearing are logged.

**The operator's exits do not depend on the host.** The engine looks at the
holds only while `ext_enabled` is 1 and the safe-mode file
`/run/forgefirm/ext-safe` does not exist. Turning extensions off, or
entering safe mode, ends every hold at the next tick, whatever has become
of the host that wrote it.

The two controllers treat the pause as they treat every pause. The GRBL
controller holds the job and resumes it lit when the hold clears: with no
press while its armed window is open, and after a press once the window's
grace has closed it
([The cooling client](grblhal-driver.md#the-cooling-client)). The cloud
client locks the latch under any armed `fire_ok=false`. When the hold
clears it unlocks the latch, sets the button breathing, and resumes the
print on a press: the lock set the hardware button latch, which only a
press taken with the lock released clears. A press during the hold
changes nothing, and a hold that outlasts `cloud_hold_max_s` cancels the
print ([Cloud mode](cloud-mode.md#how-a-job-runs)).

## The operator's attention

Some of what blocks firing is the machine's own to wait out: the warm-up, a
cold or a hot loop, an extension's hold. The rest needs a person to look:
`FIRE`, `CRASH`, `FLAME`, `BUMP`, `AIRFLOW`, `CRITICAL`, and `SENSOR`. While
one of these is the verdict, the engine flashes the machine's button red,
1 s on and 1 s off, and the panel says why. Red always means firing is
blocked. `WARMUP`, `COLD`, `OVERTEMP`, `EXT`, and an open lid never light
it. A failed motion check flashes it too, until a retry clears the motion
fault ([Mode supervision](forgectrl.md#mode-supervision)).

The flash stands over any pattern a controller writes: the engine reads the
LED back at every tick and puts the flash back within that tick, and it
never rewrites a flash that stands, which would restart its period. When
nothing wants the flash, the engine puts out only its own light: it turns
the LED off while the button still reads as the flash, or cannot be read,
and leaves a button that another owner has written since the last tick. A
pattern the flash covered comes back from its owner.
The rest of the button's language is on
[forgectrl](forgectrl.md#the-buttons-light).

**The acknowledgment.** A failure of the fail tier (`FIRE`, `CRASH`,
`AIRFLOW`, `CRITICAL`), or any failure on that list still standing when an
armed window closes (the job ended or was canceled, or the GRBL
controller's grace closed the window during the pause) or when the engine
returns to idle (a watch that stands down at the session's end, such as a
flame that started during the smoke phase, ends its verdict without its
cause having cleared), outlasts its own verdict. So does a head-bump alert
whose watch stands down inside an open window, when the accelerometer
stops answering ([The fire watch](#the-fire-watch)): nothing saw the head
sit quiet. Once its cause has gone,
the engine publishes `ACK` where it would publish `OK`: `fire_ok` false,
`hold` true only while an armed window is open, motion free, the failure's
reason, and the button still flashing red. Any other verdict that stands
meanwhile (`COLD`, `OVERTEMP`, `WARMUP`, `EXT`, a later cause on the list)
is published in its place with its own reason, and `fire_ok` stays false
until the acknowledgment either way. The verdict file's `ack_wait` is true
for as long as a failure waits for the acknowledgment, whatever the
verdict's name ([The verdict file](#the-verdict-file)), and it is what both
controllers read.

- **It ends** with `POST /cool/attention/ack`, the panel's **Acknowledge**,
  which needs no press of the button. While a cause on the list stands the
  route answers 409, "the failure still stands". The acknowledgment clears
  the reason only where it holds the acknowledged failure's words; another
  cause's words stand. It also ends with a restart of forgectrl, a reboot
  included: nothing of it is kept.
- **One failure waits at a time.** Once a failure needs the
  acknowledgment, a later, different cause does not take its place: the
  panel keeps asking about the first, and the new one shows as the verdict.
  One that comes while the first waits is logged as `cool: firing blocked,
  the operator's attention wanted: <reason> (the acknowledgment of
  <verdict> still waits)`.
- **A pause-tier cause that clears while its armed window is still open**
  needs no acknowledgment: the job it held resumes on its controller's terms
  ([An extension's hold](#an-extensions-hold) has both controllers' rules).
- **The controllers under it.** The GRBL controller refuses an arm with
  `laser fire blocked: a fault waits for its Acknowledge on the control
  panel` and `ALARM:3`
  ([The armed window](grblhal-driver.md#the-armed-window)), and a job it
  holds stays held until the acknowledgment, then resumes through the
  re-arm's press ([The cooling client](grblhal-driver.md#the-cooling-client)).
  The cloud client refuses a print before its armed session opens, with
  no press asked for, its log saying `a fault waits for its Acknowledge on
  the control panel; the print cannot arm`, and cancels a print when one
  comes to wait during its verdict wait, which is before the press
  ([Cloud mode](cloud-mode.md#how-a-job-runs) quotes that log line too).
  Both read `ack_wait` and the name `ACK`, so an acknowledgment that waits
  under another verdict's name is refused the same way.

**The notices.** A failure on that list whose cause clears on its own,
without needing the acknowledgment (a pause-tier cause gone while its armed
window is still open, or one at idle), leaves a notice: its verdict, its
reason, when it started, when it cleared, and a count. A failure that gives
way to another one on the list (a `BUMP` to a `CRASH`, a `SENSOR` under a
`FLAME`) leaves none: the new one takes its place, and the first may still
stand under it, since a verdict names only the highest. A repeat of the
last notice's verdict counts
on that notice (`times`, with its `cleared_at` moved on) rather than
stacking, and at most 5 are kept, the oldest going first. A notice blocks
nothing and lights nothing. `POST /cool/notices/dismiss?upto=<seq>` removes
the notices up to and including that sequence number, every one when `upto`
is left out; the panel's **Dismiss** sends the last one it shows. A restart
clears them.

**Where it shows.** `GET /cool/status` carries `attention`, an object with
`standing` (a failure stands, live or waiting for its acknowledgment),
`live` (a cause on the list stands now), `verdict`, `reason`, `at` (when it started), and
`cleared_at` (when its cause went, 0 while it stands), the times in seconds
since the epoch and 0 when unset; `ack_wait`, the verdict file's boolean
(`standing` and not `live`); and `notices`, an array of `{seq,
verdict, reason, at, cleared_at, times}`. The panel shows the attention as
a banner at the top of every tab, with **Acknowledge** once the cause has
gone, and the notices as a second banner with **Dismiss**
([The control panel](../../usage/control-panel.md#the-page)). The log says
`cool: firing blocked, the operator's attention wanted:` with the reason as
a failure starts, `cool: <verdict> cleared on its own after <n> s` for a
notice, and `cool: the operator acknowledged <verdict>`. The acceptance
baseline acknowledges a failure a run left waiting for its acknowledgment
and records it as a leftover, and dismisses the notices the run raised,
never one that stood before it
([Acceptance](../../developers/acceptance.md#the-baseline)).

## Over-temperature

The engine uses the factory's coolant windows:

- **Run ceiling 33 °C** (`cool_temp_max`): above this, the verdict goes
  `OVERTEMP` with a hold request and cooling airflow forced on.
- **Resume gate 31 °C** (`cool_temp_resume`): below this, recovery is
  signaled (`resume_ok`). It is always kept below the ceiling, and when a
  header tightens the ceiling the resume gate follows it down by the
  configured gap.
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
cycle takes a feed hold and resumes once the loop recovers, after a press if
the hold outlasted the armed window's grace
([The cooling client](grblhal-driver.md#the-cooling-client)); the sender
shows the hold state and a warning message. A jog is canceled instead (a
jog cannot be held). Fire stays gated for the whole excursion.

## Low temperature: the floor and the warm-up hold

Two gates sit below the operating window:

- **The floor** (`cool_temp_min`, default 5 °C) is a fire gate: coolant
  under it reads `COLD`, fire blocked, hold; the gate clears 1 °C above
  itself. A header floor can only raise it. At 0 the gate is off.
- **The warm-up gate** (`cool_temp_start`, default 16 °C, kept above the
  floor): a session that opens under it holds with the loop heater on and
  the fans idle until the gate is reached (verdict `WARMUP`, phase `warm-up`
  in `/cool/status`), then runs. At 0 the gate is off.

  **The release judges a one-minute rolling minimum of the upstream reading,
  not the instant one.** With the pump running, a slug of the heater's output
  reaches the upstream sensor within seconds. On the bench reference it lifts
  the instant reading by a degree while the bulk warms about half a degree a
  minute, so a release on the instant reading ends a hold in about eleven
  seconds with the loop still cold. Between slugs the rolling minimum
  falls back to the bulk, which is the number that matters.

  The hold has no time limit by design; the heater has one (the heat budget
  below). On the bench reference the heater plateaus 8 to 9 °C over
  ambient, so a loop that stops warming short of the gate is named once and
  keeps holding: a shop more than about 8 °C below the gate needs the gate
  lowered or the room warmed.

  **The warm-up heater runs at 40 % within limits**, decided and written at
  every tick (the kernel's lease,
  [Kernel module](kernel-module.md#heater_pwm)):

  - **The downstream cutoff.** Off while the downstream sensor reads 45 °C
    or more, and on again once it reads 40 °C or less. The downstream sensor
    sits after the heater and reads its heat first; every coolant gate reads
    upstream, before the heater.
  - **The heat budget.** Off for the rest of the warm-up once it has run
    30 minutes. The hold stays, with the reason
    `WARM-UP: heater off after 30 min, coolant X C under the Y C gate - hold`:
    a loop that has not reached the gate in that time is not going to.
  - **A silent pump.** Off while a quiet hold has the pump off.
  - **A blind sensor.** Off with the downstream sensor unreadable, and
    under `SENSOR`; a warm-up gets its heater back once both sensors read
    again.

### The TEC

`thermal/tec_on` is a bare output with no readback, so presence cannot be
detected. The TEC is driven only when `cool_tec_present` is `1` (the
Machine tab's "TEC (Pro chiller)", set by the setup's Your machine step;
default `0`, and ForgeFIRM never touches the line otherwise). It is the
operator's word, which also covers retrofits: the `tec_temp` input has no
sensor connected either ([Sensors](../machine/sensors.md#power-supply-and-tec-temperatures-picpwr_temp-pictec_temp)).
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

## Diagnostics

The web panel's **Setup** tab runs the cooling tool,
`aa-offset-calibrate`
([The air-assist offset](#the-air-assist-offset-on-the-coolant-readings)).
The operator procedure is on [Diagnostics](../../usage/diagnostics.md);
this section is the method.

The tool takes the hardware over: the active controller is suspended for
the duration, the engine stands aside, and the controller is restored on
every exit path (completion, error, or Abort). The laser stays latched
throughout. Progress, both coolant temperatures, and a scrolling log stream
to the page while it runs.

A diagnostic owns the thermal hardware between `cool_diag_take` and
`cool_diag_release`. Take succeeds only from an idle engine, every tool
write goes through the engine's guarded diag helpers (one owner), the tick
publishes phase `diag` with `fire_ok=false, hold=true` and leaves the
thermal hardware to the diagnostic, and the release reasserts the idle
posture in one place. The engine does not write a diagnostic's heater for
it: a diagnostic that wants heat writes its duty again inside the kernel's
lease ([Kernel module](kernel-module.md#heater_pwm)), so one that hangs
loses its heat with the lease. Nothing is sensed under a diagnostic, so
the operator's attention stands as the last tick left it: a failure that
waits for its acknowledgment keeps its red flash, put back over whatever
the diagnostic's side wrote, and its verdict name `ACK`; a cause that was
live is still counted live, under the name `OK`, and no notice says it
cleared.

## The fire watch

The engine runs the physical-evidence witnesses at its 1 Hz tick.

- **Emission evidence.** `cnc/laser_on_sampled` counts the last ~1 s
  window's emitting samples on the gated output of the hardware AND-gate:
  evidence, not a commanded state. Emission with no armed window in the
  last 3 s (the sample window's lag past a disarm) gets the hung-controller
  treatment (`cnc/stop` + `cnc/laser_latch=1`, repeated while the evidence
  persists). The GRBL controller runs the same check in-process once a
  second and alarms on it ([The grblHAL driver](grblhal-driver.md#faults)).
- **Laser supply power-good** is watched during an armed window: when fewer
  than half of the last second's samples read good, the engine warns once per
  session. On a healthy supply the line is good in every sample, so the
  warning means the supply's supervisor reported a fault.
- **Lid IR fire watch.** The four `pic/lid_ir_*` channels are polled every
  tick; the sensors logger's job record carries each job's baseline and
  peaks (the characterization dataset).
  The channels are first of all a photometer for the lid lamp, and a cut and
  a candle move them by the same few counts, which is what shapes this watch:
  the measurements are on
  [Sensors](../machine/sensors.md#lid-ir-sensors-piclid_ir_1-to-piclid_ir_4).
  Through the run, smoke, and
  thermal phases the four readings sorted ascending (the quartiles, the
  factory's statistic) are judged against two tiers per quartile, the
  factory's own shape. A first or second quartile over its alert threshold
  for two ticks is the pause tier (verdict `FLAME`, `hold`, fire blocked;
  released by five readings in a row back under the alert). A read of the
  channels that fails mid-session judges nothing: a standing `FLAME` stays,
  and its count of clean readings starts over. The watch stands down when
  the engine is back at idle, and the hold goes with it, into the
  acknowledgment. A `FLAME` that stands in a session's tail carries into
  the run session that opens over it and is released there the same way.
  Over
  its critical threshold is the fail tier (motion stopped, latch locked,
  verdict `FIRE` with `hold` through the session's tail until the engine is
  back at idle or a run session opens, then `ACK` until the acknowledgment
  ([The operator's attention](#the-operators-attention)), smoke-clear airflow
  held, and the controller ended: after its own kernel writes the engine
  asks the supervisor to stop the controller and start it again, so no run
  start can relight what was locked and the sender sees the job end
  ([forgectrl](forgectrl.md#mode-supervision))). The defaults are the thresholds the factory ships in every pulse
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
  `CRASH` with `hold` for the rest of the run session, and the controller
  stopped and started again the same way as on `FIRE`). Thresholds are IG
  register units at the ±4 g run full scale, so 1 g is about 64; the defaults
  are the factory's own header values, about 2 g, far above normal commanded
  motion. Z is never armed: gravity rides it, and the factory ships Z zero
  too. The registers, the threshold scale and the factory's own values are on
  [Sensors](../machine/sensors.md#the-head-accelerometer).
  The watch arms only inside the laser's armed window. The liveness probe and
  cloud homing read the accelerometer through `st_accel` in unarmed sessions,
  and the armed watch owns the part's ODR and full scale (`st_accel` leaves it
  powered down between one-shots; the watch sets 800 Hz and ±4 g, re-asserts
  them every poll, and restores what it found on disarm). A head that fails
  three polls in a row stands the watch down for the session, said once.
  A `BUMP` whose watch stands down, with the armed window closing or the
  head not answering, ends with the watch and waits for the acknowledgment
  ([The operator's attention](#the-operators-attention)): nothing polls
  the part from there, so nothing saw the head sit quiet. A `CRASH` stands
  on to its session's end.
  `/cool/status` carries the watch state as
  `accel_watch: off | watch | armed | alert | ALARM` (`off` = the part
  absent or not answering; `watch` = thresholds set, window not armed).
- **Telemetry.** `cnc/faults` transitions to nonzero during a run window
  are warned. What every sensor read through a job, the chassis, SoC die
  and supply temperatures and `pic/hv_current` (the only live HV telemetry)
  among them, is the sensors logger's job record
  ([Logging](logging.md#the-sensors-logger)). No gate stands behind any of
  them ([Planned](#planned)). The SoC guards itself: the i.MX6 thermal zone
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
| `cool_tach_exhaust_min_rpm` | `exhaust` | 6400 rpm | 0 to 20000 | 5800 to 7000 | 0 |
| `cool_tach_intake_min_rpm` | `intake` (each tach fitted) | 2290 rpm | 0 to 20000 | 2100 to 2500 | 0 |
| `cool_tach_air_assist_min_rpm` | `air_assist` | 6000 rpm | 0 to 30000 | 5500 to 6600 | 0 |
| `cool_purge_min_current` | `purge` (current, raw) | 300 | 0 to 1023 | 150 to 500 | 0 |
| `cool_fan_grace_s` | (the spin-up window, no gate) | 15 s | 0 to 120 s | 5 to 30 s | never |

**A limit that is not a finite number keeps its default.** The gate
validator refuses one, so it can only come from a file edited by hand. Every
comparison against `nan` is false, so such a limit would never trip and
never read as off: the engine keeps the default instead and logs
`cool: <key> = <value> is not a finite number; the default <default> stands`
at each run start. A `GFCOOL_*` override that is not finite is passed over
the same way (`cool: <variable>=<value> is not a finite number; ignored`),
and the setting or the default stands.

**What an off gate does:** the engine skips the comparison (no verdict, no
hold from it) and keeps measuring. With `coolant_max` off, the first reading
in a run session over the shipped default is logged once as what the gate
would have done; with a fan floor off, the first reading under the shipped
default likewise. A header limit never overrules an off gate.

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

- **The channel is the running controller's alone.** A forged `mode=idle`
  would stand the fans down under a cut, so the route takes a report from
  one sender. It answers a loopback peer only, and a loopback peer is not
  enough, since anything that runs on the machine is one: the supervisor
  hands each controller it spawns a secret in its environment
  (`GF_REPORT_SECRET`, 32 hex digits, new at every spawn, the way it hands
  over the pulse device), the controller sends it with every report as the
  header `X-ForgeFIRM-Report`, and the route refuses a report without it
  (403). A reap ends the secret, so nothing reports for a controller that is
  gone. Both clients read it once and take it out of their environment, so
  nothing they start inherits it, with one exception: the GRBL controller
  hands it to the homing runner at the runner's spawn. The runner reports in
  the controller's place while a camera home holds the machine, and the
  controller reports nothing then ([Homing](homing.md)); without the secret
  every one of the runner's reports is refused, the engine hears silence,
  and the hung-controller dead-man stops the session's first motion. Neither
  client puts a value in a header that is not 32 hex digits. The secret is
  never logged.
- **Level-triggered, repeated at ~1 Hz** while the controller runs, not
  edge-triggered events. A lost report self-heals on the next one.
- `armed` = the laser is armed (fire possible). The engine forces the run
  fan profile whenever `armed` is true, whatever `mode` says.
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
  on, fans idle, the engine's heater off). `GET /cool/status` shows `armed` false from
  that point (`report_age_s` tells the age of the last report). The
  timeout holds the controllers' own rule inside it: a controller treats a
  verdict older than 2 s as a hold and reports every second. The report
  route records each report on the HTTP server's own threads, so a stall
  of the engine's thread never ages the reports, and the stall alone never
  trips the dead-man below. What the job that the controller held on its
  stale verdict needs to resume is the controller's rule: the GRBL
  controller's armed window counts its grace down through a hold
  ([The armed window](grblhal-driver.md#the-armed-window)), and the cloud
  client locks the latch under any armed `fire_ok=false`
  ([An extension's hold](#an-extensions-hold)). Reports silent past the
  5 s are the dead-man below.
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
  "ack_wait": false,
  "reason": "", "down_c": 21.3, "up_c": 21.1 }
```

- `ts_mono` is `CLOCK_MONOTONIC` seconds. **Readers must treat a missing
  file or `ts_mono` older than 2 s as `fire_ok=false, hold=true`.** The
  engine prints it to the millisecond, rounded down, so a reader on the
  same clock never sees a stamp from its future; a stamp ahead of the
  reader's clock is no verdict, like one older than 2 s. A body
  without its closing brace is a torn read, not a verdict; an absent
  `fire_ok`, `hold`, `resume_ok`, or `armed` key takes the fail-safe value
  (`false`, `true`, `false`, `false`), and an absent `ack_wait` reads as
  false: it gates nothing by itself, since `fire_ok` carries the block. The
  publisher never writes a document longer than its buffer.
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
- `verdict` is one of `OK`, `OVERTEMP`, `COLD`,
  `WARMUP`, `CRITICAL`, `SENSOR`, `AIRFLOW`, `FLAME`, `FIRE`, `BUMP`, `CRASH`,
  `EXT`, `ACK` ([What the verdicts do](#what-the-verdicts-do)). `hold=true` asks the
  active controller for a feed hold, and for it again if the job is
  resumed under it; `resume_ok=true` signals recovery (auto-resume is the
  controller's call). `OVERTEMP`, `COLD`, `WARMUP`,
  `SENSOR`, `FLAME`, `BUMP`, and `EXT` are pause tiers. `CRITICAL`, `AIRFLOW`, `CRASH`, and
  `FIRE` are the fail tier: they hold for the rest of the run session and
  never offer a resume in it; `CRITICAL`, `AIRFLOW`, and `CRASH` end with
  the session (the ceiling's pause tier keeps holding while the loop is
  hot), `FIRE` holds through the session's tail and ends when the engine is
  back at idle or a run session opens, with `ACK` after it. `ACK` blocks fire until the
  operator acknowledges the failure behind it and holds only inside an
  armed window ([The operator's attention](#the-operators-attention)).
  Controllers key on the flags, not the name; an unknown name with
  `hold=true` holds.
- `ack_wait` is true while a failure waits for the operator's Acknowledge,
  whatever the verdict's name: the name `ACK` is published only when no
  other verdict stands, so under a `COLD` or an `OVERTEMP` the field alone
  says it. `fire_ok` is false whenever it is true. Both controllers read
  the field, so that neither asks for a press it would then refuse. The
  engine's tick under a diagnostic carries it too.
- **Enforcement of the pause tier stays in the controller.** The fire gate
  and hold/resume issuance run in-process in each controller (the GRBL
  controller as a feed hold and cycle start, with FIRE masked on every tick
  of its stream by the window and `fire_ok`; the cloud client as its
  laser-off pause and retraced resume, bounded by `cloud_hold_max_s`); the
  verdict file is an input they must survive losing. The fail tiers do not
  wait for it: their kernel writes land first, and the controller is stopped
  and started again by the supervisor. The channel is not fast enough for
  anything safety-critical. The hardware AND-gate is the safety boundary;
  this is equipment protection.
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
  state beside them), on the Status tab, and ranged over every job in the
  sensors logger's job record ([Logging](logging.md#the-sensors-logger)).
  The SoC already guards itself (the kernel throttles the CPU at
  85 °C and powers the board off at 90 °C on this part). A ceiling for each
  is planned once the record says where one belongs. The supply's
  conversion stays unverified by decision (its heatsink is not reachable
  with a thermometer while the machine runs), so its reading stays a raw
  count and any ceiling for it would be set in raw counts too.
- **Fan floors measured on more than one machine.** The shipped floors are
  a fraction of the bench reference's run-duty speeds; a machine whose
  fans read differently sets its own, and a floor of zero turns that gate
  off while it does.
