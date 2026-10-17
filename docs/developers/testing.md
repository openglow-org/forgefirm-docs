---
title: Test
---

# Test

A feature or fix is not complete until it is proven. The order of preference for proof:

1. A host test that runs in CI.
2. A bench drill on [the bench reference](../technical/machine/index.md#the-bench-reference),
   recorded in the commit message that carries the change.
3. Documented reasoning.

A change that can put energy where it was not commanded gets a regression
test with the feature or fix, not after it ([Contribute](contributing.md)). This page
is the inventory. It lists the host tests in each repository, the CI
workflows, and the tests of the acceptance tool. It also gives the coverage
rule that connects a code change to the release gate.

## Host tests, for each repository

| Repository | Command | What it proves |
|---|---|---|
| `kernel-module-glowforge` | `make -C tests check` | The kernel-independent parts of the module, built with the host compiler against `src/`: `interlock_test` (`cnc_interlock.c`) and `backtrack_test` (`cnc_backtrack.h`: the ring arithmetic and the run-start gate's answer). Each test is a standalone binary that returns nonzero on failure. |
| `grblHAL-glowforge` | `cmake -B build && cmake --build build`, then the eight test binaries under `build/` | `switch_map_test` (the switch-map decode truth table), `laser_arm_test` (the arm flow: its gates, with the arm refused under a verdict that blocks and the engine's acknowledgment waited for inside the fan grace; the button wait, where a press counts only after the button has been seen up; one arm for each job, with the window kept through S changes and M5/M3 toggles; the verdict's pause and fail tiers under an open window; the re-arm of a held job and the sender change that cancels it; a jog that does not hold the window open), `latch_test` (the latch writer: retries, the fault on a lost lock, the relight rules; the kernel run requests: the run gate (no request while the kernel plays, and a run only over exactly the bytes that the stream wrote for it, so a stop's residue, bytes that another writer added, or a state or a count that cannot be read faults the stream), the request that waits on a playing kernel and ends with its stream, the underrun under it and at a run start, the retry asked for once and read with the state after it, a refusal at idle other than on an empty ring, a run start that finds its bytes gone, no run over a failed stream; the mid-run check: a kernel that stops under a live stream, by an underrun or another writer's stop, faults it with no run over the residue; no second alarm for a fault another thread lands during a state read; a reset's dropped backlog leaves no step in the ring; the reset during motion: the kernel's stop and the clear, whether or not the stream's run is still the engine's, the dropped backlog, the dark pad behind a lit byte, and the position read-back: the step the core counted for a pulse start that never came, the backlog, and the residue from the kernel's step counters, a count that cannot be read or a counter zero under the clear's read losing the position, and the null sink's clear with no seek, a reset that lands after the core's own idle ended the stream, which still gets the stop and the read-back while a device handed over owes nothing, and a failed stream's reset during motion that owes no read-back but still clears the residue), `cooling_test` (the verdict client: the tiers by name, the stale pause, a stamp ahead of the reader's clock taken as no verdict, the per-poll enforcement, the arm-time gate that waits on the engine's acknowledgment, and the engine's verdict file with `GFSINK` set, whatever `GF_VERDICT_FILE` names), `switches_test` (a lid cancel in flight with the switch device gone; with `GFSINK` set, no switch source from `GF_SWITCH_FILE`), `serial_test` (the RX ring under a sender that ignores flow control, the banner on connect, the TX stall bound, the keep-out: a sender from the network turned away, one from the loopback admitted, the line in flight; the `-b` listen address: an IPv6 literal as written, an IPv4 literal in its v4-mapped form written whole, a host name and a short dotted form refused; the start notice, run through the entry point: one line that names the overrides in force, names only, none when none is in force, and no test hook with `GFSINK` set; its two lists held to the sources, a getenv with white space before its parenthesis included, and each test hook in the environment read only through `gfio_test_hook` and each exempt argument matched once), `lens_home_test` (the lens reference and the homing key clamps), `xy_scale_test` (the pinned settings). The host build is the null-sink controller (below). |
| `grblHAL-glowforge`, with the harnesses from `forgefirm/scripts/bench/` | `python3 <harness>.py build/grblHAL_glowforge`, on a build configured with `-DGFMCODE_WAIT_S=5.0`, for `laser_stream_test.py`, `laser_lifecycle_test.py`, `z_envelope_test.py`, `xy_mode_test.py`, `planner_blocks_test.py`, `ctlport_test.py`, `mcode_test.py`, `envelope_test.py`, `manual_home_test.py`, `cool_report_test.py` and `tray_test.py` | The laser pulse-stream emission rules, the operator-armed-window lifecycle (below), the Z and X/Y envelopes, the XY microstep modes, the planner buffer depth, the controller port, the M-code wait, the bed-size envelope, the manual home, the cooling report's secret, and the crumb tray. |
| `forgectrl` | `cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS=-Werror -DFORGEEXT_SRC=<forgeext checkout>/src && cmake --build build`, then `ctest --test-dir build`; without `FORGEEXT_SRC` the configure leaves out `holds_wire_test`, and says so | One binary per module, `tests/*_test.c` (each a ctest case; `fflog_e2e_test` runs inside `tests/fflog_e2e.sh`): among them `super_test` (the controller-mode supervisor, one lifecycle pass at a time: death as a signal, the runner and the kernel before a respawn, the enclosure before every spawn, the lever reaching a probe, the safing write's retries, the broker failing closed, the fail-tier restart with the safing pair before its SIGTERM), `cool_flow_test` (the cooling engine by inclusion: the flow check, the hang dead-man, the fail tiers' stop hook, the verified fan writes, the intakes fitted, the verdict file's keys and its stamp), `status_test` (`machine_is_idle` and the camera privacy gate's lid read fail closed; the sys, grbl and lens blocks of `/status`), `enclosure_wait_test`, `jobrun_test` (the job runner and the daemon's own Grbl sender under it), `sanitize_test`, `debayer_test`, `camhealth_test`, `cool_gate_test`, `holds_wire_test` (the extension host's real hold files read by the engine's reader, built from forgeext's `holdkeep.c`), `airflow_test`, `accel_test`, `lenshome_test`, `wizlive_test` (the live session's exit, wizlive.c by inclusion: the lens stepped only with no controller and the engine idle, else the marker dropped; the posture and the controller handed back), `coolfmt_test`, `auth_scoped_test` (the guards' judgment of a scoped token, and the loopback peer check), `mp4mux_test`, and the rest. `tests/fflog_e2e.sh` proves the full logging path on a host against a private rsyslogd; `tests/test_routes.py` holds the route table: every route the panel calls is registered, every route carries its capability, and every page carries the page policy, and the daemon's list of environment variables, which its start notice names. `tests/wizard_walk.py` walks the first-run page as bundled, in headless Chrome against the dev server's mock, from the documents to the choice onto the panel, and again, from `tests/host_setup.sh`, against the daemon it starts; against the mock, a diagnostic start on the panel that the cooling engine refuses goes once more a second later, and not after a later press or the operator's Abort, which also clears the press's starting text, and a start refused for another reason shows at once and goes once. `tests/host_start.sh` runs the built daemon on a host with its machine paths in a temporary directory: one read answered, no controller started, and the start notice naming the overrides that are set, names only. The other host scripts take the image's ulfius, which `tests/ulfius_image.sh` builds from the `forgefirm` recipe: `host_routes.sh` brings the controller up on a host (the report channel, the event streams' cap, the motion routes to the port, the extension and setup routes); `host_ext.sh` drives the extension host's routes against a compiled stand-in for the host; `host_setup.sh` the setup gate, its consents, the checks, and the first-run page walked against the daemon; `host_lease.sh` the machine lease and the requests refused in its name; `host_guard.sh` the factory return refused without `confirm=1`, the slot inventory, the setup record's routes, the log tree, and the sanitized export; `host_lan.sh`, as root in a network namespace, the writes from a LAN peer sent to HTTPS and the camera key read from the LAN; and `host_update.sh` the release check against a local release server and an update job's lease. |
| `forgeext` | `cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS=-Werror && cmake --build build`, then `caps_test`, `manifest_test`, `version_test`, `state_test`, `super_test`, `holdkeep_test`, `httpreq_test`, `api_test`, `evfeed_test`, `settings_test`, `quota_test`, `FWUP=<fwup> python3 -B tests/install_test.py`, `tests/ffx_test.py`, and as root `./build/sandbox_test`, `tests/netrules_test.py`, `tests/run_test.py`, and `tests/sdk_test.py` | The [extension host](../technical/forgefirm/extensions.md): the closed capability list, the manifest parser and each way of being wrong, the firmware's own version file (`version_test`), `state.json`, a package's own settings against the schema its manifest declares (`settings_test`), and what a package's data directory holds against what it asked for, and a measurement that did not complete, a listing that fails part way and a directory swapped for a link while it is measured included, and a file removed while it is measured, which holds nothing (`quota_test`); `install_test.py` drives the built binary against real archives made with fwup and throwaway keys (the tiers, the product gate, a firmware key, a swapped payload, hostile payloads, the key pin, conflicts, the budget, the integrity check, a rollback to the kept predecessor, an install refused after `current` turned, removal), and nothing a refused archive brought stays behind; `sandbox_test` starts a real child under the launcher (root and cgroup v2) and looks at it from inside and from outside; `super_test` runs the supervisor's rules against fake operations and a fake clock (a quarantine whose write fails is held until it is written or the operator lifts it, for a crash, a freeze and a measurement); `holdkeep_test` takes what the host says for a package's hold through every case and runs the keeper against a real directory (fresh while the main loop speaks, stale when it goes silent, a clean stop leaving the required files); `httpreq_test` feeds the API socket's request reader what it takes (a byte at a time too) and what it refuses, each with its status; `api_test` runs the broker's judgment over a fake machine (a capability not held, a machine never asked for a package that may not read it, an answer that is no JSON object, the hold's one closed form, and the events poll: its body's form, what comes back after a sequence number, and when the broker is told to make a request wait); `evfeed_test` feeds the server-sent-events reader the lines forgectrl writes (half an event, a keep-alive, a goodbye, a line longer than it holds) and runs the ring a package reads from (where the present is against the beginning of what is held, a place the feed never had, and a reader a whole ring behind told what it lost), and runs the feeder against a listener that closes every connection, with the wall clock an hour ahead and stepped back inside the feeder's backoff, and fwup's and nft's bounds with the wall clock stepped ten years ahead; `netrules_test.py` loads the image's rule file into a network namespace with a peer on a veth pair and drives the allowlist; `run_test.py` runs the host itself in such a namespace against a stand-in for forgectrl's read-only routes and four real packages: the stagger, the confinement, the API socket used by real sandboxed services (self, the relayed mode, a hold raised and cleared, 403 without the capabilities, sixty requests at once, the socket's owner and mode, a caller that is not the account), the holds (fresh, raised for a required package that keeps ending and never flickering clear, named for forgectrl, gone with extensions off and safe mode), the armed window, quarantine (one the host could not write, held through a destination the operator names and lifted by the operator's enable, one inside the host's turn included, but not by one just before the measurement that set it; a manifest it cannot read; a removal inside a measuring turn), a second host refused, a killed host's services swept by the next one, safe mode, a clean end, the host's start notice naming the environment overrides in force, and its list held to the sources; `sdk_test.py` runs the author's kit (`ffx.py`, `ffx.sh` through curl, and `ffx.h` built static), each as a real package under the host; `ffx_test.py` holds the author's tool to `ffx lint` agreeing with `forgeext inspect` on every fixture, and runs pack, keygen, and new. |
| `python3-gfhardware` | `(set -e; for t in tests/test_*.py; do python3 -m unittest -v "tests.$(basename "$t" .py)"; done)`, with a `Glowforge-Utilities` checkout beside the repository: each module in its own interpreter, as CI runs them, and the first module that fails ends the loop with a failing status | The cloud client: the run loop and its holds (`test_machine_lid_button`), the pulse feeder and its power-before-fire check on a job's bytes (`test_feeder`), the homing runner's exit (`test_gfhome_exit`), the lid gate, the limits and the engine's verdict file as the client reads it (`test_limits`), the shared machine glue. |
| `Glowforge-Utilities` | `python3 -m pytest tests/` | The service layer: the pulse header checks, the pulse source, the offline service, the dispatch, the firmware policy. |
| `forgefirm/forgetest` | `python3 -m unittest discover -s tests -v` | The acceptance tool: the campaign rules, the fingerprints, the artifact build and its verification (the decision of the release gate, with the negative fixtures), the runner and the HTTP API end to end with a fake catalog and a fake bench tool, the suites replayed on the log lines of the machine, and the check that each log phrase the cloud suite looks for is one that the pinned cloud application can log. |
| `forgefirm/fixture` | `CC=gcc sh test/run.sh`, or `./fixture.sh test` | `policy.c` of the bench actuator: the decisions that need no hardware (the channel names, the loop request words, the button pulse clamp, the key comparison). |
| `forgefirm-docs` | `zensical build`, `python scripts/check-style.py`, `python scripts/check-interfaces.py` | This site: a strict build (a broken link fails it), the house-style lint, and the interface-coverage lint ([This site](docs.md)). |

## The null-sink controller

On a host without `GFSINK`, the grblHAL driver runs the real core, the
planner, and the stream code against a null sink instead of
`/dev/glowforge`. With `GFSINK_DUMP` set, it writes each pulse byte that it
would ship to a file. This makes the laser path testable without hardware.
The eleven harnesses from `forgefirm/scripts/bench/` that the CI of the
driver runs all run against the null-sink build. The two lists that follow
are the laser-stream rules and the armed-window walk:

- `laser_stream_test.py` drives small laser jobs over TCP and compares the
  dumped bytes with the kernel feeder contract. The rules:
    - a leading power byte;
    - no back-to-back power bytes;
    - FIRE only in cutting moves;
    - each stream ends FIRE-clear;
    - no FIRE on a stepless gap, read for either power model: no stepless
      run lit for longer than a step interval, and no FIRE tick farther
      than one from every step (the density dither splits a leaked fire
      state into short bursts, so only its distance from a step shows it);
    - no FIRE leak across cycle churn;
    - the rapids after an M5 executed at idle ship dark;
    - an M2 closes the window, and the next job in the same process
      re-arms and fires at the level where the previous job ended;
    - a feed hold leaves no dark ground in either mode: lit into the hold,
      dark while held, lit from the first step out;
    - the verdict's pause tier holds lit into the stop and resumes with no
      press, its fail tier ends the job dark, a sender change holds the job
      with the deceleration dark, and a verdict gone stale holds at its own
      expiry;
    - a producer stall while armed faults the stream with no step burst,
      the same stall unarmed is a warning and the move completes, and a
      stall of the sink's write leaves the producer on pace.
    The stand-in engine takes `GFSINK_STALL_MS` (the producer starved
    once) and `GFSINK_WRITE_STALL_MS` (the sink's write held once), and
    every session reads the latch sideband: with `GFSINK_LATCH_LOG` set the
    controller appends one line per latch write, so a rule can say which
    locks and unlocks a job made.
- `laser_lifecycle_test.py` walks the operator-armed window:
    - the re-consent after a sender change, and the hold that a sender
      change puts a running job into;
    - the disarm grace that counts down in Hold, and the resume that
      re-arms a held job (the sender's `~` and the button);
    - a sender change that cancels a re-arm;
    - a lid opened on a job the button holds: canceled, returned to its
      start, and not resumed by a later press;
    - a `^X` during a move: the kernel's stop (`cnc/stop` in
      `GFSINK_ATTR_LOG`), Alarm with MPos at the X that the shipped
      stream moved, and an unreferenced lens still held after `$X`;
    - a `^X` during the web-service homing session: `ALARM:6`, the
      session's command ended, no stop asked of the kernel, and after `$X`
      the lens still held (a Z jog refused, a program Z move alarmed).

## The frame-isolation harness

What keeps a package's page from reaching anything is the browser: the
sandboxed frame, the policy the frame carries, and the policy of the panel
page around it ([A package's own page](../technical/forgefirm/extensions.md#a-packages-own-page)).
So the proof runs in a browser, and it is not part of CI:

```sh
python3 tools/frame_isolation.py [--port 8091] [--lan] [--once] [--out verdict.json]
```

in the `forgectrl` repository, then open `http://127.0.0.1:8091/harness`.
The harness serves the panel as the dev server's mock does (the files under
`src/ui/`, bundled as the daemon bundles them, with the daemon's page
headers), installs one more package in the mock whose page tries every way
out, and adds a driver script to that one copy of the panel page. The driver
opens the hostile page in its card on the Extensions tab, through the
panel's own `extOpenUi()`, once for the whole battery and once for each
navigation (a navigation that is blocked can still replace the document, so
each gets a frame of its own).

Three listeners stand in for everywhere that is not the machine: an HTTP
server, a STUN server, and a bare TCP listener. The panel's own port records
every request that carries a harness tag, because a request that reaches the
machine is a request too. **Their log is the ground truth**: an attempt
failed only if its tag arrived. A control frame, the same page with no
policy, must get at least ten vectors out, or the run says `NORESULT`,
since a witness that stays quiet in the control is no witness.

| Asserted | Recorded, not asserted |
|---|---|
| No request reaches another address or the machine: fetch, XHR, beacon, WebSocket, EventSource, images, scripts, style sheets, fonts, prefetch and preload, nested frames, objects, media, workers | WebRTC, and a connection hint (`rel=preconnect`): the two ways out that no page policy closes |
| No navigation leaves the frame: `location`, a form, `<meta refresh>`, a link, a popup, the top window | |
| Nothing of the panel is read (its window, its token, its frames, the top location, cookies, storage), and nothing draws over it (fullscreen, a modal, pointer lock) | |
| The bridge answers what the package may use and refuses the rest by name: a capability not held, a camera not held, a call that does not exist, a claim in the message about who is asking; a call to a service goes out for the frame's own package, whatever package the message names | |
| The frame is sandboxed with `allow-scripts` alone and no permissions, its policy is its first element, the panel's label sits outside it, and the panel page sends `frame-src 'none'` | |
| The frame takes the panel's color scheme and the page reads it as its own, with the panel's theme set against the browser's preference | |
| Leaving the Extensions tab stops every page but one granted `ui.background`, which starts with the panel on the Status tab and goes on running; a manifest that asks for `ui.background` without the grant is stopped too | How often a hidden page's timers ran (Chrome slows them) |

The verdict is on the page and in its title, and `--once` exits with it: 0
for `PASS`, 1 for `FAIL`, 2 for `NORESULT`. Chrome and Firefox are the
browsers this project tests, and either can run it headless on a
throwaway profile. Firefox ignores a STUN server on loopback, so its WebRTC
reading needs `--lan` and the workstation's LAN address. forgectrl's
`tests/host_routes.sh` holds the panel page the daemon serves to the same
header.

## Continuous integration

Each repository with host tests runs them on push and on pull request. This
table describes each workflow file as it stands in its repository; the
coverage lint reads a component's workflow at its pinned revision instead
(below).

| Repository | Workflow | Steps |
|---|---|---|
| `kernel-module-glowforge` | `build` | The host tests. Then a cross build of the module with `KCFLAGS=-Werror` against linux-fslc 6.12, with the Glowforge BSP overlay and patches applied, and with the `imx_v6_v7` configuration plus the `glowforge` fragment. |
| `grblHAL-glowforge` | `build` | The CMake build and the eight C tests. Then a checkout of `forgefirm` for the eleven harnesses, which run against the null-sink build. The harnesses come from the head of `master` in `forgefirm`, unpinned. Push a harness change before the driver change that needs it. |
| `forgectrl` | `build` | The CMake build with `-Werror`, with a checkout of `forgeext` beside the `forgefirm` one for `holds_wire_test`, at the head of its default branch, unpinned ([the push order](release-flow.md#the-push-order)), and every C test binary (`fflog_e2e_test` runs inside `tests/fflog_e2e.sh`). The configure reads this workflow and stops on a `*_test` target that no step runs on every run, as the [coverage lint](#coverage-currency) counts a step. Of a step's own `run:` line it takes two forms alone, both narrower than the lint's: `./build/<name>` and nothing else, or, for `fflog_e2e_test`, a line that starts with `tests/fflog_e2e.sh`, after `sudo` and `sh` when given, and holds neither a pipe (\|) nor an `&`. A tree without the workflow file does not configure, and neither does one with an `add_executable()` after the ctest block at the end of `CMakeLists.txt`. `tools/check_ui_js.py`, which parses every script of the bundled pages. `tests/wizard_walk.py`, which walks the bundled first-run page in headless Chrome; the runner image carries Google Chrome, which the Dependencies step checks for, so the walk finds `/usr/bin/google-chrome` (`host_setup.sh` runs it a second time against the daemon). `tests/fflog_e2e.sh` with the image's `rsyslog.conf` from a `forgefirm` checkout, and `tests/host_start.sh`. Then the image's ulfius, which the workflow builds from that checkout's recipe, and against it `tests/host_routes.sh`, `host_ext.sh`, `host_setup.sh`, `host_lease.sh`, `host_guard.sh`, `host_lan.sh`, and `host_update.sh`. Last, `tests/test_routes.py`. |
| `forgeext` | `build` | fwup 1.16.0 (the version the image carries) and the CMake build with `-Werror`; eleven C tests, `install_test.py`, and `ffx_test.py`; and under `sudo`, `sandbox_test` and, with the rule file from a `forgefirm` checkout, `netrules_test.py`, `run_test.py`, and `sdk_test.py`. A test that reports it could not run (exit 77) fails the job. A second job, `holds-wire`, checks out `forgectrl` beside the tree at the head of its default branch, unpinned, and builds and runs its `holds_wire_test` against this tree's `holdkeep.c` ([the push order](release-flow.md#the-push-order)). |
| `python3-gfhardware` | `host-tests` | Every test module, each in its own interpreter, with a checkout of `Glowforge-Utilities` beside the tree at the head of its default branch, unpinned, which the tests import ([the push order](release-flow.md#the-push-order)). |
| `Glowforge-Utilities` | `host-tests` | The whole suite in one `pytest` run, after an editable install of the package. |
| `forgefirm` | `forgetest-ci` | On each pull request, and on a push to `master` that changes `forgetest/`, the gate, manifest, and source-bundle scripts, the overlay `kas/source-bundle.yml`, or a file under `meta-forgefirm/recipes-forgefirm/`. Steps: the tree manifest from the recipe pins (`scripts/manifest-from-tree.py`, which also gets the pinned application sources that the log-phrase check reads); the unit tests; a pyflakes pass over `forgetest` and `tests` that fails on an undefined name, on a pyflakes crash, on a status other than 0 or 1, on a run SIGINT stops, or when pyflakes is absent, and prints the capture when the run fails; the shared-UI check (`scripts/check-ui-vendor.py`: the `theme.css` and the vendored Bootstrap of the page are byte-identical to those of forgectrl at its pinned revision); the coverage lint with `--enforce`; and a gate self-check (the gate refuses an empty artifact with exit status 1, never with a traceback). After the tree manifest, it compares the image's extension key with the key the extension catalog publishes, and the address in the pinned forgectrl's `src/extpkg.h` with the file name that the catalog's publish tool uploads, without requesting that address; the catalog's own check workflow runs the same two comparisons, against forgefirm's default branch, on each pull request and each push to main. |
| `forgefirm` | `fixture-ci` | On a change under `fixture/`. Steps: the policy host test with gcc, and the firmware build in the pinned ESP-IDF container with a placeholder `fixture.env`. Thus a change that does not compile never reaches a bench. |
| `forgefirm` | `sandbox-ci` | On each pull request, and on a push to `master` that changes the `forgefirm-sandbox` recipe or the test. One step: `scripts/sandbox-rules-test.py` as root, which loads the [extension sandbox's](../technical/forgefirm/image-and-bsp.md#the-extension-sandbox) rule file into a network namespace of its own, joins a second namespace to it with a veth pair (a peer that is not the machine), and sends from real uids. A pool uid is refused on loopback (IPv4 and IPv6), at its own LAN address, and at the peer (TCP at once, UDP with `EPERM`); root and the uids on either side of the pool are not touched; an allowlist chain opens one port of the peer to one uid; with loopback and the machine's own address on its allowlist a pool uid is still refused there; and loading the file again takes the allowlist away. |
| `forgefirm-docs` | `check`, `deploy` | The strict build and the two lints, on each pull request and push. `deploy` publishes `main` to GitHub Pages. |
| `forgefirm-extension-alignment`, `forgefirm-extension-automation` | `package` | forgeext's shared workflow (`.github/workflows/package.yml`, with its `kit` action), on each pull request and push: the package's own tests (automation: its unit tests), the package staged as it ships, linted and packed, and a test under the real extension host as root (automation: `tests/automation_test.py`). On a push to `main` whose manifest version has no release, the release job signs the package and publishes it with its catalog record ([A repository for your package](extensions.md#a-repository-for-your-package)). |
| `forgefirm-extensions-catalog` | `check` | On each pull request and push: the extension host of every `forgeext` revision in `hosts`, built from source (`tools/hosts.sh`), and fwup 1.16.0; `tests/check_test.py` and `tests/publish_test.py`, which hold the check and the publish step to what they promise on throwaway catalogs; then the [catalog's check](extension-listing.md#asking-for-a-listing) (`tools/check.py`). A pull request fetches each new record's archive once, and the workflow's cache keeps it by its SHA-256; a push to `main` fetches no archive. Beside it, the firmware job runs the two comparisons of the `forgetest-ci` row. On a push to `main`, the publish job waits for the check job and the firmware job, then signs the index and publishes it when it changed ([How the catalog is built](extension-listing.md#how-the-catalog-is-built)). |

## Coverage currency

The acceptance catalog is for what needs the machine: the safing chain,
laser emission, coolant flow sensing, the real sensors and actuators, real
motion and step timing, the pulse engine of the kernel on the SoC, the
camera pipeline, the boot and the slots of the board, and the hardware
crypto. It is also for what needs an operator to do something that
automation cannot, such as a print from the Glowforge web app. A host test
proves everything else, even when the bench is the quicker place to check
it. A behavior whose inputs can be emulated is software: a coolant reading
past a limit, a switch edge that only triggers a decision, a verdict file, a
settings write.

The release gate reads the coverage maps of the acceptance catalog. Thus
each change is evaluated in two ways:

1. Which host test proves the change? If none does, add a case to the test
   that owns the rule. A host test proves behavior. It does not pin message
   wording, help text, field order, or markup unless the text is the
   contract, and it does not prove a rule a second time.
2. Does an acceptance test exercise the changed behavior on the hardware? If
   it does, the `covers` map of that test names the files that you touched.
   Widen it in the same change. Never add or extend an acceptance test for
   behavior that a host test can prove.

A behavior change with no catalog consequence names its host test in the
commit message. A coverage gap is a defect. Under the
domain model, an uncovered path lets an inherited PASS stay valid across a
change that must have invalidated it.

The mechanical floor is the coverage lint:

```
python3 -m forgetest.coverage --manifest <manifest.json> [--enforce]
```

It lists each manifest path that neither an acceptance test nor a host test
covers, minus the non-behavioral paths. Those are documentation, CI, the
unit tests of the components, and licenses; the list is `NON_BEHAVIORAL` in
`forgetest/forgetest/manifest.py`.

A path that a host test proves, and that no acceptance test exercises on the
hardware, has a row in `HOST_TESTED` in the same file: the component, a
glob, the host test, and the CI workflow that runs it. The last two are each
`<repository>:<path>`: a file of a component, or `forgefirm:` with a path in
the `forgefirm` repository. The null-sink harnesses are `forgefirm:` files
that the workflow of `grblhal-glowforge` runs. A host-tested path is in no
fingerprint, so a change there makes no acceptance run necessary.

The lint also lists:

- each coverage entry and each host-tested row that selects nothing;
- each row whose host test or workflow does not exist;
- each row whose workflow's own `on:` names neither `push` nor
  `pull_request`. The lint reads `on:` as a block mapping, a block list
  (`- push`), one scalar, or a flow list (`[push, pull_request]`), and of a
  flow list only the items on the `on:` line itself. It does not read a
  flow mapping (`on: {push: ...}`), and it does not follow a
  `workflow_call` to the workflow that calls it, so it lists such a
  workflow too. A quoted key counts only in a matched pair of quotes: an
  event key with one stray quote (`push":`) is no event, and the workflow
  then names none;
- each row whose workflow does not check out the test's repository, or has
  no step that runs the test on every run. The lint does not evaluate a
  condition. A step with an `if:` other than the literal `true`, or a
  `continue-on-error:` other than the literal `false`, on the step or on its
  job, counts as no step, even when the condition runs it on every run
  (`always()`, `success()`). Such a checkout counts as no checkout. A key
  with one stray quote (`if":`, `"run:`) at the top level, at a job, at a
  step (its first key, on its dash line, too), or as the first key of a
  list item outside a step (a matrix entry) makes every step of the
  workflow count as no step. The
  lint reads no other condition: not a job's `needs:`, and not an event's
  `branches:` or `paths:` filter. A step that one of these keeps from a run
  still counts, so there the lint is a floor.
  The lint reads a step's `run` text line by line, as `bash -e` or `sh -e`
  runs it. A step whose own `shell:`, or a `defaults: run: shell:` of its
  job or of its workflow, is other than `bash` or `sh` counts as no step. A
  folded block (`run: >`), or a scalar continued on the lines under its
  key, is one line. A command counts on a line that holds it alone, with
  its redirections, or in a pipeline under `pipefail` (`shell: bash`, or
  `set -o pipefail` on an earlier line), and only while `errexit` holds
  (`set +e` clears it). The lint stops at a line with any other operator
  (`||`, `&&`, `;`, `&`, a subshell, a here-document). It also stops at a
  command that opens a compound command or negates a status (`if`, `case`,
  `while`, `until`, a group, a function, `!`), at `exit`, `exec`, `trap`,
  `eval`, `source` and the like, and at a `set` of an option it does not
  follow. No command on that line or after it counts. A `for` loop counts
  as `for <name> in <words>; do` on its own line, body lines that count,
  and `done` on its own line. So `./build/x || true`, `./build/x | tee log`
  with no `pipefail`, and a test after an `exit 0` or a `set +e` line do
  not count, and neither does `./build/x; true`, a form the lint does not
  read. The lint does not read what a loop's body does with the loop's
  name, a `cd` before the test, a `defaults: run: working-directory:`, what
  `PATH` or `BASH_ENV` change, or the runner's operating system, so there
  it is a floor too. Each path is resolved against the step's
  `working-directory` and compared with the test's path in the workspace
  (where the workflow checks its repository out). A command
  runs the test when it is the test (a script run directly, or a C test's
  built binary, `<dir>/<stem>`); when an interpreter (`python`, `bash`,
  `sh`) runs it, or a `for` loop runs over it, by its path or a glob that
  matches the whole path (`tests/test_*.py`); when `python -m unittest` is
  given its file or a dotted name whose module is that file (`tests.test_x`,
  `tests.test_x.Case.test_one`); or when `unittest discover` starts in its
  directory with a pattern its name matches, or `pytest` is given it or its
  directory. `sudo`, `env`, `time`, `command` and `nice` in front of a
  command are passed over with the flags with which they run it
  (`sudo -E`, `env -i`), and so are variable assignments: `command -v`
  prints a path and runs nothing. An argument to any other command (`echo`,
  a build) does not run a test, and neither does a comment, a step's name,
  or a trigger's `paths` filter;
- each row whose workflow should be readable and is not.

The lint reads a component's workflow at its pinned revision, from the
sources that `scripts/manifest-from-tree.py` fetches (`--sources`, by
default the checkout's `.manifest-cache`). CI runs the lint on a manifest
from the recipe pins (no Yocto build is necessary) and fails the job on any
of these. On the board, run it against `/etc/forgefirm-manifest.json`. There
it has neither the checkout nor the sources, so it does not check the
`forgefirm:` files or whether a workflow runs its test, and it says so.

The lint proves that a file is *fingerprinted*, or that a host test which
CI runs answers for it. Whether the test *exercises* the change is the
judgment of the author of the change. The contract behind this, with the
catalog, the fingerprints, the campaigns, and the gate, is the
[Acceptance](acceptance.md) page.

## Work on the acceptance tool

`forgetest` is the daemon behind port 8090 on the dev image. It runs the
catalog against the machine and keeps the append-only result log. It decides
which results still apply to the image that runs. It exports the release
artifact that the gate reads, and it serves the bench diagnostics page
([The bench](bench.md)).

### Add a test

1. Register the test in the subsystem module under `forgetest/suite/` with
   `@test(...)`. Give it an id of the form `subsystem.name`, the kind, the
   hardware, the `mode`, `covers`, `requires`, `always`, and the steps. The
   `mode` is the controller mode that the test needs; the runner switches to
   it first.
2. Write the body. It gets a `Context` with `log`, `check`, `fail`,
   `prompt`, `confirm`, `instruct`, `sleep`, `evidence`, `forgectrl`,
   `sysfs`, `grbl`, and `takeover`. Return normally for PASS. Raise
   `runner.Failed` for FAIL.
3. Run the unit tests and the coverage lint.

### Run the daemon on a workstation

The daemon runs against a mock or a manifest file:

```
FORGETEST_DATA=/tmp/ft FORGETEST_MANIFEST=../tree-manifest.json \
FORGECTRL_URL=http://<machine> python3 -m forgetest --port 8090
```

`scripts/manifest-from-tree.py` makes `tree-manifest.json` from the recipe
pins.

| Variable | Default | Purpose |
|---|---|---|
| `FORGETEST_DATA` | `/data/forgetest` | `results.jsonl`, `bench.jsonl`, the token, `export/` |
| `FORGETEST_MANIFEST` | `/etc/forgefirm-manifest.json` | The image manifest |
| `FORGETEST_PORT`, `FORGETEST_HOST` | 8090, 0.0.0.0 | The listener |
| `FORGETEST_BENCH_DIR` | `/usr/share/forgetest/bench` | The installed bench scripts |
| `FORGETEST_BENCH_DATA` | `<FORGETEST_DATA>/bench` | Passed to the bench tools: the directory for their data files (with `GF_HOST=127.0.0.1` and the panel token in `GF_TOKEN`) |
| `FORGETEST_MARKER` | `/run/forgetest.active` | The takeover marker |
| `FORGECTRL_URL`, `FORGECTRL_TOKEN_FILE` | `http://127.0.0.1`, `/data/forgefirm/panel.token` | The forgectrl client |
| `GF_SYSFS_ROOT` | `/sys/glowforge/` | The sysfs of the kernel module |
| `GRBL_HOST`, `GRBL_PORT` | 127.0.0.1, 23 | The Grbl TCP port |

### Layout

```
forgetest/forgetest/         the package (standard library only)
  manifest.py                the manifest, the globs, the fingerprints, the coverage report
  catalog.py                 the @test registry, the catalog hash
  campaign.py                the rules (pure functions)
  artifact.py                the export and the gate verification
  runner.py                  one run at a time, prompts, abort, takeover, queues
  baseline.py                the fresh-boot idle state around each run
  hw.py / puls.py            the hardware readers; the dark job
  server.py / page.py / ui/  the HTTP API and the page (the access rules of forgectrl;
                             Bootstrap and the OpenGlow theme, shared with the panel)
  bench.py / coverage.py     the bench registry and the subprocess runner; the lint
  suite/                     the catalog, one module for each subsystem
forgetest/tests/             the host unit tests
scripts/bench/               the bench tools (with gfbench.py, the board/host helper)
scripts/acceptance-gate.py   the gate
scripts/manifest-from-tree.py  the manifest from the recipe pins (CI, workstation)
releases/v<version>/         the committed artifacts
```

The [Acceptance](acceptance.md#domain-fingerprints-and-inheritance) page names
the shared judges and says what they mean for the fingerprints.
