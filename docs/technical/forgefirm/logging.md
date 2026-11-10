---
title: Logging
---

# Logging

ForgeFIRM has one log transport and one log writer. This page is the
internals: the emitters, the per-logger tree, the levels and why they apply
at reboot, remote syslog, rotation, and the export sanitizer. The operator's
view (the Logs tab, the viewer, the export for issue reports) is on
[Logging](../../usage/logging.md).

## One transport, one writer

Every ForgeFIRM process emits through the system syslog socket (`/dev/log`)
and **rsyslog is the only file writer**: nobody opens its own log file, and
nothing of ForgeFIRM's is written anywhere under the factory's
`/data/log/*` directories or as `/data/*.log`. rsyslog replaces the busybox
syslogd and klogd on the image and is trimmed to the local socket and kernel
inputs, file output, plain UDP and TCP forwarding, and rainerscript filters
([Image and BSP](image-and-bsp.md)).

## Emitters

forgectrl and the grblHAL driver use the shared `fflog` emitter
(`src/fflog.[ch]` in forgectrl, vendored verbatim into grblHAL-glowforge;
the copies are kept identical). It differs from glibc `syslog(3)` in one
deliberate way: the socket is non-blocking, and a message that cannot be
queued is dropped and counted, never waited for. A unix datagram socket
exerts backpressure on its sender, so a stalled log daemon could otherwise
park a controller thread. The RT feeder thread never logs except a fault.
A process can also emit under a second program name (`fflog_channel`),
with a level of its own: forgectrl's sensors logger does, so its records
land in a logger of their own.

The Python apps (gfcloud, gfhome) use `logging.handlers.SysLogHandler` on a
non-blocking socket with the same drop semantics. Python has no `notice`;
its loggers emit INFO for both `info` and `notice`.

Stray stdout and stderr of a controller (an interpreter traceback, a library
message) reach syslog through a `logger` relay the supervisor spawns per
controller under the controller's program name (double-forked, so it
outlives the daemon while the controller does). The daemon's own stray
output flows through a fifo relay in its init script.

## Loggers and the tree

`LOGS_ROOT = /data/log/forgefirm/<logger>/<logger>.log`, plus rotated
`.N.gz`:

