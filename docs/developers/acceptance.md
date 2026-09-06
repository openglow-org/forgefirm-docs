---
title: Acceptance
---

# Release acceptance

A ForgeFIRM release is signed and published only when the acceptance
catalog passes on the bench machine, and the result is committed with the
release. This page is the contract. It says what the gate is, how a campaign
runs, how a result stays valid across builds, and what the release pipeline
checks. The coverage rule and the tests of the tool itself are on the
[Test](testing.md) page. The bench diagnostics page and the bench actuator
hardware are on [The bench](bench.md) page. The pipeline is on the
[Release flow](release-flow.md) page.

## The pieces

| Piece | Where | What it does |
|---|---|---|
| **forgetest** | `forgetest/` in the `forgefirm` repository; on the dev image, a daemon on HTTP port 8090 | Runs the catalog against the machine from a self-contained web page. Keeps the append-only result log under `/data/forgetest/`. Exports the release artifact. Serves the bench diagnostics page. Never on a release image. |
| **The image manifest** | `/etc/forgefirm-manifest.json` in each image (`meta-forgefirm/classes/forgefirm-manifest.bbclass`, `forgefirm-image-manifest.bbclass`) | The inputs of the build. For each component: the pinned revision, and one `[path, blob-id]` pair for each source file. Plus the platform identity: the machine, the kernel revision and configuration hash, the device tree hashes, and the layer content hashes. |
| **The artifact** | `releases/v<version>/acceptance.json` (with `acceptance.md`), committed to the `forgefirm` repository and attached to the GitHub release | The export of forgetest. For each catalog test: the PASS that counts, the fingerprint it ran under, and whether it was inherited. Self-hashed. |
| **The gate** | `scripts/acceptance-gate.py`, called by `scripts/release.sh` | Computes the fingerprint of each test again, from the manifest in the release rootfs. Requires that the recorded PASS agrees. |

The manifest is content-defined. `scripts/manifest-from-tree.py` computes
the byte-identical manifest on a workstation, from the recipe pins. Thus the
identity does not depend on the commit or the dirty state of a checkout. The
dev image and the release image come from the same tree in one `bitbake`
run, so their manifests have the same identity.

## The catalog

Each test declares, in code (`forgetest/forgetest/suite/*.py`):

- **kind**: `auto` (no operator), `operator` (prompts, no emission), or
  `live` (laser emission is possible). For a `live` test, the page requires
  the acknowledgment for eye protection, fire watch, and exhaust. The
  physical arm press goes through the normal path of the controller.
  forgetest never touches the laser latch.
- **hardware**: `api` or `takeover`. With `api`, forgectrl and the controller
  stay up. With `takeover`, forgectrl is stopped for the duration, and a
  marker file makes a crash recoverable at the next start.
- **mode**: the controller mode that must be live when the test starts
  (`grbl` or `cloud`), or none. The runner switches the machine to that mode
  before the test, through `POST /mode`, settled and with the Grbl port
  answering. It leaves the machine there. A test with no mode runs in the
  mode that it finds, or manages the mode itself. The `cloud.*` job tests
  do that through `enter_cloud`, which also waits for the service session.
- **covers**: the source paths that the test stands for, as
  `(component, glob)` pairs. A glob anchors at the root of the component
  repository (`forgefirm-app/gfcloud.py`, not `gfcloud.py`). A glob that
  selects nothing is a lint failure. Non-behavioral paths are outside each
  fingerprint: documentation, CI, the unit tests of the components,
  licenses (the list is `NON_BEHAVIORAL` in `forgetest/forgetest/manifest.py`).
  Thus a README edit makes nothing necessary again.
- **requires**: the tests that must be satisfied first. The emission tests
  require the motion and readback tests. This orders the runs. It is not a
  release condition of its own, because the release needs each test
  satisfied anyway. The **Ignore prerequisites** switch on the page lets any
  test start alone. A run that starts that way records the unmet
  prerequisites in its `evidence.prerequisites` and in its log, and the
  prerequisites stay required.
- **always**: membership in the **always-required core**. The core runs in
  each campaign, and it is never inherited. It holds image health, the
  kernel latch and safety readbacks, and one live emission witness with the
  armed-window disarm. The armed kill test (`laser.armed-kill`) stays in its
  domain: the emission witness already carries the core's live proof, and
  the kill path is forgectrl's supervisor, which the coverage map re-requires
  on each forgectrl change.
