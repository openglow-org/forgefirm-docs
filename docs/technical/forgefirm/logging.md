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
| `grblhal` | `programname == grblhal` | fflog (plus relay) |
| `gfcloud` | `programname == gfcloud` | SysLogHandler (plus relay) |
| `gfhome` | `programname == gfhome` | SysLogHandler; stray output rides the grblhal relay (it is the controller's child) |
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
cap protects.

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
cloud credentials, panel token, camera key, WiFi SSID, PSK, and identity),
then pattern
classes (bearer and basic credentials, JWTs, key=value secrets, e-mail
addresses, MAC addresses, IPv4 and IPv6 addresses with loopback kept, hex of
32 or more characters, base64-like strings of 40 or more). Placeholders are
stable per value within a bundle, and the output is idempotent.
`tests/sanitize_test.c` runs in CI and is the regression gate for both leaks
and over-redaction. `tests/fflog_e2e.sh` proves the whole path on a host
against a private rsyslogd (emitter, relay, format, per-logger filtering)
([Test](../../developers/testing.md)).

## Rules for new code

- No `fprintf(stderr)` or `printf` for logging in the C daemons. Use
  `fflog(LOG_x, ...)`, with the message free of a program prefix (rsyslog
  tags it) and of a trailing newline.
- Never log a credential, token, or password value. The sanitizer is the
  second line, not the first.
- Never log from the RT feeder path except a fault.
- New loggers are added to `logs_names[]` (forgectrl) plus a setting pair.
  New secrets go in `load_known()`.
