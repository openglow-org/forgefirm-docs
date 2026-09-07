---
title: forgectrl
---

# forgectrl

forgectrl is the machine-services daemon of ForgeFIRM. It runs on the
factory i.MX6 control board and serves HTTPS on port 443 and HTTP on port
80. This page is the
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
- **Commissioning.** The first-run setup, the login, and the gate that
  holds every controller until the setup is complete
  ([below](#commissioning-and-the-gate)).

## HTTP API

forgectrl runs two listeners. HTTPS on port 443 serves every route. Its
certificate is self-signed, made at the first start, and kept under
`/data/forgefirm/` across updates. `GET /settings` reports its SHA-256
fingerprint as `tls_fingerprint`; the panel's Commissioning card and
`GET /cert` show the same fingerprint. HTTP on port 80
serves only the read-only routes to the LAN. Those are `GET /status`, the camera routes and the
mjpg-streamer aliases, `/settings`, `/grbl/settings`, `/mode`,
`/cool/status`, `/diag/status`, `/curve/status`, `/curve/ladder.gcode`,
`/slots`, `/update/status`, `/wiz`, `/wiz/advisories/press`, and
`/advisories/<id>`. A state-changing route over HTTP answers a loopback
client only; every other client is redirected to HTTPS. mDNS announces the
machine as `forgefirm.local` and as its fuse hostname `<name>.local`; the
console banner (`/etc/issue`) prints the addresses.

Every state-changing call is behind forgectrl's auth layer: the panel
token plus origin checks, and, once the setup has created the account, a
login session. The session is a cookie, HTTPS only, with a 12 h idle expiry.
The sessions are kept in a root-only file under `/run/forgefirm`, so a
restart of the daemon keeps you logged in and a reboot does not; the login
page returns to the page that sent you to it. Five wrong attempts from one
address lock the login for 30 s. The same name
and password open SSH. The token is `/data/forgefirm/panel.token`, sent as
`X-ForgeFIRM-Token`, and the panel page carries it. A script on the machine
writes with the token alone; so does any client on a development image. A
client on the network needs the session too. The read-only routes answer any
LAN client while `panel_open_reads` is 1 (the default); 0 closes them to
sessions and loopback. Unsigned firmware installs and `GET /fuse-identity`
additionally require the physical button held.

The HTTP surface carries accept-side caps: 64 connections in total and 16
per client address (`MHD_OPTION_CONNECTION_LIMIT` and the per-IP limit), so
a flood is bounded before it reaches a request thread. The camera pipeline's
setup children (`media-ctl`, `v4l2-ctl`) run in their own process groups
under a 10 s deadline and are killed past it, so a wedged V4L2 pipeline
costs one bounded error, never a pinned thread.

| Route | Purpose |
|---|---|
| `GET /` | The control panel ([Control panel](../../usage/control-panel.md)); the setup until it is complete |
| `GET /login`, `POST /login`, `POST /logout` | The login page, the login (`name`, `password`), the sign-out |
| `GET /setup`, `GET /wiz`, `GET /wiz/record`, `GET /advisories/<id>`, `POST /wiz/advisories/accept`, `POST /wiz/advisories/press`, `GET /wiz/advisories/press`, `POST /wiz/advisories/press/cancel`, `POST /wiz/account`, `POST /wiz/preferences`, `POST /wiz/machine`, `POST /wiz/cloud`, `POST /wiz/complete` | The setup ([Commissioning](../../usage/commissioning.md#the-routes)); an advisory's `ETag` is its hash; `GET /wiz` carries the what-changed menu (`changes`) |
| `GET /wiz/record?download=1`, `GET /wiz/record.html`, `POST /wiz/changed` (`what`) | The record as a download named after the sheet id; the printable summary (`recordhtml.c`: one page, no script, every value escaped, the steps in catalog order with the sentence, the settings written with their values before, and the numbers); a replaced part or a service mapped to the wizards to run again (`commission.c`: the table of changes, required for the wizards whose settings were measured on the old part, recommended for the ones that prove it; a required flag never drops to recommended, and a run clears it). The record routes take a login session or the token |
| `POST /wiz/<id>/start`, `POST /wiz/<id>/answer` (`seq`, `value`), `POST /wiz/<id>/abort`, `POST /wiz/<id>/takeover`, `GET /wiz/dark`, `GET /wiz/shot?cam=lid\|head` | The checks (the dark wizards) and the sheet cards (the live wizards): one runs at a time on a worker thread; the status carries the phase, the progress, the time so far, the log, the open prompt with its sequence number and how long it waits (`timeout_s`, `since_s`), the result (a live card's carries a `summary` sentence), the settings the wizard wrote with their values before (`applied`), and the run's ownership (`owned`: a login session drives it; `mine`: the requester's); the login session that started a run answers and aborts it, another session is refused (409) until it takes the run over, and a requester with no session (a tool with the token) is never held back; the shot is the cameras check's last snapshot |
| `GET /wiz/sheet.svg?card=<id>`, `GET /wiz/sheet.gcode?card=<id>` | A sheet card's preview (the drawing the daemon streams, from the record's facts) and its program body; the live wizards stream their programs through the daemon's own sender (`jobstream.c`: lines in flight up to half the controller's RX ring, ok per line, a $ command, M102 and the program end sent alone as barriers, the emission witnesses sampled at 25 Hz) in loopback posture, with the lens referenced on its hall sensor first; the focus card homes the lens on its bottom stop to place the hall edge in the carriage's travel, and its result is the focus model in the lens's own half-steps ([The motion hardware](../machine/motion-hardware.md#the-lens-and-its-travel)) |
| `GET /status` | Machine operational status as JSON: state, position when homed, fans, coolant, switches, `gates_off`, `temps`, `sys`, the `grbl` block ([Telemetry](#telemetry)) |
| `GET /settings` | Current settings as JSON, plus `machine_id` (the fuse-derived identity), the firmware version, `tls_fingerprint`, and the `gates` table: range, recommended band, off end, and state per gate setting |
| `POST /settings?key=value&...` | Set any subset of known keys. An empty value clears a key to its built-in default. Refused (409) unless the machine is idle. `cloud_enabled=1` from 0 takes `phrase=I UNDERSTAND` (400 without it); `cloud_enabled=0` takes `homing_mode` to `none` and `controller_mode` to `grbl` when they point at the cloud |
| `GET /mode` | Supervisor state: mode, controller (`running`, `stopped`, `standby`, `motion-fault`, or `gated` with `why`), pid, motion verdict |
| `POST /mode?controller=grbl` or `=cloud` | Live idle-gated mode switch; also the retry lever after a motion fault |
| `POST /controller/stop`, `POST /controller/start` | The manual emergency lever ([Mode supervision](#mode-supervision)) |
| `POST /cool/state` | Controller job-state report, level-triggered at ~1 Hz ([Cooling engine](cooling-engine.md#job-state-reports)) |
| `GET /cool/status` | Cooling-engine state: phase, verdict, `fire_ok`, `hold`, `resume_ok`, temps, report age, `gates_off`, the effective `limits`, `fan_gates`, `fire_watch`, `accel_watch`, `quiet_hold` |
| `POST /cool/quiet?on=1` or `=0`, with `pump=1` | The quiet hold for a listening to the head accelerometer (the bench tools; the commissioning finder uses the same hold inside the daemon): every fan off, and with `pump=1` the coolant pump and the TEC too, the machine silent. Taken only from an idle machine with no diagnostic running; the engine releases it itself when a run session opens or after 600 s ([Cooling engine](cooling-engine.md#what-the-fans-do-and-when)) |
| `POST /diag/flow-verify`, `POST /diag/flow-calibrate`, `POST /diag/aa-offset-calibrate`, `POST /diag/abort`, `GET /diag/status` | The diagnostics runner ([Diagnostics](../../usage/diagnostics.md)) |
| `GET /fuse-identity` | The machine's fuse identity ([Control panel](../../usage/control-panel.md)) |
| `GET /grbl/settings` | The controller's `$$` view, verbatim; 404 with no live controller |
| `POST /curve/record`, `GET /curve/status`, `POST /curve/stop`, `GET /curve/ladder.gcode` | The dose-curve recorder ([below](#the-dose-curve-recorder)) |
| `GET /logs`, `GET /logs/tail`, `POST /logs/export` | The logging tree ([Logging](logging.md)) |
| `GET /cam/stream`, `GET /cam/snapshot`, `GET /cam/status`, `GET /cam/h264`, the mjpg-streamer aliases | The camera service ([Video pipeline](video-pipeline.md)) |
| `GET /slots`, `POST /boot`, `POST /update/check`, `POST /update/download`, `POST /update/apply`, `POST /update/upload`, `GET /update/status`, `POST /restore/factory`, `POST /restore/factory-return?confirm=1`, `POST /system/reboot` | The update manager ([Install and update](install-and-update.md#the-update-manager)) |
| `GET /system/ssh`, `POST /system/ssh?enable=0` or `=1` | SSH state, and the switch that turns it on until the next reboot; off at every boot, kept on by a development image |
| `GET /system/camera-key`, `POST /system/camera-key?rotate=1` | The per-machine camera key (`/data/forgefirm/camera.key`, 128 bits) with the stream and snapshot URLs that carry it, and its rotation. A valid key, as the `key` query parameter or the `X-ForgeFIRM-Camera-Key` header, authorizes any read-only route on either listener, origin checks included, and never a write |

Settings persist in `/data/forgefirm.conf`, shared with the grblHAL
controller (re-read on every `$H` and at every run start) and the gfhome
homing runner (read at session start), so changes apply without restarts.
The one exception is `xy_microsteps`, which the controller reads at its
start only: a change of its stored value restarts a running GRBL
controller after the write (the machine is idle by the gate below), and
any other controller picks it up at its next start.
Writes are refused (409) unless the machine is idle, because the controller
and the homing runner both read this file mid-run.

**Never poll the Grbl TCP socket for status.** A connection there displaces
the sender's session (LightBurn). Position comes from the kernel step
counters anchored at the last completed homing (`/run/grblhal.homed`,
written by the controller). Controller-side facts reach forgectrl only
through pushed state: the `/run` anchor files, the job-state reports, and
the `grbl.state` file below.

### Commissioning and the gate

The first run of the panel is the setup: the advisories, the account, the
preferences, the machine facts, and the cloud decision
([Commissioning](../../usage/commissioning.md)). It is served at `/` until
it is complete and at `/setup` afterward. The advisories step ends with one
press of the machine's button, requested by `POST /wiz/advisories/press`;
the button breathes teal while it waits. A document that changes in a later
release must be accepted again.

The record is `/data/forgefirm/commissioning.json`. It holds the advisories
with their hashes and acceptance times, the account name, and the machine
facts. It also holds each wizard's completed version with its results and
applied settings, and the flags. The sheet id is derived from the serial with the salt in
`/data/forgefirm/sheet.salt`; it never reveals the serial. The account
record is `/data/forgefirm/users`. The record grows with every result, so
its routes hand out a malloc'd dump, never a fixed buffer; the sanitized
log export carries it as `system/commissioning.json`
([Logging](logging.md)).

The button LED during the setup (`led.c`, written only while no controller
runs): breathing teal for the acceptance press; breathing white while a
wizard holds the machine with the controller stopped (`wiz_controller_stop`
in `wizdark.c` sets it, `wiz_controller_start` hands the LED back dark
before the spawn, since the controller drives it for its arm wait);
blinking amber while a check waits for the lid to close (`wiz_led_attention`),
and for the password reset hold; solid green at completion, out when the
panel is first served.

The gate: until the setup is complete, the supervisor spawns no controller.
The same holds while a required step is out of date or a required flag is
raised. `GET /mode` reports `controller: gated` with `why`, and the panel's
Status tab shows a banner. The file `/run/forgefirm/commissioning-override`,
created as root, lifts the hardware gate until the next reboot. It never
lifts the advisories or the account, and the panel says so.

`cloud_enabled` (0 or 1, default 0) is set by the cloud step. While it is
0, the GF Cloud tab, the Factory cloud button, and the gfcloud homing
choice do not exist. `controller_mode=cloud` and `homing_mode=gfcloud`
are refused, and nothing contacts the Glowforge service. `POST /settings`
takes `cloud_enabled=1` only with `phrase=I UNDERSTAND`, the step's typed
acknowledgment, and `cloud_enabled=0` takes `homing_mode` and
`controller_mode` off the cloud as the step does. The hardware
wizards are the checks (the dark validation) and the sheet (the live
cards); a live card's laser keys (`laser_floor_density`,
`laser_dose_curve`, `laser_corner_gamma`) may be overridden for its one
job, the originals kept in `/data/forgefirm/curverec.saved` so a daemon
restart puts them back.

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

`GET /status` on forgectrl is the machine-state source for every
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
gated on the state file's sender flag, local only, the ring half full at most. The
dose model itself is on [grblHAL driver](grblhal-driver.md).

## Mode supervision

forgectrl owns the controller lifecycle: exactly one of the GRBL controller
or the cloud client runs at a time, spawned as a **direct child** of
forgectrl. The parent-child relationship carries the pulse-device fd under
the broker, and detects controller death the moment it happens. The boot
init scripts do not start controllers; they defer to the supervisor and
remain only as manual emergency stops.

- `GET /mode` returns
  `{"mode":"grbl|cloud","controller":"running|stopped|standby|motion-fault|gated","pid":N,"motion":"verified|unverified|fault"}`,
  with `why` beside a `gated` controller
  ([Commissioning and the gate](#commissioning-and-the-gate)).
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
  ([Cooling engine](cooling-engine.md#job-state-reports)). A controller the
  supervisor stops on purpose is a death, not a hang: the supervisor clears the
  engine's last report at the stop, so the liveness probe it runs next, the one
  program that plays with no controller alive, is not counted as a silent one.
  The broker fd is
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