- **actions**: the machine actions that the test asks for by name (`lid`,
  `interlock`, `button`; see "The operator's part"). An `auto` test declares
  none. The page lists them before a start. A bench actuator that covers a
  channel can do them.
- **precheck**: a condition that the machine must meet for the test to start
  at all, and that the test cannot make for itself. `kernel.fire-line` needs
  HV not reporting good, which is the rule of the kernel for a zero-duty
  latch unlock. `commission.gate-blocks-controllers` needs a completed
  commissioning record to start from. A start that the precheck refuses is
  not a result. The page says why. A queue skips the test with the reason
  and continues. Nothing is recorded. A precheck never names a setting the
  operator should change: a test that needs a setting, a record, or an
  account makes it itself and puts the found state back at the end, so
  every test starts from the page as the machine is, and a queue runs
  through.

Neither `actions` nor `precheck` is part of the definition that the gate
sees. `GET /catalog` on the tool lists the definitions. The page shows them
under the *details* of each test.

## Domain fingerprints and inheritance

The **domain fingerprint** of a test is a hash of three things:

- the `(component, path, blob-id)` triples that its coverage globs select in
  the image manifest;
- the platform identity;
- the hash of the implementation of the test. That is its function,
  decorator included, plus the shared code of its suite module. The shared
  code is everything in the module outside the `@test` functions.

A PASS recorded under fingerprint F applies to each build whose recomputed
fingerprint is F. The same code computes it on the board and in the gate.

The consequences:

- A change to a covered file invalidates exactly the tests that cover it. A
  panel-only change runs the core plus the panel tests again, not the
  cooling drills.
- A platform change (the kernel, the device tree, the content of a layer)
  invalidates everything. Layer content is each file under `meta-forgefirm`,
  `meta-glowforge-bsp`, and `meta-openglow-core`, with two exceptions:
  documentation (`*.md`) and the component pin files. A pin file
  (`<recipe>-pin.inc`) holds only the `SRCREV` of a component and the `PV`
  that moves with it. A pin bump
  is the change of the component, and the component entry already carries
  it file by file. Thus it invalidates the tests that cover the component,
  not the bench. A change in a recipe body is layer content, and it
  invalidates everything. That includes build flags, patches, configuration
  fragments, init scripts, and a third-party pin with no manifest entry. A
  pin written into a recipe body instead of its pin file also invalidates
  everything; that is the safe direction.
- A change in the body of a test invalidates the earlier passes of that test
  and no other. A change to a helper that its module shares invalidates the
  tests of that module.
- "Touched" is computed from the content hashes in the image. It is never
  declared by hand.

## Campaigns

A **campaign** is bound to one image (the manifest content hash) and one
catalog (the catalog hash). The first Start on an image opens one. It stays
open until a **FAIL** (or a test that errors), an **invalidate-all**, an
explicit **reset**, or a different image or catalog. A reboot into the same
image continues it.

For each test, in this order:

1. A PASS in the open campaign, with the current fingerprint, satisfies it.
2. Otherwise, if the test is not core, the tool looks for the newest PASS in
   the history with the current fingerprint. A PASS newer than the last
   invalidate-all is **inherited**. Its origin (run time, image, campaign)
   is kept and exported.
3. Otherwise the test is **required**. The reason is `always`,
   `never-passed`, or `domain-changed`.

**Release authorized** means: a campaign is open, and each catalog test is
satisfied. There is no SKIP. A test that the bench cannot run means that the
release cannot be authorized. That is a catalog change, not a skip.

**Invalidate all** (in the page footer, with a reason) records that the
bench itself changed. Examples: a new tube, a driver swap, cable work, a
judgment call. It forces a full campaign. Nothing before it can be inherited.

**Inheritance is local.** The history that a bench inherits from is its own
results log. There is no import of a published `acceptance.json`. A second
bench, or one whose `/data` was wiped, starts with a full campaign.

## Run a campaign

1. Boot the dev image (`forgefirm-image-dev`) on the bench, after a power
   cycle (see "The baseline"). Open `http://<machine>:8090/`.
