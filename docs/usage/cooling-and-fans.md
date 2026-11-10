---
title: Cooling and fans
---

# Cooling and fans

The tube is water-cooled and the enclosure is air-cleared, and both matter
while the laser fires. ForgeFIRM runs this as one service, the cooling engine,
that owns every piece of thermal hardware and answers one question for
whichever controller is running: *is it safe to fire right now?* This page
tells you what you can tune, how to turn a gate off, and what the machine does
when.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

How the engine decides (the fan phases, the over-temperature tiers, the
airflow gates, the fire watch, and the crash watch) is in
[The cooling engine](../technical/forgefirm/cooling-engine.md). The
hardware itself is in [Coolant and airflow](../technical/machine/coolant-and-airflow.md).
The coolant offset tool on the Setup tab is in [Diagnostics](diagnostics.md).

!!! warning "Nothing checks that the coolant is flowing"

    ForgeFIRM does not verify coolant flow. The machine watches the coolant's
    temperature, not whether it moves. Before you cut, make sure the pump
    runs and the coolant circulates.

In GRBL mode the cut fan profile follows your sender's `M8`/`M9`, OR'd with the
armed window ([GRBL mode](grbl-mode.md)). In cloud mode the job's own header
carries the fan duties ([Cloud mode](cloud-mode.md)).

## Settings

All of these live in the panel's Machine tab, are validated on entry, and can
only be changed while the machine is idle. The engine re-reads them at the
start of every run, so a change takes effect on your next job. Blank fields use
the built-in values, shown as placeholders.

