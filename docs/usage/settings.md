---
title: Settings
---

# Settings

This page is the reference for the machine settings: where they live, how they
are changed, and what each key means.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

## Where settings live

Machine settings live in the web panel and are stored on the machine, in
`/data/forgefirm/forgefirm.conf`, shared with the grblHAL-glowforge controller (re-read on
every `$H` and at every arm) and the homing runner (read at session start), so
changes apply without restarts. The cooling engine re-reads its keys at the
start of every run.

Settings can only be changed while the machine is idle. Writes are refused
(409) otherwise, and while a diagnostic owns the hardware, because the
controller and the homing runner both read this file mid-run. The panel's save
bar posts every change in one request, and a multi-key save lands as one
atomic replace.

An empty value clears a key back to its built-in default (blank fields in the
panel show the built-in value as a placeholder). The routes are `GET /settings`
and `POST /settings?key=value&...` ([The control panel](control-panel.md)).

## General keys

| Key | Meaning |
|---|---|
| `controller_mode` | `grbl` or `cloud`: the boot-time mode. `POST /mode` switches live and persists it ([Modes](modes.md)). `cloud` needs `cloud_enabled=1`. |
| `homing_mode` | `$H` behavior: `gfcloud`, `switches` (planned, not available), or `none` ([Homing](homing.md)). `gfcloud` needs `cloud_enabled=1`. |
| `cloud_enabled` | `0` (default) or `1`: whether cloud mode exists. The setup's cloud step sets it ([Setup](setup.md#cloud-mode)). While 0, the GF Cloud tab, the Factory cloud button, and the gfcloud homing choice do not exist, `controller_mode=cloud` and `homing_mode=gfcloud` are refused, and nothing contacts the Glowforge service. Through `POST /settings`, `1` takes `phrase=I UNDERSTAND` as the step does, and `0` takes `homing_mode` to `none` and `controller_mode` to `grbl` when they point at the cloud. |
| `panel_open_reads` | `1` (default) or `0`: whether the read-only routes answer any client on the network without a login. 0 closes them to logged-in sessions and the machine itself ([The control panel](control-panel.md#access)). |
| `gfcloud_home_x/y/z` | Machine coordinates after a completed homing (mm). |
| `gfcloud_home_timeout_s` | Web-service homing session budget (30 to 3600 s). |
| `gf_serial` | Cloud sign-in serial override (digits). |
| `gf_password` | Cloud sign-in password override (64 hex; write-only: `GET` reports `gf_password_set`). |
| `ui_units` | Panel display units: `metric` or `imperial` (values are stored and exchanged in metric). |
| `lid_lamp_idle` | Brightness of the lid lamp while the machine is idle (0 to 255, default 236). Applied immediately, at every daemon start, and at every controller start. Cloud mode drives the lamp itself while it runs. 0 is dark. |
| `cool_*` | Coolant-loop protection tunables (flow-check bands, temperature ceiling and resume, cooldown, fan floors, the flame and crash watches). [Cooling and fans](cooling-and-fans.md) has every key. |
| `wifi_country` | WiFi regulatory region, ISO 3166-1 alpha-2; unset = automatic (the AP's 802.11d country, else world). Applied via `iw reg reload`/`iw reg set` at startup and on change; power save is pinned off in the same pass. |
| `log_<logger>_disk`, `log_<logger>_remote` | Log level per logger (`forgectrl`, `grblhal`, `gfcloud`, `gfhome`, `kernel`, `system`) and destination: `off`, `error`, `warning`, `notice`, `info` (disk default), `debug`; remote defaults to `off`. Applied at the next reboot ([Logging](logging.md)). |
| `syslog_server`, `syslog_port`, `syslog_proto` | Remote syslog target (host or address; 514; `udp` or `tcp`). Nothing is forwarded until a server is set. Applied at the next reboot. |
| `pulse_warn_threshold_bytes`, `pulse_reject_threshold_bytes` | Cloud mode's download guards: bytes of compressed job body held in memory. Unset = 32 MiB warn and 128 MiB refuse; 0 lifts either; 0 to 1073741824 ([Cloud mode](cloud-mode.md)). |

## Settings that affect motion

| Setting | Default | Effect |
|---|---|---|
| `controller_mode` | `grbl` | Which controller runs: `grbl` or `cloud` (`cloud` needs `cloud_enabled=1`). |
| `homing_mode` | unset (behaves as `none`) | What `$H` does: `gfcloud`, `switches`, `none`. Set `gfcloud` for camera homing (needs `cloud_enabled=1`). |
| `gfcloud_home_x/y/z` | 0 / 0 / Z max | Coordinates assigned after a successful camera home. |
| `gfcloud_home_timeout_s` | 300 | How long a homing session may take before it alarms. |
| `lid_policy` | `cancel` | `cancel` = factory behavior; `hold` = stock Grbl door parking. |
| `xy_microsteps` | `8` | The X and Y microstep mode: `8` (the factory's), `16` or `32`. The GRBL controller reads it at its start and derives `$100`/`$101`, its machine tick (28160 Hz at 8, doubled at 16, quadrupled at 32) and the kernel stop ramp from it, so nothing else needs typing; `$100`/`$101` are derived, never typed. Saving a change restarts an idle GRBL controller. Cloud mode runs at the service's own 8. 32 asks four times the step rate of 8 and depends on the machine ([The motion hardware](../technical/machine/motion-hardware.md)). |
| `laser_button_timeout_s` | 300 | How long the machine waits at the button prompt. |
| `laser_disarm_s` | 60 | Spindle-off grace before the armed window closes. |
| `laser_floor_density` | 10 | The S-range floor, percent of full: the lowest pulse density that still marks. Loaded into `$35` at every spindle precompute; `$35` is derived, never typed. |
| `laser_dose_curve` | (built-in measured default) | The measured dose curve as density:light percent pairs; S commands a light fraction and the driver maps it onto the density that delivers it. `off` = identity; a bad value falls back to the default. The panel's recorder measures and applies a machine's own. |
| `laser_corner_gamma` | 2 | The corner rolloff under M4: delivered light follows (v/v_programmed)^gamma, so 1 is plain proportionality and higher values starve the slow spots where heat accumulates. Rides the curve. Range 0.25 to 4. |
| `laser_pulse_ticks` | 20 | Density base period in ticks of the 28160 Hz reference tick (35.5 us each); the driver scales it to the tick in force, so the period is a time at every microstep mode. |
| `laser_pulse_min_ticks` | 3 | Shortest density pulse in the same ticks; below it a period is skipped and its debt carried. |
| `rail_settle_s` | 2.5 | Motor-rail off period when a controller takes the device standalone. 0 disables. |
| `cloud_pause_backtrack_ticks` | 2000 | Cloud pause: laser-off backtrack after the stop (0 to 30000). |
| `cloud_resume_lead_ticks` | 1950 | Cloud resume: laser-off lead before firing again (0 to 30000). |
| `cloud_hold_max_s` | 1800 | Cloud: how long a print may be held on the cooling verdict before it is canceled (60 to 7200). |

The laser keys apply at the next job. Grbl `$` settings (rates,
accelerations, laser mode) are set through your sender in the usual way; the
defaults are baked in from the factory machine's own measured values, and
the X and Y steps per millimeter (`$100`, `$101`) follow `xy_microsteps`
rather than a typed value; `$102` (the lens screw), `$32` (laser mode) and
the `$110`/`$111` ceiling the machine tick carries are held the same way, so
a typed value is overwritten on the spot
([The grblHAL driver](../technical/forgefirm/grblhal-driver.md#the-xy-scale)). If you
change a baked default and it does not appear to take, remember that stored
settings win: `$RST=$` restores the defaults. A spindle `$` setting takes
effect when the controller restarts ([GRBL mode](grbl-mode.md)).
