---
title: Extension packages
---

# Extension packages

An extension package is software that is not part of the firmware image and
is installed on the machine by its owner. `forgeext`, the extension host,
verifies a package, unpacks it, and keeps the record of what is installed.
It is a separate program from [forgectrl](forgectrl.md) on purpose:
manifest parsing, archive handling, and everything else that reads what an
outsider wrote stay out of the process that holds the cooling engine and the
supervisor.

Two other kinds of extension need no package at all: the
[built-in extensions](forgectrl.md#built-in-extensions) are part of the
image, and a program on another computer uses the
[remote API](remote-api.md) with a scoped token.

What a package's service runs inside (the account pool, the cgroup tree,
the network rules) is part of the image:
[the extension sandbox](image-and-bsp.md#the-extension-sandbox).

## The archive

A package is one file, `<name>.ffx`: an [fwup](https://github.com/fwup-home/fwup)
archive, the container the firmware itself ships in. It is a ZIP whose
entries are, in this order, `meta.conf.ed25519` (the Ed25519 signature,
absent when the archive is unsigned), `meta.conf` (the metadata), and
`data/payload.tar.gz`, the one resource. The payload is a gzip-compressed tar
of the package's files with `manifest.json` at its top.

`tools/mkffx.sh` in the `forgeext` repository packs a directory:

```sh
tools/mkffx.sh <package-dir> <out.ffx> [<private-key>]
```

The key pair comes from `fwup -g`. The script builds the payload the same
way every time (sorted names, owner 0, time 0), signs when it is given a key,
and checks the signature against the key's public half before it reports
success.

## What the verifier takes

Firmware and packages share a container and a verifier, so the first thing
the extension host is, is a product gate:

- `meta-product` is `ForgeFIRM extension`, exactly.
- The archive lists **no task**. A task is what fwup would write to a disk.
- The metadata holds `meta-*` lines and one `file-resource` block for
  `payload.tar.gz`, and nothing else. Every line is accounted for or the
  archive is refused.
- An archive whose only valid signature is a key that signs **firmware**
  (the release key, the factory keyring) is refused outright.
- The archive holds its metadata and that one resource, in that order, and
  no other entry.

[forgectrl's firmware paths](install-and-update.md#invariants-every-flash-path)
hold the other door: they take firmware only.

**The bytes that are parsed are the bytes that were verified.** The host
reads the archive the way fwup does (streaming, the local headers, in
order), checks the signature itself over the `meta.conf` it took, and hashes
the payload against the BLAKE2b-256 that same `meta.conf` names. fwup is
asked as well (`-m`, `-l`, `-V`), because it is the program a firmware
archive would be handed to, and its reading of the product, the version, and
the task list must agree.

**The payload is unpacked where nothing in it can reach outside.** Regular
files and directories only: a symbolic link, a hard link, a device, or a
fifo refuses the package. Every path is relative, with no `..`, printable
ASCII, at most 192 characters and 16 directories deep. Modes are reduced to
0644 and 0755; whatever the archive said about setuid bits or owners is
dropped. The limits:

| Limit | Value |
|---|---|
| The archive | 32 MiB |
| The payload unpacked | 64 MiB, one file 32 MiB, 4096 files |
| Every installed package together | 256 MiB |
| Free space an install must leave | 576 MiB, what a firmware update may need |
| Installed packages | 64, of which 32 may run a service (the account pool) |

A refusal leaves nothing behind: staging lives under the root's `tmp/` and
is removed on every path out.

## Trust tiers

| Tier | Signed by | What an install takes |
|---|---|---|
| **Official** | The OpenGlow extension key in the image (`/etc/forgefirm/keys/ext/forgefirm-ext.pub`), a different key from the one that signs firmware | Nothing beyond the grants below |
| **Community** | A key the owner added under `/data/forgefirm/ext/keys/` | The operator's typed consent |
| **Unverified** | Nobody this machine trusts: unsigned, or signed by a key it does not hold | The machine button held, as for unsigned firmware |

- The ids under `org.openglow.` and `org.forgefirm.` belong to the official
  tier: an archive that claims one and is not signed with the OpenGlow
  extension key is refused.
- **An update is signed by the key that signed the installed version.** A
  package cannot change its signer, or lose its signature, by updating;
  the owner removes it first.
- Nothing updates itself. An update is the operator's act, and what it asks
  for that the installed version did not is shown as new.

## The manifest

`manifest.json` is the one thing a package says about itself. The parser is
strict on purpose: an unknown key, a duplicate key, a field of the wrong
type, or a capability listed twice is a refusal in words, never a default,
so that a typo cannot silently drop a capability the operator was meant to
see.

```json
{
  "manifest": 1,
  "id": "org.example.notify",
  "name": "Notify",
  "version": "1.2.0",
  "description": "Tells you when a job ends",
  "author": "Someone",
  "license": "MIT",
  "homepage": "https://example.org/notify",
  "api": "0.1",
  "core": { "min": "0.0.7" },
  "runtime": "python",
  "service": { "exec": "bin/run.py", "args": ["--quiet"] },
  "modes": ["grbl", "cloud"],
  "capabilities": ["events", "machine.read", "net.outbound:mqtt.example.org:8883", "storage:8"],
  "conflicts": ["org.example.other-notifier"]
}
```

| Key | Rule |
|---|---|
| `manifest` | The schema number, 1 |
| `id` | Reverse-DNS, lowercase: two or more labels of `a-z`, `0-9`, and `-`, each starting with a letter; 63 characters in all. It names the package's directories |
| `name`, `author`, `license` | Required text. `description` and `homepage` are optional |
| `version` | `MAJOR.MINOR.PATCH` with an optional `-prerelease`. The archive's own `meta-version` must say the same |
| `api` | The extension API the package was built for, `MAJOR.MINOR`. This firmware serves **0.1**. A 0.x API carries no stability promise, so the minor must match exactly |
| `core` | Optional `min` and `max` firmware versions |
| `runtime` | `data` (nothing executes), `ui` (runs in the operator's browser), `shell`, `native` (a static ARMv7 hard-float binary), or `python` (inside the release image's module list) |
| `service` | `exec`, a path inside the package, and optional `args`. Required for `shell`, `native`, and `python`; refused for `data` and `ui`. The entry point must be a file of the package, and executable for `native` |
| `modes` | `grbl`, `cloud`, or both (the default) |
| `capabilities` | Required, and may be empty. See below |
| `conflicts` | Ids this package cannot be installed beside. The refusal works in both directions |

## Capabilities

The list is closed and compile-time. A manifest that asks for anything else
is refused, and nothing a manifest can spell reaches a privileged role or a
provider kind: `role:homing` and `role:controller` are refused by name,
because both are part of the firmware, and no other role exists.

| Capability | Grants | The operator's own grant |
|---|---|---|
| `machine.read` | The machine's status, cooling status, mode, and position | |
| `events` | The event stream | |
| `settings.own` | The package's own settings | |
| `camera.lid`, `camera.head` | Pictures from that camera, under the privacy gate | |
| `motion.jog` | Dark jogs inside the jog bounds | |
| `motion.job` | Running a program as the machine's one sender, under every arm gate | required |
| `hold` | Holding a job until the package clears the hold (pause tier only) | required |
| `job_time.run` | Not being frozen while a job is armed | required |
| `ui` | Its own tab or cards in the control panel | |
| `net.outbound:<host>:<port>` | One named destination: a lowercase DNS name, an IPv4 address, or an IPv6 address in brackets. Never the machine itself | |
| `net.listen:<port>` | One listening port, 1024 to 65535, never one of the firmware's, and one package per port | |
| `storage:<MiB>` | A data directory, 1 to 256 MiB | |

`motion.offsets`, `wizard`, and `mcode:<n>` are known names that this API
version does not serve; a manifest that asks for one is refused in those
words.

Three rules tie capabilities to the runtime. A `data` package holds none.
`hold`, `job_time.run`, `net.outbound`, `net.listen`, and `storage` belong
to a service, so a `ui` package cannot hold them. And the capabilities
marked *required* above are never implied by a tier: the operator grants
each one, per package, at install, and an install that lacks a grant, or
carries a grant for something the package did not ask for, is refused.

## What is installed

The extension root is `/data/forgefirm/ext`:

| Path | Holds |
|---|---|
| `pkg/<id>/<version>/` | The package's files, root-owned, never written again |
| `pkg/<id>/<version>.files` | What was unpacked: BLAKE2b-256, mode, size, and path of every file |
| `pkg/<id>/current` | A symbolic link to the version in use |
| `data/<id>/` | A service's own data, mode 0700, owned by its account |
| `keys/` | Public keys the owner added |
| `tmp/` | Staging, the host's alone |
| `state.json` | What no package can say about itself: the tier and the key that signed it, its account of the pool (`ffx0` to `ffx31`, the lowest free one), the operator's grants, enabled, quarantined |

An update keeps the version it replaces; the one before that is removed. `state.json` is written whole and renamed into
place, and a state file this program did not write (another schema, an
account outside the pool or held twice, a grant for a capability that needs
none) is refused whole rather than guessed at.

**The integrity check** compares an installed tree with its `.files` list:
every listed file present with its hash and mode, and nothing else there. A
changed file, a changed mode, an added file, or an added link fails it.

## The extension host

`forgeext run` is the extension host: the daemon that runs the services of
the installed packages. The image starts it after forgectrl
(`/etc/init.d/forgeext`) and it runs whether extensions are on or off, so
turning them on or off never starts or stops a system service.

**The master switch** is the setting `ext_enabled` (0 or 1, default 0),
which the host reads from the settings file on every turn of its one-second
loop. While it is 0, no service runs. forgectrl takes `ext_enabled=1` only
over the Extensions advisory
([forgectrl](forgectrl.md#the-extensions-advisory)). **Safe mode** is the
file `/run/forgefirm/ext-safe`, made as root at the console: while it
exists no service runs, whatever the setting says, and it is gone at the
next reboot.

**What the host knows about the machine** it reads and never writes: the
armed window from `GET /cool/status`, the controller mode from `GET /mode`,
a running diagnostic from `GET /status`, and a firmware flash from
`GET /update/status`, all on forgectrl's read-only loopback port. What it
cannot read it takes the careful side of: an armed window it cannot see is
open, and a machine it cannot ask is not ready for a new process. A root
that a package's account cannot walk to (a directory on the way to
`/data/forgefirm/ext` without the search bit for others) is also a machine
that is not ready: the host names the directory in `not_ready` and in its
log and starts nothing, because a service started there would end at once
and be quarantined for a fault that is not its own.

**What a service runs inside.** The host forks, and before one instruction
of the package runs, the new process:

- is in the package's own cgroup under `/sys/fs/cgroup/ffx` (25 percent of
  the core, 48 MiB, 32 processes);
- is idle-class in every scheduler (`SCHED_IDLE`, nice 19, I/O class idle)
  and first in line for the OOM killer (`oom_score_adj` 900);
- holds no descriptor but `/dev/null` and its log pipe, with limits of no
  core file, 256 descriptors, 64 processes, and 1 GiB of address space;
- has the package's pool account (`ffx0` to `ffx31`) and no group but its
  own, and can gain nothing by exec (`no_new_privs`);
- sees of the file tree only the system's read-only parts, its package
  (read and execute), and its data directory (landlock);
- connects and binds only on the TCP ports it declared (landlock), and
  sends only where its chain in the image's rule table allows, which is
  never the machine itself
  ([the extension sandbox](image-and-bsp.md#the-extension-sandbox));
- cannot make the system calls a package has no business making, and can
  open only UNIX, IPv4, and IPv6 sockets (seccomp).

A step that cannot be taken is a failed start, never a looser sandbox. The
environment is fixed: `PATH`, `LANG`, `HOME` (the data directory),
`TMPDIR`, `FFX_ID`, `FFX_PKG`, `FFX_DATA`, `PYTHONDONTWRITEBYTECODE`, and
`PYTHONUNBUFFERED`. A service's output goes
to the `forgeext` logger under the package's id, at most 60 lines in 10
seconds, with a count of what was dropped.

**The rules of the supervisor:**

| Rule | Value |
|---|---|
| A service starts only when | extensions are on, the controller is up, motion is verified, no diagnostic runs, and no firmware is being flashed; never inside an armed window |
| Starts | one at a time, 5 s apart, at most 4 services running; of the services that are due, the one that has ended least lately goes first |
| A service that ends | is started again after a backoff that doubles from 1 s to 30 s |
| Healthy | after 60 s of running: the backoff starts over, and the package's previous version is removed |
| Quarantine | at the fifth end inside 10 minutes without reaching healthy; remembered in `state.json` until the operator lifts it |
| A service that should not run | (disabled, removed, quarantined, the wrong controller mode, extensions off) is stopped: its group is killed and removed, and its chain and map element are taken out of the rule table |

**The armed window.** While the window is open, every service is frozen
with its cgroup's `cgroup.freeze`, and it is thawed when the window closes.
A package with the operator's `job_time.run` grant is not frozen: it runs
on at 3 percent of the core. The freeze follows the `armed` field of
`GET /cool/status`, read once a second. On the bench reference the services
were frozen within a second of the field turning on, 4 s before the job ran,
and thawed within a second of it turning off.

**One host, and nothing it did not start.** The host holds a lock
(`/run/forgefirm/ext/daemon.lock`) for its lifetime, and a second one is
refused. A host that ended without stopping its services would leave them
running with nobody to freeze them, so the init wrapper kills every group
of the pool the moment the host ends abnormally, and a starting host
removes every group and every allowlist chain it finds before it starts
anything.

**The status file** `/run/forgefirm/ext/status.json` is rewritten when it
changes: `pid` (the host that wrote it; the file outlives a host that was
killed, and a pid that is not a running host marks it as a dead one's),
`enabled`, `off_reason`, `armed` (null when it cannot be read),
`not_ready`, and per service `id`, `state` (`stopped`, `running`,
`waiting`, `quarantined`), `account`, `pid`, `frozen`, `job_limited`,
`healthy`, and `reason`.

The acceptance test `exthost.service` proves the host on the image with a
reference package it builds and signs on the board: the confinement seen
from inside the service, safe mode, a killed host, and the master switch.
`setup.extensions-consent` proves the consent
([Release acceptance](../../developers/acceptance.md)).

## The command line

`forgeext` answers every command with one JSON object and exits 0 when
`"ok"` is true.

| Command | Does |
|---|---|
| `inspect <file.ffx>` | Everything an install checks short of consent and grants, with nothing left behind: the tier, the manifest, what needs a grant, what is new against the installed version, whether it is a downgrade |
| `install <file.ffx> [--grant <capability>]... [--consent-community] [--consent-unverified]` | Installs, or refuses in words |
| `list` | What is installed |
| `check [<id>]` | The integrity check |
| `remove <id> [--keep-data]` | Removes the package and, unless told otherwise, its data |
| `caps` | The capability list and the API version |
| `run` | The extension host, above |
