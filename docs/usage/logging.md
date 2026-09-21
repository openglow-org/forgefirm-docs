---
title: Logging
---

# Logging

Every ForgeFIRM program logs through the system logger, and the panel's Logs
tab is where you set the levels, read the logs, and export them for an issue
report. This page tells you how to use it.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

The emitters, the relay for stray output, the rsyslog rules, and the line
format are in [Logging internals](../technical/forgefirm/logging.md).

## The loggers

Every ForgeFIRM process emits through the system syslog socket, and rsyslog is
the only file writer. It files each program under its own directory,
`/data/log/forgefirm/<logger>/`, size-capped and rotated.

| Logger | What it holds |
|---|---|
| `forgectrl` | The machine-services daemon: supervision, cooling, cameras, settings, updates. |
| `grblhal` | The GRBL controller. |
| `gfcloud` | The cloud-mode client. |
| `gfhome` | The camera-referenced homing runner. |
| `forgeext` | The extension host, and the output of every package's service under the package's id. |
| `kernel` | The glowforge driver and the rest of the kernel. Its levels only filter what the kernel emits. |
| `system` | Everything else: SSH, WiFi, time sync, the init scripts. |

A controller's stray output (an interpreter traceback, a library message)
reaches the log under the controller's own name.

## Log levels

Each logger has two independent levels, one for the disk file and one for the
remote target: `off`, `error`, `warning`, `notice`, `info` (the disk default),
or `debug` (remote defaults to `off`). Levels are cumulative: `warning` keeps
warnings and errors, `debug` keeps everything, `off` writes nothing. A process
emits at the more verbose of its two levels, and rsyslog filters per
destination.

**Levels apply at the next reboot.** The boot sequence writes the rsyslog
rules from the settings before rsyslog starts, so a change waits for a reboot.
The Logs tab shows the configured level beside the effective one and offers
the reboot. The keys are `log_<logger>_disk` and `log_<logger>_remote`
([Settings](settings.md)).

## Remote syslog

The Logs tab's remote target forwards each logger at its remote level as
RFC 5424 syslog: `syslog_server` (a host name or address), `syslog_port` (514),
and `syslog_proto` (`udp` or `tcp`). Nothing is forwarded until a server is set
and at least one logger's remote level is on. An unreachable server never holds
up the machine: undeliverable messages are dropped. Applied at the next reboot.

## The log viewer

The Logs tab's viewer shows the tail of one logger. **Follow** keeps it moving;
**Refresh** fetches once. The viewer keeps the last few hundred kilobytes.

## Export

**Export** streams a `tar.gz` of every logger's files plus a system snapshot:
firmware version, kernel ring buffer, uptime, memory, disk, processes, effective
log levels, and the settings with secrets masked. It also carries the log the
installer kept of each of its runs, when the machine has one
([Logging](../technical/forgefirm/logging.md#loggers-and-the-tree)).

The bundle is **sanitized by default**, for attaching to a public issue report.
Known identifiers (serial, hostname, cloud credentials, panel token, camera
key, WiFi network) and pattern classes (network addresses, e-mail addresses, bearer and
basic credentials, JWTs, key=value secrets, long hex and base64 blobs) become
placeholders. A placeholder keeps the same number for the same value within the
bundle, so hosts can still be told apart. The sanitizer removes what it knows
and what it can recognize: skim the bundle before posting it. Untick the option
to keep everything for your own use.

## The routes

| Endpoint | Purpose |
|---|---|
| `GET /logs` | Loggers with configured and effective levels and on-disk sizes, the remote target, `pending_reboot` |
| `GET /logs/tail?name=&lines=&from=` | The last `lines` of a logger's live file, or everything since byte offset `from` (incremental follow) |
| `POST /logs/export?sanitize=1\|0` | Streams the `tar.gz` bundle, sanitized by default; it carries the setup record as `system/setup.json` ([Setup](setup.md#the-record)) |

All three require a login ([The control panel](control-panel.md#access)).