| Logger | Selector | Emitter |
|---|---|---|
| `forgectrl` | `programname == forgectrl` | fflog (plus the fifo relay) |
| `sensors` | `programname == sensors` | forgectrl's sensors logger, an fflog channel ([The sensors logger](#the-sensors-logger)) |
| `grblhal` | `programname == grblhal` | fflog (plus relay) |
| `gfcloud` | `programname == gfcloud` | SysLogHandler (plus relay) |
| `gfhome` | `programname == gfhome` | SysLogHandler; stray output rides the grblhal relay (it is the controller's child) |
| `forgeext` | `programname == forgeext` | fflog (plus the fifo relay); a service's output arrives through the host's log pipe as `ext <id>: <line>` |
| `kernel` | facility `kern` (imklog) | printk; levels only filter |
| `system` | everything else | sshd, ntpd, wpa_supplicant, init scripts via `logger` |

Line format (`ff_line`):

```
2026-08-15T16:35:44.123456-04:00 forgectrl[512] INFO super: started grbl controller (pid 3084)
```

One directory of the tree has no logger: `install/install.log` is written
by the installer itself, on factory firmware, before ForgeFIRM's first boot
([The slot installer](install-and-update.md#the-slot-installer)). It uses
the same line format with the program name `install`, in UTC, and it is
appended across runs, so a run that failed is still there after the run
that worked. It has no level setting and no viewer in the panel; the export
carries it.

## Levels

Per logger, two independent settings in `/data/forgefirm/forgefirm.conf`:
`log_<logger>_disk` (default `info`) and `log_<logger>_remote` (default
`off`), each one of `off`, `error`, `warning`, `notice`, `info`, `debug`.
Rule: **a process emits at the more verbose of its two levels**, and rsyslog
filters per destination (`fflog_init` reads both keys itself; the kernel is
filter-only). The `FFLOG_LEVEL` environment variable overrides the emit
level of one process for harnesses.

## Remote syslog

Three more settings name the remote target: `syslog_server`, `syslog_port`
(514), and `syslog_proto` (`udp` or `tcp`). Forwarding is RFC 5424, with a
per-action queue that discards when full, so an unreachable server never
stalls the disk writers. Nothing is forwarded until a server is set.

## Applied at reboot, by design

`forgectrl --render-syslog` renders the rules into
`/data/forgefirm/rsyslog-forgefirm.conf` (included by `/etc/rsyslog.conf`),
creates the log directories, and records the levels in force in
`/var/run/forgefirm-loglevels`. The `forgefirm-logging` init script runs it
before rsyslog starts, and each process reads its own level at start. There
is no live re-level path; the panel shows configured against effective
levels and offers the reboot.

Rotation is logrotate, size-capped per file, with a `HUP` to rsyslog (never
`copytruncate`), driven by the same init script at boot and hourly. A full
`/data` breaks settings, updates, and controller writes, which is what the
cap protects. Every logger keeps its file at 2 MB and three compressed ones,
except the sensors logger, which keeps months: a 4 MB file and 25
compressed ones, under 15 MB on `/data`, all of which the export carries.
Each logger's directory is named in the rotation rules (a file two rules
select is an error to logrotate), so a new logger gets a line there.

## Panel and API

| Endpoint | Purpose |
|---|---|
| `GET /logs` | Loggers with configured and effective levels and on-disk sizes, the remote target, `pending_reboot` |
| `GET /logs/tail?name=&lines=&from=` | The last `lines` of a logger's live file, or everything since byte offset `from` (incremental follow) |
| `POST /logs/export?sanitize=1` or `=0` | Streams a `tar.gz` of every logger's files, the installer's log when the machine has one (`logs/install/`), and a system snapshot (version, dmesg, uptime, memory, disk, processes, effective levels, settings with secrets masked, and the setup record as `system/setup.json`, indented so the sanitizer sees one value per line) |

All three require a login session or the panel token
([forgectrl](forgectrl.md#http-api)).

The export is sanitized by default for public issue reports. The sanitizer
(`src/sanitize.c`) is two-layer: exact known values first (serial, hostname,
cloud credentials, panel token, camera key, WiFi SSID, PSK, and identity, the
account name), then pattern
classes (bearer and basic credentials, JWTs, key=value secrets, e-mail
addresses, MAC addresses, IPv4 and IPv6 addresses with loopback kept, hex of
32 or more characters, base64-like strings of 40 or more). Placeholders are
stable per value within a bundle, and the output is idempotent. forgectrl
does not log the account name; as a known value it comes out of any log
line that carries it, and an account name that is a common word takes that
word out of the bundle with it, the over-redaction the sanitizer accepts. The
setup record's `account.name` is also replaced by its key in
`system/setup.json`, which covers a name too short for the known-value pass
(it takes no value under 3 characters).
`tests/sanitize_test.c` runs in CI and is the regression gate for both leaks
and over-redaction. Beside it, `tests/host_guard.sh` drives the three routes
against a daemon on a host, and a file planted in the installer's directory
comes back in the export without its MAC or IP address. `tests/fflog_e2e.sh` proves the whole path on a host
against a private rsyslogd (emitter, relay, format, per-logger filtering)
([Test](../../developers/testing.md)).

## The sensors logger

forgectrl's sensors logger (`src/senslog.c`, its records in
`src/senslogfmt.c`) writes the machine's sensors and what was commanded to
the `sensors` logger, so a bundle shows how one machine differs from
another, before a fault and not only at it. Its own thread samples every
sensor once a second, apart from the cooling engine, so nothing it does can
delay a verdict. It writes seven record types:

| Record | When | What |
|---|---|---|
| `beat` | every 10 s while a run session is open, cooling down, armed, running, or in diagnostics; every 60 s at idle; and at every change of the engine's phase | every sensor, every commanded output, the engine's verdict |
| `job` | once a job is over: from the run session's opening to the machine's return to idle, the cooldown included | the job's summary |
| `inv`, `cfg` | at start, after the clock is set, when either changes, and daily | the machine's inventory; the settings in force |
| `clock` | when the wall clock steps | the step |
| `fr`, `frc` | 30 s after an event | the flight recorder: the 1 Hz samples from 120 s before the event to 30 s after it, one `frc` line a channel |

**The line.** A record is one line: its type, then `key=value` pairs
separated by single spaces. Every record carries `v` (the schema version),
`boot` (the first 8 hex digits of the kernel's boot id) and `mono` (seconds
since boot), so a line written before the clock was set can still be ordered
and dated. A value that could not be read is `-`. Hex values are written
`0x..`. A `msg` key, where there is one, is the last and runs to the end of
the line. Keys are only ever added; renaming or removing one raises `v`.
Wherever a conversion is unverified, the raw count is written beside the
converted value, so a corrected conversion can be applied to old records.

**`beat`.** `ph`, `vd`, `hold`, `fire`, `arm` (the engine's phase, verdict,
hold, fire permission and armed window); `kst`, `flt`, `sw` (the kernel's
state, its fault mask, the switch bits; `sw=-` when the switch device could
not be read, never a word of zeros); `down`, `up` (the coolant in °C, as
the engine converts it) with `down_raw`, `up_raw`; `chassis`, `soc` (°C);
`psu_raw`, `tec_raw` (`pic/pwr_temp`, `pic/tec_temp`); `thr` (the CPU's
cooling state); per fan the commanded duty, the tach reading and the speed
(`exhaust_pwm`, `exhaust_ns`, `exhaust_rpm`; `intake_pwm`, `intake1_ns`,
`intake1_rpm`, `intake2_ns`, `intake2_rpm`; `aa_pwm`, `aa_us`, `aa_rpm`);
`purge`, `purge_cur`, `pump`, `heater_pwm`, `tec_on`; `hv`, `hv_v`
(`pic/hv_current`, `pic/hv_voltage`); `lon`, `pgood` (the kernel's sampled
LASER_ON and power-good counts); `beam`, `beam_dig`, `beam_base`, `beam_n`,
`head_flags` (the head's beam reading, its comparator, the head's own
baseline, its samples in the last window, its flag byte); `ir` (the four lid
IR channels); `hall`; `cpu`, `mem` (percent, over the interval since the
last beat); `tick_ms` (the slowest cooling-engine tick since the last beat);
`data_free_mb`; `drops` (log messages the daemon dropped).

**`job`.** `seq`, `start` (mono), `end` (`idle`, `new-session`, or the phase
that took it), `run_s`, `cool_s`, `armed_s`, `lit_s` (seconds with LASER_ON
sampled), `hv_dose` (the sum of `hv` over the lit seconds), `hv_lit_mean`,
`hv_sat_s` (lit seconds with `hv` at its converter's top, 1023); the coolant
at the session's opening (`down_start`, `up_start`), at its end (`down_end`,
`up_end`) and at the return to idle (`down_last`, `up_last`); `down`, `up`,
`chassis`, `soc`, `psu_raw` as `min/mean/max` over the whole job; `thr_s`;
the fans' speeds and the purge current as `min/mean/max` over the run phase
past the first 15 s (the spin-up); `ir_base`, `ir_peak`; `beam_dark`
(`min/mean/max` while dark), `beam_peak` (lit), `beam_rise`; `verdicts`
(every verdict other than OK the job saw).

**`inv` and `cfg`.** `why` (`start`, `clock`, `change`, `daily`). The
inventory: `image`, `kernel`, `module`, `soc`, `soc_rev`, `soc_trips` (the
SoC thermal zone's trip points), `mem_kb`, `data_kb`, `pic_id`, `head_id`,
`head_fw`, `beam_coeffs` (the head's beam-detector coefficients as it holds
them), `model`, `tec`, `camera` (the setup record's). The settings record:
every `cool_*` tunable of the engine as it resolved it at the last run start
(the flow watch's `cool_flow_*` keys are not among them), then a fixed list
of machine settings as stored (`-`: unset, the default stands). It is a list,
never the settings file, which holds credentials.

**`clock`.** `from`, `to` (UTC). The step dates the boot: every record of
the same `boot` was written at `to` plus its own `mono` less the clock
record's. The plain log lines of that boot written before the step carry
whatever the clock read then (1970, or a date saved at an earlier
shutdown), and `from` names it.

**`fr` and `frc`.** The engine's arrival at any hold for a fault or a gate
(every verdict but OK, WARMUP and EXT) arms the recorder, and so do the
warnings that change no verdict: emission sensed with no armed window, a
controller silent while armed or running, the supply's power-good dropping in
the armed window, a stepper driver fault, a throttled SoC, a thermal cooldown
that timed out. `fr` carries `ev` (the dump's number), `at` (the event's
mono), `pre`, `post` and the event's words in `msg`; each `frc` carries `ev`,
`ch` (the channel: `ph`, `vd`, `down`, `up`, `down_raw`, `up_raw`,
`heater_pwm`, `hv`, `lon`, `beam`, `ir1` to `ir4`, the four fan speeds,
`purge_cur`, `soc`, `cpu`), `n`, `t0`, `t1` and `vals`, the samples one a
second. At most six dumps are written in any hour for the alarm tier (the
verdicts FIRE, CRASH, FLAME and CRITICAL, emission with no armed window, a
power-good drop, a silent controller, a stepper driver fault) and six for
the rest, so a warning that flaps never costs an alarm its dump; an event
past its budget is counted and named in the next dump. A dump still inside
its 30 s when the daemon stops is written before it stops, with the samples
it has.

**What it never holds.** No serial number (the head's serial line is
skipped and the SoC's unique id is never read), no network name or address,
no account. `tests/sanitize_test.c` proves the sanitizer leaves the records
as they are, and `tests/host_start.sh` that a planted head serial reaches no
record.

**Reading a bundle.** `tools/senslog_read.py` (in forgectrl, standard
library only) reads the records out of an export (`.tar.gz`), its directory,
or the files, oldest first, dates them per boot, and prints a summary or
writes one CSV table per record type and one per flight-recorder dump
(`--csv DIR`). The formats are a contract between the two:
`tests/senslog_test.c` proves the daemon writes exactly
`tests/senslog_records.txt`, and the reader's own test parses that file.

## Rules for new code

- No `fprintf(stderr)` or `printf` for logging in the C daemons. Use
  `fflog(LOG_x, ...)`, with the message free of a program prefix (rsyslog
  tags it) and of a trailing newline.
- Never log a credential, token, or password value, or the account name. The
  sanitizer is the second line, not the first.
- Never log from the RT feeder path except a fault.
- New loggers are added to `logs_names[]` (forgectrl), plus a setting pair
  and a line in the rotation rules. New secrets go in `load_known()`.
- A new sensor reading goes in the sensors logger's `beat`, never in a line
  of prose: a key appended to the record, the golden file rewritten
  (`SENSLOG_GOLDEN=write`), the reader following it.
