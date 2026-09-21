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
| `kernel-module-glowforge` | `make -C tests check` | The kernel-independent parts of the module, built with the host compiler against `src/`: `interlock_test` (`cnc_interlock.c`) and `backtrack_test` (`cnc_backtrack.h`). Each test is a standalone binary that returns nonzero on failure. |
| `grblHAL-glowforge` | `cmake -B build && cmake --build build`, then the nine test binaries under `build/` | `switch_map_test` (the switch-map decode truth table), `laser_arm_test` (the arm flow: its gates, the button wait, the verdict's tiers, the re-arm), `latch_test` (the latch writer: retries, the fault on a lost lock, the relight rules), `cooling_test` (the verdict client: the tiers by name, the stale pause, the per-poll enforcement), `switches_test` (a lid cancel in flight with the switch device gone), `serial_test` (the RX ring under a sender that ignores flow control, the banner on connect, the TX stall bound), `bind_addr_test` (the listen-address parser), `lens_home_test` (the lens reference and the homing key clamps), `xy_scale_test` (the pinned settings). The host build is the null-sink controller (below). |
| `grblHAL-glowforge`, with the harnesses from `forgefirm/scripts/bench/` | `python3 <harness>.py build/grblHAL_glowforge` for `laser_stream_test.py`, `laser_lifecycle_test.py`, `z_envelope_test.py`, `xy_mode_test.py` and `planner_blocks_test.py` | The laser pulse-stream emission rules, the operator-armed-window lifecycle (below), the Z and X/Y envelopes, the XY microstep modes, and the planner buffer depth. |
| `forgectrl` | `cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS=-Werror && cmake --build build`, then the test binaries under `build/` | One binary per module, `tests/*_test.c`: among them `super_test` (the controller-mode supervisor, one lifecycle pass at a time: death as a signal, the runner and the kernel before a respawn, the enclosure before every spawn, the lever reaching a probe, the safing write's retries, the broker failing closed, the fail-tier restart), `cool_flow_test` and `cool_fanwrite_test` (the cooling engine by inclusion: the flow check, the hang dead-man, the fail tiers' stop hook), `status_idle_test` (`machine_is_idle` fails closed), `enclosure_wait_test`, `lid_gate_test` (the camera privacy gate fails closed), `jobstream_test` (the daemon's own Grbl sender), `sanitize_test`, `debayer_test`, `camhealth_test`, `cool_gate_test`, `airflow_test`, `accel_test`, `lenshome_test`, `coolfmt_test`, `auth_peer_test`, `mp4mux_test`, and the rest. `tests/fflog_e2e.sh` proves the full logging path on a host against a private rsyslogd; `tests/test_devserver_mock.py` holds the panel's dev-server mock to the C tables. |
| `forgeext` | `cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS=-Werror && cmake --build build`, then `caps_test`, `manifest_test`, `state_test`, `super_test`, `holdkeep_test`, `FWUP=<fwup> python3 -B tests/install_test.py`, and as root `./build/sandbox_test`, `tests/netrules_test.py`, and `tests/run_test.py` | The [extension host](../technical/forgefirm/extensions.md): the closed capability list, the manifest parser and each way of being wrong, `state.json`; `install_test.py` drives the built binary against real archives made with fwup and throwaway keys (the tiers, the product gate, a firmware key, a swapped payload, hostile payloads, the key pin, conflicts, the budget, the integrity check, removal), and nothing a refused archive brought stays behind; `sandbox_test` starts a real child under the launcher (root and cgroup v2) and looks at it from inside and from outside; `super_test` runs the supervisor's rules against fake operations and a fake clock; `holdkeep_test` takes what the host says for a package's hold through every case and runs the keeper against a real directory (fresh while the main loop speaks, stale when it goes silent, a clean stop leaving the required files); `netrules_test.py` loads the image's rule file into a network namespace with a peer on a veth pair and drives the allowlist; `run_test.py` runs the host itself in such a namespace against a stand-in for forgectrl's read-only routes and four real packages: the stagger, the confinement, the holds (fresh, raised for a required package that keeps ending and never flickering clear, named for forgectrl, gone with extensions off and safe mode), the armed window, quarantine, a second host refused, a killed host's services swept by the next one, safe mode, and a clean end. |
| `python3-gfhardware` | `python3 -m pytest tests/` (or `python3 -m unittest` per module) | The cloud client: the run loop and its holds (`test_machine_lid_button`), the pulse feeder (`test_feeder`), the power-before-fire check on a job's bytes (`test_pulse_body`), the homing runner's exit (`test_gfhome_exit`), the lid gate, the limits, the shared machine glue. |
| `Glowforge-Utilities` | `python3 -m pytest tests/` | The service layer: the pulse header checks, the pulse source, the offline service, the dispatch, the firmware policy. |
| `forgefirm/forgetest` | `python3 -m unittest discover -s tests -v` | The acceptance tool: the campaign rules, the fingerprints, the artifact build and its verification (the decision of the release gate, with the negative fixtures), the runner and the HTTP API end to end with a fake catalog and a fake bench tool, the suites replayed on the log lines of the machine, and the check that each log phrase the cloud suite looks for is one that the pinned cloud application can log. |
| `forgefirm/fixture` | `CC=gcc sh test/run.sh`, or `./fixture.sh test` | `policy.c` of the bench actuator: the decisions that need no hardware (the channel names, the loop request words, the button pulse clamp, the key comparison). |
| `forgefirm-docs` | `zensical build`, `python scripts/check-style.py`, `python scripts/check-interfaces.py` | This site: a strict build (a broken link fails it), the house-style lint, and the interface-coverage lint ([This site](docs.md)). |

## The null-sink controller

On a host without `GFSINK`, the grblHAL driver runs the real core, the
planner, and the stream code against a null sink instead of
`/dev/glowforge`. With `GFSINK_DUMP` set, it writes each pulse byte that it
would ship to a file. This makes the laser path testable without hardware.
Two harnesses in `forgefirm/scripts/bench/` use it, and both run in the CI of
the driver:

- `laser_stream_test.py` drives small laser jobs over TCP and compares the
  dumped bytes with the kernel feeder contract. The rules:
    - a leading power byte;
    - no back-to-back power bytes;
    - FIRE only in cutting moves;
    - each stream ends FIRE-clear;
    - no FIRE on a stepless gap;
    - no FIRE leak across cycle churn;
    - the rapids after an M5 executed at idle ship dark;
    - the next job in the same process fires at the level where the
      previous job ended;
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
    - one arm for each job, with M5/M3 persistence;
    - the M2 close;
    - the re-consent after a sender change, and the hold that a sender
      change puts a running job into;
    - the disarm grace that counts down in Hold, and the resume that
      re-arms a held job (the sender's `~` and the button);
    - the arm refusal under a cooling verdict that blocks;
    - the pause tier that resumes with no press, the fail tier that ends
      the job, a sender change that cancels a re-arm, a jog that does not
      hold the window open, and a press that counts only after the button
      has been seen up.

## Continuous integration

Each repository with host tests runs them on push and on pull request.

| Repository | Workflow | Steps |
|---|---|---|
| `kernel-module-glowforge` | `build` | The host tests. Then a cross build of the module with `KCFLAGS=-Werror` against linux-fslc 6.12, with the Glowforge BSP overlay and patches applied, and with the `imx_v6_v7` configuration plus the `glowforge` fragment. |
| `grblHAL-glowforge` | `build` | The CMake build and the nine C tests. Then a checkout of `forgefirm` for the five harnesses, which run against the null-sink build. The harnesses come from the head of `master` in `forgefirm`, unpinned. Push a harness change before the driver change that needs it. |
| `forgectrl` | `build` | The CMake build with `-Werror`, and every test binary. |
| `forgeext` | `build` | The CMake build with `-Werror`, the five C tests, `install_test.py` against fwup 1.16.0 (the version the image carries), and under `sudo` `sandbox_test`, `netrules_test.py`, and `run_test.py` with the rule file from a `forgefirm` checkout. A test that reports it could not run (exit 77) fails the job. |
| `python3-gfhardware`, `Glowforge-Utilities` | `host-tests` | Every test module, each in its own interpreter. |
| `forgefirm` | `forgetest-ci` | On a change under `forgetest/`, the gate and manifest scripts, or the component recipes. Steps: the tree manifest from the recipe pins (`scripts/manifest-from-tree.py`, which also gets the pinned application sources that the log-phrase check reads); the unit tests; the shared-UI check (`scripts/check-ui-vendor.py`: the `theme.css` and the vendored Bootstrap of the page are byte-identical to those of forgectrl at its pinned revision); the coverage lint with `--enforce`; and a gate self-check (the gate refuses an empty artifact with exit status 1, never with a traceback). |
| `forgefirm` | `fixture-ci` | On a change under `fixture/`. Steps: the policy host test with gcc, and the firmware build in the pinned ESP-IDF container with a placeholder `fixture.env`. Thus a change that does not compile never reaches a bench. |
| `forgefirm` | `sandbox-ci` | On a change to the `forgefirm-sandbox` recipe or to the test. One step: `scripts/sandbox-rules-test.py` as root, which loads the [extension sandbox's](../technical/forgefirm/image-and-bsp.md#the-extension-sandbox) rule file into a network namespace of its own, joins a second namespace to it with a veth pair (a peer that is not the machine), and sends from real uids. A pool uid is refused on loopback (IPv4 and IPv6), at its own LAN address, and at the peer (TCP at once, UDP with `EPERM`); root and the uids on either side of the pool are not touched; an allowlist chain opens one port of the peer to one uid; with loopback and the machine's own address on its allowlist a pool uid is still refused there; and loading the file again takes the allowlist away. |
| `forgefirm-docs` | `check`, `deploy` | The strict build and the two lints, on each pull request and push. `deploy` publishes `main` to GitHub Pages. |

## Coverage currency

The release gate reads the coverage maps of the acceptance catalog. Thus
each change is evaluated against the catalog, in addition to its unit tests:

1. Does an acceptance test exercise the changed behavior? If not, add one or
   extend one in the same change.
2. Does the `covers` map of that test name the files that you touched? If
   not, widen it in the same change.

Exercise a gate or a limit through the settings API. Set a value that a
healthy machine cannot meet. The engine reads it again at the next run
start, and the teardown of the test restores it. Never use the `GFCOOL_*`
environment overrides for this. They need a daemon restart, and they stay
bench-only.

A behavior change with no catalog consequence needs a sentence of
justification in the commit message. A coverage gap is a defect. Under the
domain model, an uncovered path lets an inherited PASS stay valid across a
change that must have invalidated it.

The mechanical floor is the coverage lint:

```
python3 -m forgetest.coverage --manifest <manifest.json> [--enforce]
```

It lists each manifest path that no test covers, minus the non-behavioral
paths. Those are documentation, CI, the unit tests of the components, and
licenses; the list is `NON_BEHAVIORAL` in `forgetest/forgetest/manifest.py`. It also
lists each coverage entry that selects nothing. CI runs the lint on a
manifest from the recipe pins (`scripts/manifest-from-tree.py`; no Yocto
build is necessary) and fails the job on an uncovered path. On the board, run
it against `/etc/forgefirm-manifest.json`. The lint proves that a file is
*fingerprinted*. Whether the test *exercises* the change is the judgment of
the author of the change (rule 1). The contract behind this, with the
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