| Setting | Default | Legal range | Recommended | What it controls |
|---|---|---|---|---|
| `cool_temp_max` | 33 °C | 5 to 60 °C | 25 to 38 °C | Run ceiling: above it, hold. `60` turns the gate off. |
| `cool_temp_resume` | 31 °C | 5 to 59 °C | 20 to 36 °C | Resume gate: below it, continue. Always kept below the ceiling. |
| `cool_temp_critical_c` | 38 °C | 6 to 70 °C | 36 to 45 °C | Critical line: a fault with no resume in the job. Kept above the ceiling while the ceiling is a gate (a ceiling at 60 leaves the line standing alone); `70` turns the gate off. |
| `cool_cooldown_s` | 15 s | 0 to 1800 s | | Smoke-clear phase at run duty after a job. |
| `cool_cooldown_max_s` | 300 s | 0 to 1800 s | | Cap on the thermal cooldown phase. |
| `cool_tach_exhaust_min_rpm` | 6400 rpm | 0 to 20000 | 5800 to 7000 | Exhaust fan floor at run duty. `0` turns the gate off. |
| `cool_tach_intake_min_rpm` | 2290 rpm | 0 to 20000 | 2100 to 2500 | Intake fan floor, each intake fitted. `0` turns the gate off. |
| `cool_intake_fans` | 2 | 1 or 2 | | The intake fans fitted. Some machines are built with one; the setup counts them and writes the count, and with `1` the second intake is not checked. Until it has a value, no controller runs for a Grbl sender ([Setup](setup.md#the-gate)), and the Machine tab's **Intake fans** field reads **Not counted**: choose **Two** or **One**, then save. |
| `cool_tach_air_assist_min_rpm` | 6000 rpm | 0 to 30000 | 5500 to 6600 | Air-assist fan floor. `0` turns the gate off. |
| `cool_purge_min_current` | 300 raw | 0 to 1023 | 150 to 500 | Purge-air fan current floor (the fan has no tachometer; about 1 off, about 630 on). `0` turns the gate off. |
| `cool_fan_grace_s` | 15 s | 0 to 120 s | 5 to 30 s | Spin-up window after the run profile is written, during which no floor counts. |

The shipped fan floors are 55 percent of the steady speed each fan reaches at
the cut profile on the bench reference (exhaust 11640, intakes 4160, air
assist 11050 rpm); the recommended bands are 50 to 60 percent. A machine whose
fans read differently sets its own floors.

### The other gate settings on the Machine tab

The same tab carries the coolant floor and warm-up gate, the TEC, the lid-IR
flame watch, and the head-accelerometer crash watch. Each is a plain number
with the same range, band, and off-end rules as the table above.
[The cooling engine](../technical/forgefirm/cooling-engine.md) describes what
each gate does.

| Setting | Default | Legal range | Recommended | Off at | What it controls |
|---|---|---|---|---|---|
| `cool_temp_min` | 5 °C | 0 to 40 °C | 3 to 8 °C | 0 | Coolant floor, a fire gate; it clears 1 °C above itself. |
| `cool_temp_start` | 16 °C | 0 to 40 °C | 12 to 20 °C | 0 | Warm-up gate: a session opening under it holds with the loop heater on until the coolant reaches it. Kept above the floor. |
| `cool_tec_present` | 0 | 0 or 1 | | | Whether a thermoelectric cooler (a Pro's chiller) is fitted. The line has no readback, so this is the operator's word; leave it 0 on a Basic or a Plus. The setup's **Your machine** step sets it from your answer ([Setup](setup.md#the-first-run)). |
| `cool_temp_offset_c` | 0 | -5 to 5 C | | | Added to both coolant readings after the conversion, a per-machine correction. No setup step writes it: the coolant and the air in the case are not at one temperature on a machine that has been on for a while, so a room thermometer is not a reference for it. Set it by hand only when a known-good reading says the sensors are off. |
| `cool_tec_on_c` | 20 °C | 6 to 32 °C | 18 to 24 °C | never | TEC on threshold (upstream coolant reading). Kept above `cool_tec_off_c`. |
| `cool_tec_off_c` | 18 °C | 5 to 31 °C | 16 to 22 °C | never | TEC off threshold. The TEC runs only while the fans run, and never within a degree of the coolant floor. |
| `cool_fire_q1_alert` | 275 | 0 to 1023 | 250 to 450 | 0 | Flame watch, lowest sorted lid-IR reading: the pause tier. |
| `cool_fire_q1_critical` | 688 | 0 to 1023 | 500 to 1023 | 0 | Flame watch, lowest reading: the fail tier. Kept above the alert. |
| `cool_fire_q2_alert` | 374 | 0 to 1023 | 300 to 500 | 0 | Flame watch, second-lowest sorted reading: the pause tier. |
| `cool_fire_q2_critical` | 1022 | 0 to 1023 | 500 to 1023 | 0 | Flame watch, second-lowest reading: the fail tier. Kept above the alert. |
| `cool_accel_x_alert` | 132 | 0 to 255 | 100 to 170 | 0 | Crash watch, head-accelerometer X high event: the pause tier. |
| `cool_accel_y_alert` | 112 | 0 to 255 | 85 to 145 | 0 | Crash watch, Y high event: the pause tier. |
| `cool_accel_abort` | 133 | 0 to 255 | 100 to 170 | 0 | Crash watch, shared abort: the fail tier. |

The crash-watch values are the sensor's register units (about 64 per g); the
defaults are the factory's own, about 2 g, far above normal motion. The
flame-watch defaults are the factory's thresholds and sit far above a fully lit
lid lamp.

One tunable rides with the readings and is not a gate:

| Setting | Default | Legal range | What it controls |
|---|---|---|---|
| `cool_aa_offset_counts` | 0 | 0 to 60 | The air-assist fan's shift on both coolant readings, in ADC counts, taken off while the fan runs. The **coolant offset** diagnostic measures it and Apply writes it ([Diagnostics](diagnostics.md)). Zero is the factory behavior, which never corrected the shift. |

`GFCOOL_*` environment overrides exist for bench work; they win for the
lifetime of the process and are not a normal operating path.

### The flow watch (logs only, not a gate)

The coolant flow watch is off by default. It stops nothing, never touches
the pump, and only writes what it sees to the log
([The cooling engine](../technical/forgefirm/cooling-engine.md#coolant-flow)).
Its settings take effect within 5 seconds, not at the next job.

| Setting | Default | Legal range | What it controls |
|---|---|---|---|
| `cool_flow_watch` | 0 | 0 or 1 | `1` turns the watch on. It keeps the downstream coolant sensor slightly warm with the loop's small inline heater. |
| `cool_flow_hold_c` | 1.0 °C | 0.5 to 3.0 °C | The watch's step: how far its heater holds the downstream coolant sensor over the upstream one. A larger step costs more heat. A change starts the watch's hold over. |
| `cool_flow_duty_min` | 0 % | 0 to 4 % | The least heater duty the watch's hold uses. |
| `cool_flow_duty_max` | 15 % | 5 to 25 % | The most heater duty the watch's hold uses. A hold that sits there for 20 s means a dead reading or heater, and the watch stops until forgectrl restarts. |

### Turning a gate off

The gates are settings, and the far end of a gate setting's range is the off
switch: a coolant ceiling of 60 °C never trips, and a fan floor of 0 never
trips. There is no other
switch, and no list of names to get wrong. The ranges are wide on purpose: the
shipped defaults and the recommended bands come from the bench reference, and
a machine whose loop or sensors read differently changes the number rather than
waiting for new firmware.

A gate that is off is not a gate that is forgotten. The panel flags any value
outside its recommended band beside the field and says "this gate is OFF" at
the far end; the Status tab shows a standing banner while any gate is off; the
engine logs one line per gate setting at every run start, and with the ceiling
off it still logs the first reading in a job that would have tripped the
default. `/status` and `/cool/status` carry the off gates as `gates_off`.
Nothing about it reaches the cloud service.

What no setting can reach: the hardware safety chain, the laser latch, the
emission witness, the controller-silence dead-man, and the motion-liveness
gate. A machine with every thermal gate off still stops firing the moment its
controller goes quiet; what it no longer does is hold a job for an
overheating loop. The banner says so.

## Quick reference: what the machine does when

| Situation | Machine response |
|---|---|
| Idle | Pump on, purge air on, fans at idle, heater off (or at the flow watch's few percent, if you turned it on), TEC off. |
| Job starts (or the laser arms) | Cut airflow. |
| Upstream coolant above 33 °C | `OVERTEMP`: hold + forced cooling; released under 31 °C. |
| Upstream coolant at or over 38 °C during a job | `CRITICAL`: fire blocked, hold, no resume this job (a resume under it is held again within a second; reset the job); the ceiling's hold stands until the loop is under 31 °C. |
| Coolant under `cool_temp_min` | `COLD`: fire blocked, hold; released a degree above the floor. |
| A session opened under `cool_temp_start` | `WARMUP`: hold with the loop heater on and the fans idle until the gate is reached, then the run starts. After 30 minutes the heater goes off and the hold stays. |
| A coolant sensor unreadable for two ticks in a row | `SENSOR`: fire blocked, hold, heater off; released the moment both sensors read again. The other coolant gates keep their state meanwhile. |
| Lid IR over an alert threshold for two ticks | `FLAME`: hold, fire blocked; released once five readings in a row are back under the alert. |
| Lid IR over a critical threshold | `FIRE`: motion stopped, laser locked, the controller stopped and started again, hold through the smoke clear and the cooldown; then `ACK`, with jogs allowed. |
| Head accelerometer over an alert threshold | `BUMP`: hold, fire blocked; released after five quiet polls. |
| Head accelerometer over the abort threshold | `CRASH`: motion stopped, laser locked, the controller stopped and started again, hold for the rest of the run session. |
| A fan under its floor inside the spin-up grace | Nothing yet: the gate reads `grace`. |
| A fan under its floor for three seconds after the grace | `AIRFLOW`: fire blocked, hold, no resume this job (a resume under it is held again within a second; reset the job); fans held at run duty; the next job starts the gates fresh. |
| Purge-air current absent at run duty | `AIRFLOW`, the same way. |
| A gate setting at its off end (ceiling 60 °C, a fan floor 0) | No verdict from that gate; a run-start log line, `gates_off` in `/status`, and a standing panel banner. |
| `FIRE`, `CRASH`, `FLAME`, `BUMP`, `AIRFLOW`, `CRITICAL`, or `SENSOR` stands | The button flashes red and a banner on the control panel says why. |
| The cause of `FIRE`, `CRASH`, `AIRFLOW`, or `CRITICAL` has gone, or one of the verdicts above still stood when its job ended and has since cleared | `ACK`: fire blocked, the button still red, until you press **Acknowledge** on the control panel or the machine restarts ([The button flashes red](troubleshooting.md#the-button-flashes-red)). |
| One of those clears on its own | A notice on the control panel; it blocks nothing. |
| Job ends | 15 s smoke clear at run duty, then reduced airflow until the loop is under the resume gate. |
| Controller stops reporting | Fire blocked at once, stand-down through cooldown. |
| Silence while armed, or a program still playing | Motion stopped and the latch locked by the engine itself. |
| Verdict file missing or stale | The controller treats it as fire-blocked and holds. |
| Diagnostic running | Engine suspends its writes and publishes fire-blocked. |
| Engine gone while armed | Controller writes factory run duties once, holds, stands down. |

In GRBL mode the verdicts fall into two tiers as you see them. A pause-tier
hold (`OVERTEMP`, `COLD`, `WARMUP`, `SENSOR`, `FLAME`, `BUMP`, or a verdict
gone stale) holds the job where it is. When the verdict clears, the job
resumes by itself, unless the pause lasted long enough to disarm the laser:
then the button breathes white, and your press resumes the job
([GRBL mode](grbl-mode.md#arming-the-button-press-is-part-of-every-job)).
A fail-tier verdict (`FIRE`, `CRASH`, `AIRFLOW`, `CRITICAL`) ends the job
with alarm 3 and the laser locked, and the next job waits for your
**Acknowledge**
([GRBL mode](grbl-mode.md#pausing-stopping-and-faults)). In cloud mode the
same tiers pause the print or cancel it, and the Glowforge app says why a
print is held where it has words for it. When a pause clears, the button
breathes white: press it to carry on
([Cloud mode](cloud-mode.md#pause-cancel-and-park)).

[Troubleshooting](troubleshooting.md) tells you what to do about each verdict.