2. Read the banner. It shows the image, the manifest identity, and *Release
   authorized*. Tests marked **required** must run. Tests marked
   **inherited** do not.
3. Start the required tests, one by one or through a queue (below). An
   `operator` test asks questions in the run pane. A `live` test needs the
   acknowledgment and the physical arm press. A `takeover` test stops
   forgectrl for the duration. A test whose prerequisites are not satisfied
   is locked until they are, unless the **Ignore prerequisites** switch in
   the Campaign card is on. That switch unlocks each Start. The browser
   remembers it, and a run started under it says so in its record.
4. When *Release authorized* reads *YES*, click **Export release
   artifact**. Download `acceptance.json` and `acceptance.md`. Commit them
   as `releases/v<version>/acceptance.json` and `.md`.

The raw log (`/data/forgetest/results.jsonl`, *Raw log* in the footer) is
the record of the bench. The artifact is the record of the release. The
events of the runner itself go to the **journal** (*Runner journal* in the
footer). Examples: a queue that opens, skips, or stops; a takeover
recovered at start-up; the leftovers that a baseline pass found. The
journal is the `daemon.log` of the daemon under the data directory, and
also syslog under the `forgetest` name. It includes the log of the run in
progress. These events never
go to the campaign card of the page.

### Queues

**Run what is left** offers two queues:

- **Unattended** takes each `auto` test that the campaign does not count as
  satisfied. It needs nobody in the room.
- **Operator and live** takes the `operator` and `live` tests. It needs
  somebody at the machine, because it prompts and it fires the laser.

Each button says how many tests it would run, and it asks before it starts.
The live queue names the tests that fire, and it takes the acknowledgment
once, for all of them. A queue runs one test at a time, in prerequisite
order. It stops on the first result that is not a PASS, because a FAIL
closes the campaign. A test that it cannot start is skipped with the reason
on the page, and the rest continue. That is what occurs to an `auto` test
that waits on an `operator` test: run the attended queue, then the
unattended one again. **Stop the queue** cancels what still waits and lets
the run in progress complete. **Abort** ends that run too. The queue lives
in the runner, so a closed or reloaded page does not disturb the run.

### The cloud tests

The `cloud.*` job tests run **in cloud mode and stay there**. The first one
switches from GRBL mode, once, and waits out the connect-time hunt. The
following ones use the live session again. Nothing switches back after them.
The tests that need GRBL mode (`motion.*`, `laser.*`,
`cooling.fans-quiet-after-motion`, `cloud.mode-switch`) declare it, and the
runner switches back when one of them starts. Thus the mode changes only
where the next test asks for it, never between tests of the same mode.
`cloud.mode-switch` is the one round trip. It carries the two motions that
the service drives. One is the connect-time hunt with the lid open. The
other is the web-service homing (`$H` with `homing_mode = gfcloud`) after
the switch back.

The cloud tests split by what they prove:

- **The service protocol** is `cloud.service-protocol`. It covers sign-in,
  the firmware check, the WebSocket, the hunt, and the image uploads. It
  also covers the download and the lifecycle of a print, as the app sees
  them. The cloud client is
  restarted as the emulator of gfutilities, in the identity of this
  machine, under the `/run/gfcloud-emulate` marker. It answers the real
  service with the canned frames of the dev image and runs the print from
  the app without hardware. Thus only the app must be driven, by a person
  or an agent, anywhere.
- **The service and the machine together** are `cloud.mode-switch` and one
  real print, `cloud.pause-resume`. The print covers the progress, the
  button wait, and the limits of the job that reach the engine.
- **The print behavior of the machine** runs under the **offline service**.
  That behavior is the lid and interlock aborts, the button-wait cancel,
  and a paused print ended by the lid. It also includes a print longer than
  the ring, with the cancel from the app.
  `enter_offline` restarts the cloud client with the `/run/gfcloud-offline`
  marker: no account, no network. The test hands it a synthesized job over
  `/run/gfcloud-offline.sock` and reads the events of the machine back (see
  `forgetest/puls.py` and [Cloud mode](../technical/forgefirm/cloud-mode.md)). Those jobs
  carry no laser command, so nothing is on the bed and nothing burns. The
  arm still unlocks the latch, so they stay `live`. The offline client is
  left in place. The next test that needs the service restarts it
  (`enter_cloud` does), as does a mode switch or a controller restart.

