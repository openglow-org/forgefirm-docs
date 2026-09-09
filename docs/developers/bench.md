---
title: The bench
---

# The bench

The bench is one stock machine with the dev image, and the discipline around
it. Almost every measured value on this site was obtained there, which is why
the machine has a name and a definition:
[the bench reference](../technical/machine/index.md#the-bench-reference).
This page is the runbook: the bench machine, the clean-up rule, the bench
diagnostics page, the bench tools, and the bench actuator.

How a result was obtained is recorded in the commit that carried it.

!!! danger "Live fire"

    The bench tools that fire the laser say so. Before such a run, put on
    eye protection, keep a fire watch, keep an extinguisher in reach, and
    make sure that the exhaust runs. Each of these runs waits for the
    physical arm press of the operator. Never leave a live run unattended.

## The bench machine

- **The board.** The bench reference is one Glowforge Basic built in late
  2017; the control board is the same in the Basic, the Plus, and the Pro.
  The bench runs the dev image (`forgefirm-image-dev`) from an SD
  card. The dev image has a BusyBox userland, python3, gdb, and strace. Log
  in over SSH as root; the dev image permits a root login without a
  password. A serial console is available on `ttymxc0`
  ([serial access](../install/serial-access.md)).
- **Deploy a kernel.** Write the new dev image to the SD card again
  ([Build](building.md)). This works because U-Boot (in the eMMC boot0 area)
  reads the saved environment at eMMC user-area offset 0x80000. That
  environment selects the boot device (on the bench, the SD card: `mmcdev=0`,
  `mmcroot=/dev/mmcblk1p1`). U-Boot then loads `/boot/uEnv.txt` and
  `/boot/zImage` from that rootfs partition. Thus the kernel always comes from
  the SD card that you wrote. The full eMMC map is on
  [Boot and storage](../technical/machine/boot-and-storage.md).
- **Hot-swap a module.** A change to the module alone can go on the board
  without a flash: copy `glowforge.ko` over
  `/lib/modules/<kver>/extras/glowforge.ko`, then `rmmod glowforge &&
  modprobe glowforge`. A module reload turns the lid LED off (turn it on
  again through `/sys/class/leds/lid_led*/target`) and resets the analog
  configuration. The first liveness probe after a reload can read NO MOTION
  until the ladder probes again.
- **Hot-swap against re-stamped kernels.** The hot-swap loads only if the
  module was built against the patch state of the kernel that is on the
  board. An edit under the overlay of the kernel recipe (for example
  `glowforge.dts`) re-stamps `CONFIG_LOCALVERSION_AUTO`. The stamp does not
  come back when you revert the edit, because each `do_patch` makes a fresh
  git commit of the kernel tree. Thus, after an edit under the overlay, the
  module ships only with a full image flash. **Kernel and BSP changes ride one
  image flash, in a batch.** A `.ko` or overlay change is validated on the
  image that ships it, never hot-swapped onto a board that you are about to
  flash.
- **Deploy a userspace program.** The controller and the daemon are
  userspace programs. Replace the binary on the board. A flash is not
  necessary. The rootfs is mounted read-only: remount it writable for the
  copy, set the execute bit, and put it back
  ([Image and BSP](../technical/forgefirm/image-and-bsp.md#the-read-only-root-filesystem)):

  ```sh
  /etc/init.d/forgectrl stop; while pidof forgectrl >/dev/null; do sleep 1; done
  mount -o remount,rw /
  cp /tmp/forgectrl /usr/bin/forgectrl && chmod 755 /usr/bin/forgectrl
  mount -o remount,ro /
  /etc/init.d/forgectrl start
  ```

  Wait for the daemon's exit before the remount back: a daemon still
  exiting holds the rootfs open and the remount answers "busy". The same
  remount covers a module copy into `/lib/modules`, a script under
  `/usr/share/forgetest/bench`, and a hot copy of the acceptance suite into
  the Python site-packages (restart `forgetest` after that copy; a suite
  file that fails to import takes the daemon down). `/data` and `/tmp` need
  no remount.
- **Read the state through forgectrl or sysfs, never through the Grbl port.**
  A second connection to TCP port 23 displaces the session that holds the
  port, whether a sender or a drill. Use the `/status` route of forgectrl, or
  the sysfs tree of the kernel module. They give the same state, without
  that effect.
- **Power-cycle before a campaign.** The acceptance tool takes a fresh-boot
  reference once for each boot. Take it after a power cycle, not after a
  warm `reboot`. The true fresh state of the machine is the powered-on one.
  That state is the lamp and sensor defaults of the PIC, with the start-up
  writes of forgectrl on top.

## Bench hygiene

Remove everything that you put on the board for a test, in the same
session. That includes scripts, helper binaries, sample logs, backups,
staged copies, temporary configurations, and `__pycache__`.

- Stage test files in `/tmp`. It is lost at reboot.
- If a file must survive a reboot, put it in the one scratch directory
  `/data/bench-scratch/`. Delete that directory as a whole when the session
  ends.
- Nothing goes loose in `/data`. It holds only the factory state and the
  files of ForgeFIRM: `forgefirm/`, `forgetest/`,
  `ffboot`, `etc/`, and `log/forgefirm/`. Every ForgeFIRM configuration
  file lives inside `forgefirm/`, the settings file included.
- A bench tool that is worth a second use goes in `forgefirm/scripts/bench/`
  in the repository. The dev image installs those tools under
  `/usr/share/forgetest/bench/`. Run them from there.
- Before the end of a bench session, list `/data` and remove what you added.

## The bench diagnostics page

The acceptance daemon on the dev image also serves `#bench`
(`http://<machine>:8090/#bench`). The page is the registry of the bench
tools. It shows, for each tool, its safety class, its argument form, and its
last run. The classes:

| Class | Meaning |
|---|---|
| `dry` | Reads or dry motion. forgectrl stays up. |
| `takeover` | forgectrl and the controller are stopped for the run, and the pulse device is free. This is the same wrapper that the takeover tests use. |
| `scope` | A takeover whose result has a meaning only with the named instrument on the bench. |
| `live` | Emission is possible. The page needs the acknowledgment of the operator and the physical arm press. |

A tool runs as a subprocess with its output on the page. On the board, the
machine is `GF_HOST=127.0.0.1`, the panel token is in `GF_TOKEN`, and the
data files of the tool are under `/data/forgetest/bench/`
(`FORGETEST_BENCH_DATA`). The same scripts run from a LAN host with `GF_HOST`
set. Each tool that can run on the board is registered. Two kinds of entry
stay unported: the CI harnesses of the null-sink controller, and the decoder
of factory `.puls` files. They do not run against the machine at all. They
are listed so that the catalog of what exists is complete. Bench
runs are recorded in `/data/forgetest/bench.jsonl`. They never enter a
campaign.

The runner brackets each bench tool with a baseline pass, in the same way
as each test. Before the run, it examines the machine against the fresh-boot
idle state, and it restores what is off. After the run, on each exit path,
it restores again. A takeover run also records the kernel attributes
that the controller owns on entry, and it writes them back before forgectrl
restarts.

## The bench tools

The tools are in `forgefirm/scripts/bench/`. All of them run on the target
board (dev image, python3 present) unless the table says otherwise. The
tools that also run from a LAN host use `gfbench.py`:

- `GF_HOST` names the machine. sysfs goes through ssh (the `ssh` on `PATH`,
  or the client that `GF_SSH` names, for example
  `GF_SSH='wsl -d <distro> -- ssh'` from Windows). Grbl and forgectrl go over
  the LAN.
- With `GF_HOST` unset, the tools run on the board itself: sysfs directly,
  everything on 127.0.0.1. This is how the bench page runs them. Their data
  files are then under `/data/forgetest/bench/` (`FORGETEST_BENCH_DATA`;
  next to the tool otherwise), and the panel token is in `GF_TOKEN`.

The tools that drive the thermal hardware directly (the flow
characterization family) run with forgectrl, the owner of the thermal
hardware, and the controller stopped. The takeover of the page does that.
From a host, stop them first.

| Tool | Purpose |
|---|---|
| `feeder.c` | The underrun proof. Streams NOP pulse bytes to `/dev/glowforge` with wall-clock pacing, a bounded queue depth, a dead-man flock, and `SCHED_FIFO`. Usage: `feeder <hz> <seconds> <depth_ms>`. Proven envelope: 100 kHz for 120 s under full load, 0.2 ms worst write latency. Cross-compile it with `build-feeder.sh`. |
| `bench_phase2.py` | The end-of-data protocol bench: underrun detection and acknowledgment, the parked no-replay guard, `resume(0)`, continuous-feed stability, 20 run/underrun cycles. Motion-safe (motors locked, laser latched). |
| `check_pwm.py` | The laser PWM register check. Reads PWM2 `PWMCR` and `PWMPR` through `/dev/mem`. Expects divider 13 and about 127 counts, that is about 40 kHz. |
| `pwm_sweep.py` | The LASER_PWM scope test (on the board). `check` = read-only safety readbacks and a PWM2 dump. `sweep` = steps `PWMSAR` through 50, 25, 75, 6, and 100 percent duty with holds of 4 s, then restores. Locked state only (the controller and forgectrl stopped, the pulse device closed: the takeover of the page). The sweep relocks the latch itself. It refuses to write if FIRE reads driven or LASER_ON reads active. |
| `pwm_hold.py` | Holds one `PWMSAR` value for a scope-measurement window (`pwm_hold.py <sar> <seconds>`), then restores. The same locked-state rule and guard. |
| `fire_test.py` | The FIRE drop-timing scope test (on the board). A = latch locked (expects nothing on FIRE or LASER_ON). B = latch unlocked, normal end of data. U = a true underrun. Duty 0 throughout. Refuses to unlock if HV reports good. |
| `pwm_stream_test.py` | The LASER_PWM stream-path scope test (on the board, the controller and forgectrl stopped). Streams power bytes only (no step bytes, no FIRE bits, `motor_lock=15`, latch locked) through `/dev/glowforge`. Thus the scope verifies the real power path, with the run-start duty reset and the consecutive-power-byte drop. Compares the position counters before and after. Exit 0 = the counters did not move, idle at the end, no FIRE or emission read back. |
| `gate_a_kernel_drills.py` | The kernel laser-safety drills (on the board, forgectrl stopped so that the pulse device is free). `K1` = the controlled-stop deceleration floor. `K2` = the resume waypoint obeys the locked latch. `K3` = a latch unlock in the middle of a ramp never re-arms the FIRE drive. Software witnesses (`cnc/state`, `laser_enable`, `laser_on`, `laser_on_sampled`, interlock bit 3) plus the LASER_ON scope point on the PSU connector. K3 refuses to run if HV reports good. |
| `laser_stream_test.py` | The host-side laser pulse-stream emission harness. Runs the native null-sink controller with `GFSINK_DUMP`, drives small laser jobs over TCP, and compares the dumped bytes with the kernel feeder contract ([Test](testing.md)). Runs in the CI of the grblHAL repository. |
| `z_envelope_test.py` | The host-side Z envelope harness (null-sink controller): the Z soft limit belongs to the driver, not to `$20`, so an unreferenced Z stays collapsed to where the lens stands through a `$20` write and a `$132` write, while X and Y stay free. Runs in the CI of the grblHAL repository. |
| `xy_mode_test.py` | The host-side XY microstep mode harness (null-sink controller): `xy_microsteps` sets `$100`/`$101` and the machine tick, a typed `$100` is overwritten, a value that is not a mode falls back to x8, and `$110`/`$111` are held under a lowered tick. Runs in the CI of the grblHAL repository. |
| `planner_blocks_test.py` | The host-side planner buffer depth harness (null-sink controller): the controller restarted at `$398` 400 and 1000 answers, reports the depth and runs a move. Runs in the CI of the grblHAL repository. |
| `laser_lifecycle_test.py` | The host-side lifecycle harness of the operator-armed window (null-sink controller) ([Test](testing.md)). Runs in the CI of the grblHAL repository. |
| `live_fire_drills.py` | **LIVE LASER** drills, on the board (the bench page) or from a LAN host (`GF_HOST`): `live_fire_drills.py <drill> [S] [F]`. The drills are listed below. Each drill waits for the physical arm press of the operator. |
| `pacing_test.py` | The protocol-loop pacing check (on the board, dry motion). The idle state and the parked-in-Hold state are coarse-paced. Active motion is tight-paced. A feed hold and resume in the middle of a move keeps the position, with no feeder starve. |
| `gfbench.py` | Not a tool: the helper that the board and host tools share. `HOST` and `LOCAL` from `GF_HOST`; `board(cmd)` (a local `sh -c`, or ssh); the factory coolant conversion `degc()`; `data_path()` (`FORGETEST_BENCH_DATA`, or next to the tool); the HTTP API of forgectrl with the panel token; `setting(key)` (from forgectrl, or from `/data/forgefirm/forgefirm.conf` on the board while forgectrl is stopped). |
| `fan_test.py` | The fan and coolant bench (board or host; the controller runs). Takes a snapshot of the fan PWMs, the tachometers, and the temperatures. Drives M8 (the cut fans), then M9 (cooldown, then idle). Verifies through the tachometer readbacks. |
| `fan_floor_measure.py` | The numbers that the airflow gates ship with (board or host). `spinup` opens a run session with M8 from idle and samples the four tachometers and the purge current at 1 Hz. It reports, for each fan, the steady speed, the time to 90 percent, and the spread over the steady window, plus the purge current at idle and at run duty (the pump is always on; a dead pump reads about 1), and candidate floors at 55 percent. `cut` only samples, during a real cut, for the spread under load. Results as JSON in the bench data directory. |
| `flow_characterize.py` | The coolant flow characterization with the factory temperature curve (board or host; forgectrl and the controller stopped): baseline, flow, no flow, recovery. Prints the ΔT bands and their separation. Takes the heater duty as an argument (`flow_characterize.py 30`). Aborts if the downstream sensor passes 45 °C. |
| `flow_matrix.py` | **The flow-detection design matrix** (board or host; forgectrl and the controller stopped; with `flow_sampler.py` from `/usr/share/forgetest/bench/`). Duty × duration × flow/no-flow, each run from a common cooled baseline, with interleaved repeats. One heating trace gives the metric at each candidate duration. Thus cost and precision come from the same 60 runs. Prints a cost table, a precision table (mean ± sd, worst-case margin, d′), and a ranked shortlist. `flow_matrix.py [duties] [repeats]` (or the environment variables `FM_DUTIES`, `FM_REPEATS`, `FM_RESULTS`). Results and log in the bench data directory. Resumable. |
| `flow_sustained.py` | A long run of the real re-check cadence through M8 (board or host; the controller runs). Counts the verdicts and the false faults against the configured `cool_flow_rise`, and follows whether the loop accumulates heat. `flow_sustained.py [minutes]`. |
| `temp_calibrate.py` | The coolant temperature spot-check helper (board or host): `watch [seconds]`, `point <measured_C> [note]`, `fit`. Pairs a measured temperature with averaged raw ADC readings and fits a per-machine line, to compare the factory curve with a thermometer. The points accumulate in `temp_calibration.json` in the bench data directory. The `supply-*` modes (`supply-watch`, `supply-point <C>`, `supply-fit`) do the same for the sensor of the power supply (`pic/pwr_temp`, raw) against a thermometer on its heatsink. The fit is printed next to the unverified guess on the [Kernel module](../technical/forgefirm/kernel-module.md) page. Three points during a long cut settle it. |
| `critical_tier_drill.py` | The coolant critical tier on a rising temperature (board or host). Sets the ceiling, the resume gate, and the critical line a few tenths above the live upstream reading. Then it lets the flow-check heater of the engine warm the loop through them in one `M8` session. Expects `OVERTEMP` at the ceiling, then `CRITICAL` (fire blocked, hold, no resume), with the fault that ends at `M9`. Restores the settings and cycles a session, so that the engine reads them again. Results as JSON in the bench data directory. |
| `flow_warm_validate.py` | Runs the real check from a heater-warmed baseline (board or host; forgectrl and the controller stopped; `flow_warm_validate.py [cycles_per_case]`). Results and log in the bench data directory. Exit 1 if a run is misclassified. Note the ceiling: 100 percent duty pushes the downstream sensor past 50 °C in 30 s while the bulk hardly moves. Thus warm-loop validation above about 23 °C needs the laser, not the heater. |
| `flow_recheck_char.py` | Characterizes short in-run re-checks and the differential metric (board or host; forgectrl and the controller stopped; `flow_recheck_char.py [heater_pct] [window_s]`). Shows why over-temp cannot see a stopped pump, and why passive warming trends are ambiguous. |
| `flow_confirm_drill.py` | The coolant flow suspicion and confirmation drill (on the board). One continuous M8 session walks the verdict state machine through real pump-off transients: verified, SUSPECT (with an immediate re-check), cleared, SUSPECT, FAULT (consecutive), recovered. Prints PASS or FAIL for each transition. Leaves the machine idle (M9, pump on, heater off). |
| `flow_escalate_drill.py` | The coolant starved-re-check escalation drill (on the board; the controller runs). Sets the confirmation budget of the engine, `cool_confirm_max_s`, to a short value through the settings of forgectrl (`flow_escalate_drill.py [budget_s]`, default 60, the minimum of the setting), and restores it after. With the pump off, the job-start check reads SUSPECT, the stagnant loop cannot pass the settle gate in the budget, and the engine must escalate to FAULT. PASS or FAIL (exit status). Leaves the machine idle. |
| `flow_sampler.py` | The board-side coolant sampler that the flow tools use (`flow_sampler.py <duration_s> <interval_s>`, prints `elapsed,raw_down,raw_up`). Run it on the board (dev image: `/usr/share/forgetest/bench/`), so that the cadence does not depend on the ssh latency. |
| `build-glowforge.sh` | Cross-compiles **grblHAL-glowforge** (the driver repository) in the Yocto build environment, with the toolchain of the recipe. Run: `bash <path>/build-glowforge.sh` (from Windows, start it through the WSL distro from PowerShell; Git Bash mangles the mount paths). Environment: `FF_SRC_TOP`, `FF_BUILD_TOP`. This is the production controller build. |
| `build-forgectrl.sh` | Cross-compiles **forgectrl** (the daemon repository) in the same way, with the toolchain from the work directory of the forgectrl recipe (run `bitbake forgectrl` again after a clean). |
| `build-feeder.sh` | Cross-compiles `feeder.c` in the same way. |
| `accel_fast.py` | A direct-I2C sampler for the two LIS2HH12 accelerometers on the head bus (on the board). Unbinds and rebinds `st-accel` around the capture, 800 Hz ODR, about 270 Hz polled for each device. Optional jogs in the middle of the capture, through the local grblHAL TCP port. CSV to `/tmp/accel.csv`. The head accelerometer is i2c-3 address 0x1e. |
| `bump_seek.py` | The accelerometer bump-seek homing prototype (on the board). Creeps toward a rail in bounded jog segments through grblHAL TCP, learns the moving-noise baseline for each segment, detects the contact jolt (about 530 Hz sampling, 2-sample confirm), cancels the jog (0x85), and backs off. CSV to `/tmp/bump.csv`. |
| `puls_profile.py` | Decodes factory `.puls` streams (raw or with a GF1 header) into velocity and acceleration profiles: the peak speeds, the ramp-slope fits, the segments for each move, the Z cadence. Runs anywhere (standard library only). The source of the factory-true grblHAL defaults: 700/590 mm/s² acceleration, 200 mm/s maximum rate, 28160 Hz travel tick. |
| `cp_watchdog_timing.py` | The one-shot timing of the HV charge-pump watchdog (on the board). Latches each CHG_PUMP feed pulse in the edge detector of GPIO3 (pin 24 only, IMR untouched, ICR2 restored on exit) and polls the `!Q` (`charge_pump_alive`) and `!HV_ENABLE` (`hv_enable`) pads through `/dev/mem` in a tight loop, while it commands short local jogs. Prints, for each run, t_w (the last pulse to the fall of Q), the delay from Q to HV_ENABLE, the priming latency, and the feed period, with the worst gap of the loop as the resolution. Motion only, laser locked, no other Grbl client attached. |
| `resume_dark_lead.py` | The pause and resume timing of the safety chain (on the board, as root). Samples LASER_ON, FIRE, HV_ENABLE, the charge-pump watchdog, the button, and the doors from the SoC pads through `/dev/mem` at about 2 kHz, with the motion dated from the kernel step counters, across a pause and a resume that the button presses of the operator drive. Reports how long HV_ENABLE survives after the stream stops, how fast the chain re-arms on the resume, and, with `--run live`, the dark lead between FIRE on again and LASER_ON that follows it, in milliseconds and in millimeters at the feed of the job. `--run dry` (the default) commands no laser at all. `--auto P,R` drives the pause and the resume with `!` and `~` for an unattended rehearsal. `--run live` needs the arm press and the live-fire precautions. GRBL mode, no other Grbl client attached. |
| `pgood_probe.py` | The supply's power-good line against the laser chain (on the board, as root, no scope). Polls the kernel's readbacks (`laser_pgood` as the raw pin level, `laser_on`, `laser_enable`, `charge_pump_alive`) and the switch device's HV_ENABLE and doors bits at a few hundred hertz, with `hv_current` at 20 Hz, and prints every transition with a timestamp plus a per-line summary. Drive the machine meanwhile (a dry jog, an armed cut, a pause, a lid open); the probe only watches. It needs no file on the board: run it as `python3 -` over an ssh session with the script on standard input. |
| `bench_m2.py` | The motion-quality bench. Runs against the board over TCP port 23: bounded round-trip jogs (sanity, maximum rate, diagonal) and a feed hold and resume in the middle of a move. Reports the peak feed, the state transitions, and the position drift. |
| `xy_pattern_accel.py` | The XY microstep modes by the head accelerometer with the machine silent (on the board, the machine homed and standing at home, the lid closed, no other Grbl client). Per mode given (default 8, 16, 32) it stores `xy_microsteps`, waits for the restarted controller, takes the cooling engine's quiet hold (`POST /cool/quiet`: the air assist, exhaust, intake and purge fans, the coolant pump and the TEC off, so the modes can be heard as well as measured; the pattern is dry, the laser latched), waits the fixed 10 s, then samples the head accelerometer straight over the bus at 800 Hz through the pattern: from home to (18, 9) in, to (9, 9) in, a 9 in circle from its mid-bottom back to (9, 9), to (9, 0), home, every leg at F12000. Reports the cruise-window RMS and peak-to-peak of X and Y per leg and overall, the leg times, the kernel counters against home, and `cnc/underruns`; a JSON record with the raw trace goes to the bench data directory. Ends at 8. |
| `arc_tolerance_sweep.py` | How fine an arc the controller can plan: a `$12` ladder on the 9 in circle at F12000 (on the board, the machine homed and at home, the lid closed, no other Grbl client, the machine silent through the quiet hold). Per rung it reports the chords and the chord boundaries a second, the circle time against the ideal, the lowest feed mid-circle and the fewest free planner blocks (a starved planner shows as both), the controller CPU, clamped events, underruns and the accelerometer's cruise RMS. `$12` goes back to what it was on every exit path and the head returns home. `--mode` picks the XY microstep mode (default 16). |
| `raster_dry.py` | A dry raster at top speed at each XY microstep mode (on the board, the controller in GRBL mode, idle, no other Grbl client). For each mode given (default 8, 16, 32) it stores `xy_microsteps` through forgectrl, waits for the restarted controller, streams 60 passes of 150 mm at F12000 with the laser off, and reports the peak feed, the controller CPU, the kernel counters against the start, `cnc/underruns` and any clamped-event line. Needs 150 mm of free +X and 12 mm of free +Y travel from where the head stands. Ends at 8. |
| `platform_drills.py` | The kernel platform drills (on the board, forgectrl stopped so that the pulse device is free; start forgectrl again after). `platform_drills.py deadman|rmmod|decay|led|all`. `deadman` trips the kernel dead-man in the middle of a run and reads back what it touched. `rmmod` does three rmmod and modprobe cycles while another thread reads `cnc/state` and `cnc/position` in a tight loop. `decay` sets each decay mode and microstep mode on each axis and reads each back. `led` drives the button and lid LEDs through their target and pulse settings and back to rest. |
| `fdscan.sh` | On the board. While forgectrl spawns helper children (the curl of the update check, the media-ctl and v4l2-ctl of the snapshot), scans each child for a descriptor on the pulse device. Expected: none. Only the controller inherits `/dev/glowforge`. Usage: `fdscan.sh <panel-token>`. |
| `netblip.sh` | On the board, while a cloud session is live. Blackholes each established port 443 peer and breaks name resolution for N seconds, then restores both. The cloud client must see the dead socket and exit toward stopped-and-safe, and the respawn of the supervisor must connect again when the network is back. Usage: `netblip.sh [seconds]` (default 75). |

### The live-fire drills

`live_fire_drills.py <drill> [S] [F]`:

| Drill | What it does |
|---|---|
| `witness` | The emission witness: lid-IR peaks against the ambient baseline, the HV current, and the job-based disarm on M2. |
| `hold` | The disarm grace in Hold. |
| `faultpos` | An armed job refuses a stale origin after an underrun. |
| `ircut` | A lid-IR characterization cut at S and F. |
| `pthresh` | The laser power-threshold ladder: 13 constant-power rungs from 2 to 30 percent of full, on scrap. The lowest rung that marks is the strike threshold of the tube, and it reads directly as the `$35` value. The run needs `$35` = 0. |
| `dladder` | A density ladder at a selected base period. |
| `xymode` | The XY microstep mode under the laser: one out-and-back 20 mm line pair per feed (default 1200 and 6000 mm/min) at the same S under M4 density, the passes 5 mm apart in +Y, the block shifted +X by an offset so the runs at 8, 16 and 32 sit side by side. Reports the mode, tick and ramp the kernel holds, the discharge window and the HV current per pass. Set `xy_microsteps` before each run. |
| `xycircle` | The same question for the eye: a dark rapid +X by an offset, one full circle of the given diameter (default 152.4 mm) from its top at S under M4 density, laser off, and a rapid back to the origin. One armed run per mode, each at its own offset. Reports the mode, tick and ramp, the discharge window against the expected time, and the HV current. |
| `pcurve` | The laser performance-curve ladder: one 100 mm line for each level, at 10 mm/s under M3, with the laser off between rungs, and one mid-ladder rung repeated at the end. Reads `pic/hv_current` and the head thermopile `head/beam_detect_analog` from sysfs at about 25 Hz on the board. The thermopile is a scatter detector in the beam path before the final mirror, so it sees the beam, not the material. The drill brackets each rung on the Run and Idle states of the controller. For each rung it reports the current with a clipped-at-1023 flag, the thermopile delta over its laser-off baseline, and the in-line drift. Then it reports the normalized curve, the monotonicity, a line fit with its threshold intercept, and the drift of the repeated rung. JSON record with the raw trace in the bench data directory. The rungs follow `laser_power_model`; a comma-separated list overrides them. A curve measurement wants `$35` = 0. |
| `dpatch` | The depth witness for the density curve: two rows of small serpentine-filled patches. Row A is CW at feeds that give relative doses from 1.0 to 0.25. Row B is density 100, 80, 60, 45, and 30 percent at F600. The operator matches each row-B patch to the row-A patch of equal depth. This reads the light fraction of the density off the material, next to the prediction of the thermopile. JSON record. |
| `m5dark` | The rapids after an M5 ship dark: one 20 mm line at M3 S400, M5, dwell, rapid back, dwell, rapid forward. PASS when the 25 Hz current trace shows one discharge segment and reads dark after the M5, and `laser_on_sampled` never lights again. The catalog test `laser.m5-rapid-dark` is its port. |
| `expstop` | The armed kill on the expected-stop path. Needs the panel token (`GF_TOKEN`, or the token file of the board). |
| `ctrlstart` | The separate controller restart after `expstop`. |

### Data files

These data files stay next to the tools:

- `flow_matrix_results.json` and `flow_matrix_log.txt`: the 60-run
  flow-detection matrix.
- `flow_warm_results.json` and `flow_warm_log.txt`: the warm-baseline
  validation.
- `temp_calibration.json`: the coolant sensor spot checks.
- `lid_ir_ambient_baseline.csv`: the lid-IR ambient level, lid closed, idle.

The build scripts use the Yocto cross toolchain and sysroot from the work
directory of a target recipe in the build tree (`FF_BUILD_TOP`, default
`../forgefirm/build`). If that path is gone after a `bitbake -c clean`, you
have three options:

- Build the named recipe again.
- Point `TC` at the current work directory of any target recipe.
- Build an SDK with `bitbake meta-toolchain`.

## How the coolant-flow fire-gate threshold was derived

The cooling engine of forgectrl refuses to let the laser fire unless a
heater-based flow check passes. With the pump commanded on, the loop heater
runs at `COOL_FLOW_HEATER_PCT` (40 percent) for `COOL_FLOW_CHECK_S` (50 s).
The rise of the downstream sensor over its settled baseline must stay below
`COOL_FLOW_RISE_C` (14.4 °C). A stopped pump lets the output of the heater
pool at the downstream sensor instead of a carry-away. The three constants
are in `forgectrl/src/cool.h`. They are the compiled defaults behind the
`cool_flow_*` settings.

The 14.4 °C threshold and the 40 percent / 50 s operating point come from
`flow_matrix.py`. The matrix was 6 duties × 2 flow states × 5 interleaved
repeats, that is 60 heating runs. Each run started from a common cooled
baseline. `flow_sampler.py`
sampled both sensors at 1 Hz. One heating trace was scored at each candidate
check duration. The committed `flow_matrix_results.json` and
`flow_matrix_log.txt` are that data set. The selection rule was the cheapest duty at which each observed no-flow
rise was above each observed flow rise, with a comfortable d′. At 40 percent / 50 s:

- flow: 12.75 °C or less, over 17 observations;
- no flow: 16.04 °C or more, over 8 observations;
- d′ 8.4;
- about 0.8 °C of loop heating for each check.

The threshold is the balanced midpoint of the two
bands (14.4 °C). `flow_warm_validate.py` then ran the real check again from
heater-warmed baselines (`flow_warm_results.json`).

To reproduce this on another machine, boot the dev image. Then run the
**flow-matrix** tool from the bench page (`#bench`). It is a takeover, and
the full matrix takes about 1.6 h. The results land under
`/data/forgetest/bench/`. Or
run `flow_matrix.py [duties] [repeats]` from a host with `GF_HOST` (and
`GF_SSH` if ssh needs a wrapper), with forgectrl and the controller stopped.
The same derivation is also in forgectrl, as the **flow-calibrate** tool on
the Diagnostics tab of the panel. It does 3 trials for each case at the
operating point. It reports both bands and a recommended threshold. On the bench, its
recommendation lands within a few tenths of a degree of 14.4. Apply a
per-machine value through the `cool_flow_rise` setting. Do not edit the
constant.

## The bench actuator: forgefixture

The acceptance campaign asks a person for about eighty small things. Most of
them are the same three: open the lid, pull the interlock, press the button.
`forgefixture` (`fixture/` in the `forgefirm` repository) is the box that
does those on request. Thus the acceptance tool can run an operator test
with nobody in the room. An ESP32-S3 DevKitC-1 on the bench network drives
three relays that are wired into the connectors of the machine. The acceptance tool (`forgetest`, on the machine) asks it over HTTP. Then
the tool watches the machine for the result, in the same way as it watches
the hand of an operator.

Nothing here touches the safety chain of the laser. Two of the contacts are
normally closed, and they sit in series with loops that the chain already
reads. The third is normally open, across the button input, and it is only
ever pulsed. With the fixture unpowered, unplugged, in a reboot, or crashed,
the machine is a stock machine.

### Hardware

| Part | What |
|---|---|
| ESP32-S3-DevKitC-1 | Any flash size. Powered from its USB port by a USB wall adapter (see the note on grounds). |
| 3 × 1-channel 3.3 V optocoupler relay modules, high-level trigger | VCC, GND, IN; each coil about 100 mA |
| A 2-pin header and a jumper | The enable of the button channel |
| The interposer harness at the machine | Bench-local. It is described in the hardware facts bank of the project, not here. |

The pins on the DevKit are plain GPIOs, with no strapping, USB, flash, or
PSRAM role:

| Signal | GPIO | Relay contact | Where in the machine |
|---|---|---|---|
| lid | 4 | NC, in series with the lid-switch loop | energized = the loop opens = lid open |
| interlock | 5 | NC, in series with the interlock loop | energized = the loop opens = interlock pulled |
| button | 6 | NO, across the button input | energized = pressed; pulsed only, 20 to 500 ms |
| button enable | 7 | input, internal pull-up | a jumper to GND enables the button channel; no jumper, no presses |

Connect the parts as follows:

- The relay coils (the VCC and GND of the modules) to the 3.3 V of the
  machine.
- The three IN pins to the GPIOs above.
- The GND of the DevKit to the GND of the modules.

The opto inputs of the modules share GND with their
coils. Thus the ESP32 and the machine share a ground. Power the DevKit from
a wall adapter, not from a PC, unless you want the ground of that PC on the
machine.

### Build and flash

The only input is `fixture.env`: the wifi network, the API key, and the
hostname. Everything else is pinned (ESP-IDF v5.5, the mDNS component in
`dependencies.lock`).

```
./fixture.sh env              # fixture.env from the example, with a fresh key; fill in the wifi
./fixture.sh build            # idf.py if installed, else the espressif/idf container (docker or podman)
./fixture.sh flash COM5       # or /dev/ttyUSB0; esptool from pip talks to the board directly
./fixture.sh monitor COM5     # the log
./fixture.sh test             # the host test of policy.c
```

Either USB port of the DevKit flashes. The port marked UART also shows the
log. `fixture.env` is git-ignored and never leaves the bench. A build in the
container works where docker or podman runs (Git Bash on Windows included).
`pip install esptool pyserial` is the full host-side requirement for the
flash and the monitor.

### What it does on the network

The fixture joins the wifi as `forgefixture` (the `HOSTNAME` in
`fixture.env`). It sends that name in its DHCP request. It announces
`forgefixture.local` over mDNS, with a `_forgefixture._tcp` service. It
connects again forever, and it never puts the radio to sleep. The API is
HTTP on port 80, JSON, LAN only, with no OTA (the flash occurs over USB and
nowhere else).

Each request carries the key in `X-Fixture-Key`. Without it, or with a wrong
one, each path answers 401, and the attempt is logged with the address of
the caller.

| Request | Does |
|---|---|
| `GET /` or `/state` | The identity, the firmware version, the uptime, the states of the three channels, whether the button is enabled, the wifi link |
| `POST /lid {"state":"open"}` | Energizes the lid channel (the loop opens); `"close"` releases it |
| `POST /interlock {"state":"open"}` | The same for the interlock loop |
| `POST /button {"ms":200}` | One press. `ms` is clamped into 20 to 500 (200 when absent). 409 while the enable jumper is out, or while a press is in progress |
| `POST /release` | Releases each channel |

An action answers with the state as `GET /` shows it. The fixture does not
read the switches of the machine. The tool verifies each action through the
readings of the machine, which is the point.

```
curl -s -H "X-Fixture-Key: $KEY" http://forgefixture.local/
curl -s -H "X-Fixture-Key: $KEY" -d '{"state":"open"}' http://forgefixture.local/lid
```

### The side of the tool

`forgetest` looks for `/data/forgetest/fixture.json` on the machine:

```
{"hostname": "forgefixture", "key": "<the API_KEY>", "ip": null,
 "channels": ["lid", "interlock", "button"], "arm_press": false}
```

`ip` overrides the mDNS lookup. The tool resolves `<hostname>.local` itself,
because the image has no mDNS resolver. `channels` names what is wired.
`arm_press` stays false unless the fixture is permitted to press the button
to arm the laser for a live test. By default, that press belongs to a person.
The file has mode 0600 and is bench-local. The tool probes the fixture before
each run, and at most every 30 s otherwise. What holds:

- **The machine still proves each action.** The fixture does not read the
  switches. `ctx.act` asks the fixture, then waits for the reading of
  forgectrl, in the same way as it waits for the hand of an operator. If the
  box fails to do an action, the test falls back to the notice for the
  operator, and the record says so (`evidence.actions[].by`,
  `fixture_error`). In an unattended run there is nobody to fall back to,
  and the test ends ERROR with the refusal named. The tool spaces two button
  presses: the next one waits for the end of the last pulse, plus a 300 ms
  release. Thus the controller sees the release between them, and not one
  long press.
- **An operator test that the fixture can run alone runs unattended.** A
  test declares its actions and, with `hands=(...)`, what else it asks of a
  person ("app" for a job in the Glowforge app). An `operator` test whose
  actions the fixture covers, and whose `hands` are empty, goes into the
  unattended queue and out of the attended one. Its Ready gates pass, because the fixture does the timed step. A prompt
  that the test raises anyway is a FAIL that names the undeclared step. It
  is never a wait for nobody. A `live` test
  never moves: the fire watch and the acknowledgment belong to a person.
- **The button channel needs the jumper.** With the enable jumper of the
  fixture out, the button is not covered, and the tests that press it stay
  attended. The arm press of a live test belongs to a person unless the
  bench configuration says `arm_press: true`. Then, and only with the jumper
  in, the fixture presses when the button lights, and the record says so.
- **What the box still holds after a run is released** and recorded
  (`evidence.fixture.released`), before the post pass of the baseline. Thus
  a lid that a failed test left open never reaches the next test.

### What keeps it safe

- Each line is driven low first thing at boot, before the radio or the
  server exist, and after each reset.
- The button is a pulse whose end is armed before the line rises. A hung
  task trips the task watchdog, which panics and reboots to all-low.
- The button channel needs the jumper. A leaked LAN key cannot press the
  button on a fixture whose jumper is out.
- The contacts in the loops are NC. A fixture fault can only add an open. It
  can never mask a real lid open or a pulled interlock.
- No OTA, no configuration over the network, and nothing persisted other
  than the own calibration of the wifi driver.

### Layout

```
main/         the firmware: main.c, wifi.c, api.c, relays.c, policy.c (the pure decisions)
test/         the host test of policy.c (./fixture.sh test)
fixture.env.example, sdkconfig.defaults, dependencies.lock
```
