---
title: forgectrl
---

# forgectrl

forgectrl is the machine-services daemon of ForgeFIRM. It runs on the
factory i.MX6 control board and serves HTTP on port 8080. This page is the
machine-services contract: the switch map, the safety-chain readbacks,
telemetry, mode supervision, pulse-device ownership, the clocks rule, and the
hardware ownership table. The source is
[openglow-org/forgectrl](https://github.com/openglow-org/forgectrl). This page
is the machine-services contract.

## The contract

Three things touch the non-motion hardware of the Glowforge factory board:

- **forgectrl**, the machine-services daemon: web control panel, camera
  service, machine settings, telemetry, diagnostics, logging.
- The **GRBL controller**,
  [grblHAL-glowforge](https://github.com/openglow-org/grblHAL-glowforge):
  motion and laser in GRBL mode ([grblHAL driver](grblhal-driver.md)).
- The **cloud client**, `gfcloud`, built on
  [Glowforge-Utilities](https://github.com/openglow-org/Glowforge-Utilities)
  and [python3-gfhardware](https://github.com/openglow-org/python3-gfhardware):
  motion and laser in Glowforge-cloud mode ([Cloud mode](cloud-mode.md)).

Exactly one controller mode is active at a time. Kernel attribute semantics
(ranges, units, the feeder contract) are owned by the kernel pages
([Kernel module](kernel-module.md),
[Pulse feeder contract](pulse-feeder-contract.md)); this page does not
restate them except where a conversion or a polarity is needed by every
consumer. Where the pages disagree, the kernel pages win for kernel behavior
and this page wins for the userspace division of labor.

Parts of the contract live on their own pages:

| Part | Page |
|---|---|
| Sensor conversions | [Sensors](../machine/sensors.md) |
| The cooling service: gates, job-state reports, the verdict file | [Cooling engine](cooling-engine.md) |
| Logging | [Logging](logging.md) |
| The camera privacy gate and the camera sensors | [Video pipeline](video-pipeline.md) |
| The update manager | [Install and update](install-and-update.md) |
| The control panel, as the operator sees it | [Control panel](../../usage/control-panel.md) |
| The machine settings keys | [Settings](../../usage/settings.md) |

## What forgectrl owns

- **Controller-mode supervision.** The selected controller runs as a direct
  child; `POST /mode` switches modes live (idle-gated), a crashed controller
  is respawned after the machine is safed, and forgectrl itself runs under a
  respawn wrapper that retakes supervision once the machine is idle.
- **The pulse-device broker.** forgectrl holds `/dev/glowforge`
  (exclusive-open) for its lifetime and controllers inherit the fd, so mode
  switches, homing handovers, and respawns never close the device or cycle
  the 40 V motor rail. The supervisor is the writers' dead-man.
- **The motion-liveness gate.** The stepper drivers can come out of a rail
  power-up unserviceable while every counter runs normally, so before each
  session's first controller spawn the supervisor commands a small probe
  move and verifies it *physically happened* via the head accelerometer,
  with a rail-off recovery ladder and an explicit `motion-fault` state.
- **The cooling engine.** The single owner of fans, pump, TEC, and the
  flow-check heater for both modes ([Cooling engine](cooling-engine.md)).
- The **web control panel**, **camera service**, **telemetry**,
  **diagnostics**, persisted **machine settings**, the **logging** tree, and
  the A/B **update system**.

## HTTP API

Every state-changing call is behind forgectrl's auth layer: a bearer token
plus origin checks. The token is `/data/forgefirm/panel.token` on the
machine, and the panel page carries it. Unsigned firmware installs
additionally require the physical button held.

The HTTP surface carries accept-side caps: 64 connections in total and 16
per client address (`MHD_OPTION_CONNECTION_LIMIT` and the per-IP limit), so
a flood is bounded before it reaches a request thread. The camera pipeline's
setup children (`media-ctl`, `v4l2-ctl`) run in their own process groups
under a 10 s deadline and are killed past it, so a wedged V4L2 pipeline
costs one bounded error, never a pinned thread.

| Route | Purpose |
|---|---|
| `GET /` | The control panel ([Control panel](../../usage/control-panel.md)) |
| `GET /status` | Machine operational status as JSON: state, position when homed, fans, coolant, switches, `gates_off`, `temps`, `sys`, the `grbl` block ([Telemetry](#telemetry)) |
| `GET /settings` | Current settings as JSON, plus the system hostname, the firmware version, and the `gates` table: range, recommended band, off end, and state per gate setting |
| `POST /settings?key=value&...` | Set any subset of known keys. An empty value clears a key to its built-in default. Refused (409) unless the machine is idle |
| `GET /mode` | Supervisor state: mode, controller (`running`, `stopped`, `standby`, `motion-fault`), pid, motion verdict |
| `POST /mode?controller=grbl` or `=cloud` | Live idle-gated mode switch; also the retry lever after a motion fault |
| `POST /controller/stop`, `POST /controller/start` | The manual emergency lever ([Mode supervision](#mode-supervision)) |
| `POST /cool/state` | Controller job-state report, level-triggered at ~1 Hz ([Cooling engine](cooling-engine.md#job-state-reports)) |
| `GET /cool/status` | Cooling-engine state: phase, verdict, temps, report age, `gates_off`, the effective `limits`, `fan_gates`, `fire_watch`, `accel_watch` |
| `GET /grbl/settings` | The controller's `$$` view, verbatim; 404 with no live controller |
| `POST /curve/record`, `GET /curve/status`, `POST /curve/stop`, `GET /curve/ladder.gcode` | The dose-curve recorder ([below](#the-dose-curve-recorder)) |
| `GET /logs`, `GET /logs/tail`, `POST /logs/export` | The logging tree ([Logging](logging.md)) |
| `GET /cam/stream`, `GET /cam/snapshot`, `GET /cam/status`, `GET /cam/h264`, the mjpg-streamer aliases | The camera service ([Video pipeline](video-pipeline.md)) |
| `GET /slots`, `POST /boot`, `POST /update/check`, `POST /update/download`, `POST /update/apply`, `POST /update/upload`, `GET /update/status`, `POST /restore/factory`, `POST /system/reboot` | The update manager ([Install and update](install-and-update.md#the-update-manager)) |

Settings persist in `/data/forgefirm.conf`, shared with the grblHAL
controller (re-read on every `$H` and at every run start) and the gfhome
homing runner (read at session start), so changes apply without restarts.
Writes are refused (409) unless the machine is idle, because the controller
and the homing runner both read this file mid-run.

**Never poll the Grbl TCP socket for status.** A connection there displaces
the sender's session (LightBurn). Position comes from the kernel step
counters anchored at the last completed homing (`/run/grblhal.homed`,
written by the controller). Controller-side facts reach forgectrl only
through pushed state: the `/run` anchor files, the job-state reports, and
the `grbl.state` file below.

## Switches and button

All switch inputs surface as **EV_SW events on `/dev/input/event0`**
(gpio-keys, per the device tree). Current state is readable at any time via
`EVIOCGSW`; edges arrive as input events. Bit set = switch active.

| EV_SW code | Label (device tree) | Meaning when ACTIVE |
|---|---|---|
| 0 | `door1` | door/lid switch 1 closed |
| 1 | `door2` | door/lid switch 2 closed |
| 2 | `button` | the big button is pressed |
| 3 | `doors` | both door switches closed (the series combination the safety chain sees) |
| 4 | `hv_enable` | the safety chain's HV_ENABLE output is asserted (readback); see below |
| 5 | `interlock` | **remote-interlock loop OPEN**; see below |
| 6 | `interlock_latch` | interlock latch set (LASER_ON blocked in hardware); the kernel sets it while bit 5 reads open and releases it when the loop closes |
| 7 | `head` | head-attention line, **not** a head-present indicator; see below |

**The interlock sense is inverted relative to the door and button
switches.** Bit 5 ACTIVE means the regulatory 2-pin remote-interlock loop is
*open* (lockout engaged = the laser must not fire). Basic and Plus machines
ship the connector factory-jumpered, so the bit stays inactive there, that
is, satisfied; the Pro brings the connector out for an external lockout
chain. Any UI or gate expression must treat `interlock_ok = !bit5`.

**Bit 4 (`hv_enable`) is a readback, not an input.** It mirrors the safety
chain's HV_ENABLE output (`DOORS_OK · WDOG_ALIVE`,
[Safing chain](../machine/safing-chain.md)): inactive at idle, active only
while a run feeds the charge-pump watchdog with the lid closed, and it drops
about 0.45 s after the last pulse. It is telemetry: `/status` reports it and
the control panel shows it, and nothing gates on it. The beam and the HV
supply are already governed by the chain it reads back.

**Bit 7 (`head`) is not head presence.** A gen2 head connected and answering
I²C (`head/info` returns id and serial) reads bit 7 INACTIVE. The line
pulses while the head MCU reboots (hence its 60 ms debounce in the device
tree). Detect head presence via the head driver having probed: the
`/sys/glowforge/head/` group exists (`head/hall_sensor` readable), never
this bit. `/status` `switches.head` reports that presence. The GRBL
controller refuses to arm without it (no lens, no air assist, no beam
detector, and the hardware safety chain does not include head presence).

Who reads what:

- **forgectrl** polls `EVIOCGSW` for `/status` (no exclusive grab).
- **The active controller** reads the button directly (the GRBL arm flow
  waits on code 2; the cloud client's event loop does the same in its mode).
  Button *meaning* is mode-specific by design; the reads stay in-process for
  latency. Outside the arm wait the button is the job pause/resume toggle in
  both modes. In GRBL mode a press while running is a feed hold and a press
  while held is a cycle start. In cloud mode a press is a controlled stop
  plus a laser-off backtrack, and the next press resumes with a laser-off
  lead (the `cloud_pause_backtrack_ticks` and `cloud_resume_lead_ticks`
  settings, factory 2000 and 1950). A held button has no further meaning
  during a job.
- **The active controller also reads bits 3 and 5 for its own motion
  gate.** In GRBL mode they become the core's safety-door signal, and what
  happens next is the `lid_policy` setting. `cancel` (default, the factory's
  behavior): the job parks with a planned deceleration and is then canceled,
  the armed window closes, the reason is reported, a soft reset ends the
  sender's stream with the position kept (no alarm), and the head returns on
  its own to where the job started, lid open or not. `hold`: the stock door
  hold; a cycle start resumes it once closed. During the arm wait (button
  lit) either opening cancels the job outright under both policies. While
  the core is idle, jogging, or homing, and during the return-to-start
  motion after a cancel, the signal is hidden from it, so a lid cycle at
  idle (loading material) never strands the controller in Door; a job
  started with the lid open parks (and cancels) on the first poll. Bit 4
  gates nothing (it is a readback of the chain itself). The cloud client
  reads the same bits itself: lid or interlock open during a print or
  motion (or the pre-print button wait) cancels the job with a controlled
  stop and the print parks with the lid open; a hunt and the park itself
  ignore the lid; the button pauses and resumes a print. It reports every
  lid event to the service.
- **No process takes `EVIOCGRAB`** on the device, the cloud client's reader
  included. Exclusivity of button *meaning* comes from mode selection, and a
  grab starves every other reader of events.

## Safety-chain readbacks

Laser-safety enforcement is the hardware AND-gate
([Safing chain](../machine/safing-chain.md)); everything below is
**monitoring**, plus the one kernel lockout latch. The attribute details are
on [Kernel module](kernel-module.md).

- `cnc/interlock_circuit`: raw safety-chain GPIO bitmask, bit 0 `LASER_ON`,
  1 `LASER_ENABLE`, 2 `BUTTON_LATCH`, 3 `LASER_LATCH`, 4
  `INTERLOCK_LATCH_RESET`, 5 `CHARGE_PUMP_ALIVE`. forgectrl's `/status`
  reports bit 3 as `laser_locked`.
- `cnc/laser_latch` (write): the kernel laser lockout, 1 = the SDMA stream
  cannot enable the laser. Owned by the active controller; locked whenever
  no job is in progress, and automatically on `/dev/glowforge` close.
- `cnc/laser_on[_sampled]`, `laser_pgood[_sampled]`: the gated-output readback
  (the emission witness) and the supply's power-good readback (a supply-fault
  witness), for telemetry.

What forgectrl itself does for laser safety:

- It holds `/dev/glowforge` for its lifetime (the pulse-device broker) so
  controller handovers never close the device, and **relocks the latch
  (`cnc/stop` + `cnc/laser_latch=1`) on every transition out of a running
  child**: unexpected death, mode switch, restart.
- The **cooling engine** is the sole owner of the thermal hardware and
  publishes the fire verdict the controllers enforce; on a FIRE-class
  verdict it writes `cnc/stop` + `cnc/laser_latch=1` itself.
- The **motion-liveness gate** refuses to hand a controller a machine whose
  drivers may have wedged (counters running, motors dead), a laser-safety
  corollary of "counters are not motion".
- `/status` reports the switch map and `laser_locked` (`interlock_circuit`
  bit 3) for the panel and telemetry; nothing in forgectrl reads the Grbl
  socket for machine state. The panel's latch row is labeled *commanded*,
  with the sensed emission row beside it.

## Telemetry

`GET /status` on forgectrl (port 8080) is the machine-state source for every
latency-tolerant consumer: the control panel, the cloud client's reporting,
and anything external. It carries:

- motion state and position (homing-anchored kernel counters);
- fan RPM, coolant temperatures, pump and TEC state;
- the board temperatures (`temps`): `chassis_c` from the LM75, `soc_c` from
  the i.MX6 on-die monitor, `supply_raw` from `pic/pwr_temp` as the count,
  and `soc_throttle`, the kernel's CPU-frequency cooling state (0 at full
  speed); each `null` when absent; watched, not gated;
- the SoC load (`sys`): `cpu_pct`, busy percent from `/proc/stat` over the
  interval since the previous status read (`null` on the first read), and
  `mem_pct`, used percent from `MemTotal` against `MemAvailable`;
- the sampled laser evidence, faults, HV, and lid IR values;
- the switch map above.

### Controller state reports

The GRBL controller publishes its own state as two files under
`/run/forgefirm` (the directory of the cooling verdict file), written
atomically on change from the controller's protocol thread:

- `grbl.settings`: the `$$` view, rewritten when a setting changes or the
  derived floor moves. forgectrl serves it verbatim at `GET /grbl/settings`
  (404 with no live controller).
- `grbl.state`: one JSON object with `ts_mono` for age, the machine state
  and alarm code, the sender session (connected, generation, seconds
  connected, peer address), the laser's armed window, arming wait, dose
  model and floor, the exact `[GC:...]` modal report, the feed and rapid
  override percents, and the driver version; rewritten on change plus a 5 s
  heartbeat. forgectrl echoes it in `GET /status` as
  `"grbl":{"age_s":...,"report":{...}}` only while the supervisor holds a
  live GRBL controller. A dead controller, a torn body, or an absurd age all
  read as no block.

Position stays out of these files by design: it changes per segment and is
served from the homing-anchored kernel counters.

### The dose-curve recorder

The dose-curve recorder (`curverec.c`) measures the tube's own dose curve
from one panel press, with no new emission path. `POST /curve/record`
refuses while the published state file shows a sender connected (the
recorder becomes the machine's one Grbl connection for the run). It saves
and clears `laser_floor_density` and `laser_dose_curve` (so the ladder
measures the raw response; both are restored on every end path), streams the
ladder job itself over the local Grbl socket with ok-per-line flow control
(absolute from X0 Y0, one 100 mm line per rung, the operator's button press
starting the fire with every arm gate standing), and samples
`pic/hv_current` and `head/beam_detect_analog` at 25 Hz, segmenting on the
dark gaps when the ladder has played. `GET /curve/status` reports the state
(`idle`, `waiting`, `recording`, `done`, `failed`), the fitted density:light
points, and the ready `laser_dose_curve` value; `POST /curve/stop` ends or
aborts; `GET /curve/ladder.gcode` serves the exact job the recorder streams,
for inspection. The panel's Apply writes the fit through the ordinary
settings path. This is the one sanctioned Grbl-socket use in the daemon:
gated on the state file's sender flag, local only, one line in flight. The
dose model itself is on [grblHAL driver](grblhal-driver.md).

## Mode supervision

forgectrl owns the controller lifecycle: exactly one of the GRBL controller
or the cloud client runs at a time, spawned as a **direct child** of
forgectrl. The parent-child relationship carries the pulse-device fd under
the broker, and detects controller death the moment it happens. The boot
init scripts do not start controllers; they defer to the supervisor and
remain only as manual emergency stops.

- `GET /mode` returns
  `{"mode":"grbl|cloud","controller":"running|stopped|standby|motion-fault","pid":N,"motion":"verified|unverified|fault"}`.
- `POST /mode?controller=grbl` or `=cloud` is the live switch: idle-gated
  (machine idle, no diagnostic), stops the active controller (SIGTERM to
  SIGKILL escalation on its process group), persists `controller_mode`,
  starts the other, and waits for its first job-state report to reach the
  cooling engine (a slow first report from the cloud client is logged, not
  fatal).
- `POST /controller/stop` and `POST /controller/start` are the manual
  emergency lever (the controller init scripts route here). Stop halts the
  active controller and HOLDS supervision suspended; it is deliberately
  **not** idle-gated, and the exit safing writes run as always. Start
  resumes supervision of the selected mode. A bare `pkill` of a controller
  would just be safed and respawned seconds later.
- **Controller exit safing.** The supervisor safes the machine (`cnc/stop`,
  `cnc/laser_latch=1`) **before it signals a child to stop**, on **every**
  transition out of a running child (unexpected death, mode switch,
  diagnostics suspend, shutdown, the emergency lever), and again
  immediately after any SIGKILL escalation (a killed child runs no cleanup
  of its own). The pre-signal writes are what make the lever immediate:
  motion decelerates and FIRE is severed at the kernel the moment the stop
  is requested, whatever the controller then does with its SIGTERM (the
  GRBL controller treats a termination signal during motion as a `^X`:
  controlled stop, latch relocked, exit). Under the broker a child exit is
  not a final close of the pulse device, so these writes are the safing
  mechanism; both are harmless no-ops when the machine is already idle and
  latched. Unexpected deaths additionally respawn with exponential backoff
  (1 s to a 30 s cap, reset after 60 s healthy).
- **Diagnostics takeover** rides the same machinery: suspend (controller
  down, mode unchanged) and resume. The controller that comes back is the
  selected mode's.
- A **busy** controller survives a forgectrl stop: it is left running
  (unmanaged; its own fd carries the dead-man) rather than e-stopping a live
  job. A supervisor that finds an unmanaged controller, at startup or after
  its own crash-respawn (the init script runs the daemon under a respawn
  wrapper), stands by and **retakes supervision automatically once the
  machine is idle**: it stops the unmanaged controller, holds the pulse
  device, re-probes motion, and starts a supervised controller of the
  selected mode (a new process; the old one's inherited fd cannot be
  adopted). `POST /mode` remains the manual lever.
- **Motion liveness gates the first spawn** of each broker session. The
  supervisor commands a small probe move through its own fd (+X first, then
  back; a cable lives at the end of left travel; laser latched, no axis
  masked, the run-current step settled before sampling) and verifies it
  physically happened via the head accelerometer. A dead verdict runs a
  rail-off recovery ladder (5, 15, 30 s; the DRV8825 drivers can come out
  of a rail power-up unserviceable and need a true power-off to recover).
  If the ladder fails, controllers stay down and `/mode` reports
  `motion-fault` (retry via `POST /mode`, which the panel offers). Position
  counters advancing are never accepted as proof that the machine moved.

Switching modes is a live operation from the panel's Status tab, allowed
only when the machine is idle. The two modes side by side are on
[ForgeFIRM](index.md); the operator's view is on
[Modes](../../usage/modes.md).

## Pulse-device ownership

`/dev/glowforge` semantics (kernel details on
[Pulse feeder contract](pulse-feeder-contract.md)): the device is
**exclusive-open** (a second open fails EBUSY), the `flock` on it arms the
kernel dead-man (**final close of the open file description** mid-program =
emergency stop), and the final close locks the laser latch. The open itself has
no rail side effect; the 40 V rail moves only on `cnc/enable` and
`cnc/disable` writes. A client that disables and re-enables the rail around
its own open cycles it on every handover, and a fast off-on bounce can leave
the supply folded back (counters run, motors dead), which is why the
`rail_settle_s` off-period guards every standalone takeover and why the
broker exists.

**The broker.** The forgectrl supervisor opens the device once (lazily, at
the first managed spawn) and holds it for its lifetime, flock'd. Every
controller it spawns inherits the fd, named by **`GF_PULSE_FD`** in the
child environment; exclusive-open then *enforces* that nothing else can open
the device. The GRBL `$H` homing handover needs no socket passing: the
driver forks the homing runner, so the same fd and environment flow down a
second generation. Writers write the pulse ring **directly** through the
inherited fd; the real-time feed path is never proxied.

- A writer that sees `GF_PULSE_FD` must **never close** that fd, never
  self-open the device, and skip its takeover rail settle (the device, and
  the rail's state, is continuous across handovers). The flock re-lock on
  the shared description is a harmless no-op.
- **Exactly one writer.** The supervisor runs exactly one controller and
  safes the machine before any respawn. Handovers happen only with the
  kernel idle (the driver's suspend gate).
- **Dead-man, re-plumbed.** A writer crash does not produce a final close,
  so the kernel dead-man does not fire on it. The supervisor is the dead-man
  for its writers (`cnc/stop` and `cnc/laser_latch=1` on every transition
  out of a running child, and again after a SIGKILL), and the cooling engine
  is the dead-man for *hangs*: a reporter silent past 5 s with the window
  armed or the kernel still running gets the same two writes
  ([Cooling engine](cooling-engine.md#job-state-reports)). The broker fd is
  opened `O_CLOEXEC` and only the controller spawn clears the flag, so
  helper children (curl, fwup, media-ctl, ...) can never hold the device
  open past an exec and defeat the final-close backstop. Below that remain
  the kernel's own backstops (end-of-data forces the lines low; underrun
  faults; every fresh open starts with the flock dead-man disarmed) and the
  hardware AND-gate, the actual safety boundary. forgectrl dying with no
  writer alive closes the description and trips the kernel dead-man; dying
  while a writer runs leaves the writer's dup as the last reference, so the
  writer's own exit becomes the final close: the kernel backstop either way.
- **Rail policy.** `cnc/enable` and `cnc/disable` are forgectrl's writes
  (the liveness ladder, diagnostics under its takeover rules), and every
  deliberate re-enable observes `rail_settle_s`. **The rail stays up while
  the machine is on; there is no idle-rail-off policy.** The stepper drivers
  can come out of any power-up unserviceable, so each cycle is a fresh
  gamble and the cheapest policy is not to cycle. With a brokered fd in play
  no client writes the rail: no client drops it on a handback or a takeover,
  takeover settles are skipped because the rail never went down (an
  emergency halt may still disable it deliberately), and the GRBL controller
  writes `cnc/enable` at init and at homing resume only when it runs
  standalone, on a device it opened itself (listed in the ownership table
  below).

### Watchdog scope

The i.MX6 hardware watchdog is a boot/system watchdog, not a laser-safety
watchdog. Nothing ties `/dev/watchdog` to controller liveness, motion
liveness, or the armed state, and it must not be mistaken for a beam stop (a
boot-enabled WDT that userspace never opens is petted by the kernel
indefinitely). The fast beam-stop path on a feeder stall is the ring-drain
chain: the ring runs dry, the SDMA script forces the FIRE and step lines low
in the same tick, the driver leaves the running state, the charge pump
self-terminates on its next 200 ms tick, and the HV watchdog disarms the
chain. Cloud mode preloads whole jobs, so its ring does not drain on a
feeder stall; that residual is covered by the cooling engine's
hung-controller dead-man.

## Clocks

The board has no RTC: wall-clock time is whatever NTP last set, and it steps
by years across a cold boot (`ntp.conf` carries `tinker panic 0` so it may).
Every job, timeout, deadline, and freshness comparison in this stack is on
`CLOCK_MONOTONIC`: the verdict `ts_mono` and its 2 s freshness, the report
cadences, the button wait and disarm grace, the dead-man silences, the
supervisor's stop deadlines and respawn backoff, the liveness ladder.
Wall-clock time (`time()`, `CLOCK_REALTIME`) is for display and log stamps
only. **Never put a safety, job, or timeout decision on the wall clock.**

## Hardware ownership

Single-writer rule: each attribute group has exactly one writing process per
mode. Readers are unrestricted. This table is normative.

| Hardware | GRBL mode | Cloud mode | Diagnostics |
|---|---|---|---|
| `thermal/*` fans, pump, TEC, heater; `head/air_assist_pwm`; `head/purge_air` | forgectrl engine (plus the controller's stale-verdict fallback) | forgectrl engine (plus fallback) | forgectrl runner, through the engine's guarded diag writes (take/release; fire blocked) |
| `cnc/*` motion, `/dev/glowforge` ring | GRBL controller, through the brokered fd | cloud client, through the brokered fd | none (controller suspended) |
| `cnc/enable`, `cnc/disable` (40 V rail) | forgectrl (a standalone controller, no broker, enables at init; rail policy above) | forgectrl | forgectrl |
| `cnc/laser_latch` | GRBL controller (locked by forgectrl across handovers and on writer death) | cloud client (same) | none |
| Button LEDs (`/sys/class/leds/button_led_*`) | GRBL controller (arm flow) | cloud client | none |
| Head and lid illumination (camera lamps) | forgectrl (`lamp` on snapshot); the lid lamp's idle level is the `lid_lamp_idle` setting (0 to 255, default 236), asserted at daemon start, on a settings change, and at every controller spawn | the cloud client drives the lid lamp while it runs (its `LLvl`); forgectrl re-asserts the idle level at the next spawn | forgectrl |
| Cameras (V4L2, MIPI mux) | forgectrl; capture only with the lid closed ([privacy gate](video-pipeline.md)) | forgectrl, same gate, including the cloud client's direct-capture fallback | forgectrl, same gate |
| `/data/forgefirm.conf` settings | read (re-read per `$H` and run start) | read | read; forgectrl writes (409 while busy) |
| `/run/grblhal.homed` anchor | GRBL controller writes | none | none |
| `/run/forgefirm/cooling.state` | forgectrl writes, controllers read | forgectrl writes, controllers read | forgectrl writes |
| `/data/log/forgefirm/**` log files | rsyslog writes; every process emits to `/dev/log` only | same | same |

On a kernel dead-man trip (and on module removal) the kernel itself
de-energizes the heat sources, the loop heater and the TEC, and touches
nothing else: the pump, the exhaust and intake fans, and the head airflow
stay with the engine, which keeps circulation and airflow running over a hot
tube.

Diagnostics ownership: forgectrl stops the motion controller, writes the
marker file `/run/forgefirm-diag.active`, and recovers on the next start.
The diagnostics section of the
[bring-up runbook](https://github.com/openglow-org/forgefirm/blob/master/docs/BRINGUP.md)
describes it; the operator's tools are on
[Diagnostics](../../usage/diagnostics.md).

## Verification status

The contract is checked against the device tree (`glowforge.dts` gpio-keys
node), the kernel pages, and a live-board spot-check:

- Attribute inventory: every attribute named in this contract exists under
  `/sys/glowforge/{cnc,head,pic,thermal}`.
- hwmon: `hwmon0` is `imx_thermal_zone` (the CPU die) and `hwmon1` is
  `lm75b`, which is why the chassis sensor is resolved by name, never by
  index ([Sensors](../machine/sensors.md)).
- Switch bits 0 to 3, 5, and 6 are verified against physical state; bits 4
  and 7 are characterized from live readings (see the switch section).
- Sensor conversions are verified against live raws: the coolant beta-3380
  output matches the `/status` values; `tec_temp` reads railed at 1023 on a
  machine without a TEC; the tach periods produce plausible RPM in all three
  unit and pole variants. `pwr_temp` stays a raw count by decision: its
  heatsink cannot be reached with a thermometer while the machine runs, so
  the conversion is not verified, and it is never published as degrees.
- The gates, on the bench: the coolant ceiling trips and turns off by value
  (`cooling.gate-off`); every fan floor trips on an unmeetable floor and on
  an unplugged exhaust fan (`cooling.fan-gate-trips`); a hunt with its fans
  off is measured and not judged (`cloud.mode-switch`); the critical line
  faults over the ceiling's pause on a genuinely rising loop
  (`cooling.critical-tier`); and the header's limits reach the engine on a
  live print (`cloud.pause-resume`). These are acceptance catalog tests
  ([Acceptance](../../developers/acceptance.md)).

The channels and the ownership rules are drilled on hardware, operator
present:

- **Cooling channels.** The idle, run, and cooldown postures hit the exact
  factory duties; a silent controller blocks fire immediately and stands
  down through smoke; an engine killed mid-flood leaves the run fans held,
  the heater dropped by the client, and the sender warned, with the posture
  rebuilt from level-triggered reports within about 2 s of restart;
  over-temp hold and auto-resume inside a running cycle; a ceiling set just
  over its legal minimum trips at the next run start, and a ceiling at its
  top turns the gate off with `gates_off` and the run-start line saying so
  (`cooling.gate-off`); an exhaust floor no fan reaches trips `AIRFLOW`
  after the grace and three ticks, a purge current floor at the rail
  likewise, and a floor of zero reads off (`cooling.fan-gate-trips`).
- **Armed windows.** The fallback rewrites the run duties when the verdict
  goes stale while armed; a controller killed mid-fire drops FIRE with the
  kernel ring's in-flight bytes (tens to about 170 ms, always riding real
  motion) and the supervisor relocks the latch in the same window.
- **Supervision and broker.** Live mode switches both ways, crash respawn
  after safing, diagnostics suspend and resume returning the selected mode,
  a busy controller surviving a forgectrl stop and being retaken at idle,
  and `$H` homing handovers with no device open or close and no rail
  movement.
- **Cloud mode** runs the full stack as an engine client over a multi-hour
  signed-in session, including reconnects and clean stops.

The dated record of each drill is the
[campaign log](https://github.com/openglow-org/forgefirm/blob/master/docs/CAMPAIGN-LOG.md).