**The coverage maps follow the split.** The protocol test stands for the web
session, the emulator, and its fixtures. The offline tests stand for the run
loop, the hardware it drives, the offline dispatch, and the pulse path.
`cloud.mode-switch` stands for the homing path: the session, the whole
hardware library, `gfhome`. Each of them stands for the common ground of the
client. That is `gfcloud.py`, `ffmachine.py`, the configuration, the
identity, the cooling reporter, and the core of gfutilities with its
transport helpers. The one
real print keeps the coarse maps, all three cloud components whole. It is
the integration, and the floor that the lint needs, so whatever the finer
maps leave out still makes the print necessary again. Thus a sign-in change
makes the protocol test and the print necessary again. A feeder change
makes the offline tests and the print necessary again. A camera change
makes the mode switch and the print necessary again.

**The connect-time hunt is paid only where it is the subject.** A cloud
client that the tool starts for anything else comes up under the
`/run/gfcloud-nohunt` marker. That includes the real client back after the
emulator, a mode that the runner switches to or hands back, and a
controller that it restarts. Its first
settings report is the reconnect form, and the service keeps the head
position it has instead of a homing. The hunt tests (`cloud.mode-switch`,
`cloud.service-protocol`) get their hunt, and so does the one real print.
`enter_cloud` uses a running session again only when that client has hunted
the machine itself, never the emulator, never a no-hunt start. Otherwise it
restarts the client with the hunt. A print placed on a head position that
the service only believes can run the gantry into a rail. The same
holds outside the tool. A machine left in cloud mode by a campaign may not
have hunted since GRBL mode moved the head. Open and close the lid (the
service hunts again), or restart the controller, before a print from the
app. Each marker is one start: the client that reads it takes it down.

### The operator's part

The run card shows **what you will do** before anything is asked. It shows
the `steps` of the running test, or of the attended tests that still wait
in a queue. While the machine is idle, it shows the steps of the test whose
title you clicked. During the
run, those steps come in turn, in one of four forms:

- A **Ready** prompt announces a timed step. It says what occurs on the
  click, and what you do during it. Example: "On Ready the head starts an
  8 s move; press the button once while it moves." Nothing moves until you click.
- A **notice** is a standing instruction with no button. The test shows it
  and watches the machine for the result. A result is a reading of the machine. Examples: the lid
  switch reads open, the interlock loop reads open, the controller enters
  Hold after the press, the client writes its log line. It takes the notice down when it
  sees the result. There is nothing to answer and nothing to race.
- A machine **action** (`ctx.act("lid", "open")`, `("interlock", "close")`,
  `("button", "press", until=...)`) is a notice that the runner manages. The
  wording belongs to the action, and the test adds its context. The reading
  of the machine proves it done. `evidence.actions` in the result records
  each action, with who did it. This is the seam that the bench actuator plugs
  into ([The bench](bench.md), "The bench actuator"). A `fixture` that
  covers a channel does the action instead of the notice, and a test reads
  the same either way.
- A **confirm** is a yes or no that the evidence cannot answer. Two are left
  in the catalog. One is the mark that `laser.emission-witness` leaves on
  the scrap. That mark is the once-per-campaign calibration of the sensor
  witnesses: the beam detector of the head, the HV current, the LASER_ON
  count of the kernel. The other is the own display of the app in
  `cloud.pause-resume`. Sensors replaced the other confirms. The head
  accelerometer answers "did the gantry move". The button LEDs answer "is
  the button dark". The lid lamp, toggled between two snapshots, answers
  "is the camera live".

With the bench actuator up, an `operator` test whose actions the actuator
covers runs in the unattended queue. A `live` test never moves: the fire
watch and the acknowledgment belong to a person.

### The baseline

Each run starts from, and leaves, the fresh-boot idle state. The runner
brackets each test and each bench tool with a **baseline** pass
(`baseline.py`). Before the run, it examines the machine against the
fresh-boot idle state and restores what is off. After the run, on each exit
path (pass, fail, or abort), it restores again. There are two kinds of
item:

- **Fixed** resting values that the boot establishes. They are the defaults
  of the kernel module, the start-up writes of forgectrl, and the init
  writes of the GRBL controller. The kernel values: `motor_lock=0` (every
  axis in the pulse path; the driver's Z soft limit guards the lens), `x/y_mode=8`,
  `x/y_decay=1`, `step_freq=28160`, `ramp_rate=125000`, `streaming=0`,
  `state=idle`, the latch locked, the hold currents. Also the head lamp and
  button LEDs off, the heater and TEC off, and the lid lamp at the
  `lid_lamp_idle` setting of forgectrl. For forgectrl: the controller
  running with motion verified, no diagnostic, the camera engine and the
  cooling engine idle.
- **Preserved** state, with no resting policy, that a run must hand back as
  it found it: the position counters, the settings map, the controller
  mode.

The mode in force decides what the baseline owns. In cloud mode, the own
configuration of the cloud client is left to it. That is the init values of
the GRBL controller, which the client rewrites from each pulse header. It
is also the lid lamp, at its lid-image level, and the position counters,
which each service action re-zeroes. The safety readbacks, the latch, the ring, the module
defaults, and the engines of forgectrl are examined as always. The mode
itself is preserved, unless the run declared the change
(`ctx.mode_changed()`, the cloud tests that enter cloud mode) or the test
declared a `mode`. In that case the runner makes the switch in the pre pass,
before the preserved state is captured. The post pass keeps the mode that
the test asked for. The persisted `controller_mode` setting is never
written back as a bare setting; only the switch keeps it in step with the
live mode.

Deviations are **leftovers**. They are logged in the run pane, kept in the
`evidence` of the result (`baseline.pre`, `baseline.post`), and shown in
the message line of the page. A leftover found before a run belongs to the
previous run. One found after is a defect of the run itself. A takeover run
also captures the kernel attributes that the controller owns, on entry. It
writes them back before forgectrl restarts. Thus the liveness probe of the
supervisor runs on the machine that it expects. The runner waits for
the supervisor of forgectrl to settle (motion verified, or the verdict of
the ladder) before and after each takeover.

**Power-cycle before a campaign.** forgetest takes a **fresh-boot
reference** once for each boot (`/data/forgetest/boot-<boot_id>.json`),
only in the first ten minutes after boot, after the supervisor settles. It
is the whole idle picture of this machine as the image boots it. It is the
check on the fixed values, and the record that a leftover is judged
against. Take
it after a **power cycle**, not after a warm `reboot`. The true fresh state
of the machine is the powered-on one. That state is the own lamp and sensor
defaults of the PIC, with the start-up writes of forgectrl on top.

A displaced head is jogged back along its own path, by the X/Y delta that
the kernel measured. The delta is bounded to 100 mm, and Z is never
touched. Beyond that,
the counters are reported and the run must be fixed. A run that re-zeroes
the counters on purpose (the connect of cloud mode) tells the runner so
(`ctx.counters_rezeroed()`) and hands the head back itself.

## The gate

`scripts/release.sh <version>` builds the release image, reads
`/etc/forgefirm-manifest.json` out of the release rootfs, and runs:

```
scripts/acceptance-gate.py releases/v<version>/acceptance.json <manifest>
```

The gate requires:

- the self-hash of the artifact intact;
- `authorized: true`;
- the catalog in the tree identical to the catalog of the artifact;
- for each test, a recorded PASS whose fingerprint equals the one
  recomputed from the release manifest;
- inherited results not core, and newer than the invalidate epoch.

Any problem stops the script before the signature.
`FORGEFIRM_ACCEPTANCE_SKIP=1` bypasses the gate on purpose and prints a loud
warning. It is never the default. When the gate accepted the artifact, it is
staged and attached to the GitHub release next to `forgefirm.fw`, and listed
in `sha256sums.txt` with everything else attached. When the gate was skipped,
no artifact is attached: the release carries `NO-ACCEPTANCE.txt` instead and
is published as a prerelease, so a rootfs no campaign authorized never
travels with a proof that reads as its own.

Because the dev image and the release image are built from the same tree in
one `bitbake` run, their manifests have the same identity. A pin bumped
after the campaign shows up as a fingerprint mismatch on exactly the tests
that cover it.
