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
| `core` | Optional `min` and `max` firmware versions. **Checked against each other and nothing else:** this firmware does not refuse a package whose `core.min` is above its own version |
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

**Served** means the extension API has a route for it today
([The extension API](#the-extension-api)). A capability that is not served
can still be asked for, granted, and shown to the operator, and it reaches
nothing: the vocabulary is settled ahead of the routes so that a package's
manifest and the operator's consent do not change shape as each one lands.

| Capability | Grants | Served | The operator's own grant |
|---|---|---|---|
| `machine.read` | The machine's status, cooling status, and mode | yes | |
| `events` | The machine's events | yes | |
| `hold` | Holding a job until the package clears the hold (pause tier only) | yes | required |
| `settings.own` | The package's own settings, declared in its manifest ([A package's own settings](#a-packages-own-settings)) | yes | |
| `camera.lid`, `camera.head` | Pictures from that camera, under the privacy gate | no | |
| `motion.jog` | Dark jogs inside the jog bounds | no | |
| `motion.job` | Running a program as the machine's one sender, under every arm gate | no | required |
| `job_time.run` | Not being frozen while a job is armed | yes, as a limit the host applies | required |
| `ui` | Its own tab or cards in the control panel | no | |
| `net.outbound:<host>:<port>` | One named destination: a lowercase DNS name, an IPv4 address, or an IPv6 address in brackets. Never the machine itself | yes, as a rule the host installs | |
| `net.listen:<port>` | One listening port, 1024 to 65535, never one of the firmware's, and one package per port | yes, as a rule the host installs | |
| `storage:<MiB>` | Names the data directory a service wants, in MiB | declared only: **no quota is enforced**, and every service has a data directory whether it asks or not | |

`motion.offsets`, `wizard`, and `mcode:<n>` are not in the vocabulary at
all: a manifest that asks for one is refused in those words.

**A `ui` package installs and does nothing.** The runtime is accepted and
the capability is granted, and no part of this firmware serves a package's
own pages yet. Until it does, a package's operator-facing surface is the
Extension packages card.

At most **15** outbound destinations take effect for one service, whatever
the manifest declares: the host's rule chain and the sandbox's port list
each hold 16, one of which a DNS lookup may take. A manifest naming more is
installed, and the ones past the fifteenth are dropped when the service
starts.

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
| `required-holds/` | One empty file per package whose hold the operator marked required, so a hold fails closed across a reboot before the host has read anything |
| `settings/<id>.json` | A package's own settings, root's alone at 0600 |
| `lock` | The host's lock, taken around every change to the root |
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
  ([the extension sandbox](image-and-bsp.md#the-extension-sandbox)). A
  package that named a destination by DNS name rather than by address is
  given port 53 as well, to the resolvers of `/etc/resolv.conf` and over
  UDP and TCP, and that file is handed in as one more read-only path: a
  name it cannot look up is a destination it cannot reach;
- cannot make the system calls a package has no business making, and can
  open only UNIX, IPv4, and IPv6 sockets (seccomp).

A step that cannot be taken is a failed start, never a looser sandbox. The
environment is fixed: `PATH`, `LANG`, `HOME` (the data directory),
`TMPDIR`, `FFX_ID`, `FFX_PKG`, `FFX_DATA`, `FFX_API` (its
[API socket](#the-extension-api)), `PYTHONDONTWRITEBYTECODE`, and
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
`GET /cool/status`, read once a second. On the bench reference, across a
37.5 s window, the service's group read frozen 0.4 s after the field turned
on, 5 s before the latch unlocked for the run, and thawed 0.6 s after it
turned off.

**Holds.** A package with the operator's `hold` grant may withhold fire
and never permit it ([An extension's hold](cooling-engine.md#an-extensions-hold)
has the engine's side: the verdict `EXT`, the pause tier, and the
operator's exits). The host owns the hold, not the package, so a package
that is frozen for the job changes nothing about it. For every enabled
package with the grant that runs in the controller mode in force, the host
keeps `/run/forgefirm/holds/<id>.json`. A thread that does nothing else
rewrites the files twice a second, and only while the main loop has spoken
within 15 s: a turn that takes a few seconds pauses nobody's job, and a
loop that hangs lets every hold go stale, which is what it is.

The operator marks a granted hold **required** or **advisory**
(`forgeext hold <id> required|advisory`; advisory until marked), and the
package is then named under `<root>/required-holds/` for the engine:

| The package | Advisory | Required |
|---|---|---|
| runs, and has run healthy | What it last said | What it last said |
| has started and not yet run healthy | What it last said | Raised by the host: "the extension has only just started". A package that ends at every start reads as running for a moment each time, and a required hold does not flicker clear with it |
| should run and does not (ended, waiting, quarantined, the machine not ready) | Dropped, and logged once | Raised by the host: "the extension is not running" |
| the host itself gone, however it went | Dropped by the engine | Stands in the engine, on the stale file or on the name alone |

A running package raises and clears its own hold over its
[API socket](#the-extension-api) (`POST /v0/hold`); its word starts clear
with every start of its service. Extensions off and safe mode take every file away, and the engine does not
look at the names then; a package that is disabled or removed loses its
file and its name. Those are the operator's exits. A clean stop of the
host removes the advisory files and leaves the required ones to go stale.
`status.json` and `forgeext list` say which hold is which.

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
`not_ready`, `events` (`connected`, and `wanted`: the running services
that hold the `events` capability), and per service `id`, `state`
(`stopped`, `running`, `waiting`, `quarantined`), `account`, `pid`,
`frozen`, `job_limited`, `healthy`, `hold` (`required` or `advisory`, when
it has one), and `reason`.

The acceptance test `exthost.service` proves the host on the image with a
reference package it builds and signs on the board: the confinement seen
from inside the service (its API socket included), safe mode, a killed
host, and the master switch.
`exthost.hold-pause-tier` takes a required hold from the grant to the
engine's verdict and out through each of the operator's exits, the
package's own raise and clear over its API socket included.
`exthost.armed-freeze` opens a real armed window over it with a dark cloud
print and samples the engine's flag, the group's state, the service's
heartbeat, and the latch five times a second: frozen from 2 s in to the
close with the heartbeat still, the freeze in place before the latch unlocks
for the run, thawed within 3 s of the close, one process throughout.
`exthost.package-routes` drives the operator's door against the host's
own state, and `exthost.panel-install` installs through it at each tier's
consent, the button held included. `exthost.events` proves the one
subscription and the poll a package reads it with. `exthost.platform`
proves the image holds the sandbox ready before any of it runs.
`setup.extensions-consent` proves the consent
([Release acceptance](../../developers/acceptance.md)).

## The operator's door

forgectrl is the machine's one front door, and the extension host is the
only program that reads what a package brought, so the panel's package
routes are a relay: forgectrl runs the host's command line (below), which
answers in JSON, takes the host's lock around every change, and is what
root at the console runs too. The host's daemon picks a change up on its
next turn. Nothing of a request reaches a shell: the command is an argument
vector, a package id is checked against the form of one before it is an
argument, the actions are a closed list, and the child inherits none of
forgectrl's descriptors (it holds the pulse device).

`GET /ext/status` answers `enabled` (the master switch), `safe_mode`,
`host` (the host's own status file with `running: true`, or `running:
false` alone when no host is alive behind it), and `packages` (the host's
`list`: id, version, tier, key, enabled, quarantined, grants, the hold's
kind, the account, and the manifest). `POST /ext/package` takes `id` and
`action`: `enable` (which also lets a package out of quarantine),
`disable` (its service stops and its hold goes: the way out of a hold it
has on a job), `remove`, `remove-keep-data`, `hold-required`,
`hold-advisory`.

### Installing through the panel

Two requests. `POST /ext/upload` stages one archive (a second upload
replaces it; `POST /ext/upload/discard` removes it) and asks the host what
it is: the answer is the host's `inspect` (the tier, the manifest, what
needs a grant, what is new against the installed version, whether it is a
downgrade) with `consent` added. An archive the host will not take is
refused in the host's words and not kept. `POST /ext/install` then names
the grants and carries the consent, and forgectrl asks the host again what
the staged file is, because the tier is never the request's to say:

| Tier | Installing takes |
|---|---|
| Official | The login |
| Community | The login and the typed phrase `I UNDERSTAND` |
| Unverified | The login and the machine's button held while the request is made, as for unsigned firmware; the phrase is no substitute |

forgectrl passes the host the consent it took (`--consent-community`,
`--consent-unverified`) and the grants, each checked against the form of a
capability name before it is an argument; which grants a package needs,
and that no grant is given that it did not ask for, is the host's to
enforce. The staged file goes with a successful install and stays after a
refused one, for another try.

### The owner's keys

A package is judged by who signed it: the OpenGlow extension key makes it
official, a key under `<root>/keys/*.pub` makes it community, and anything
else is unverified. Those keys are the owner's, and the trust anchor is
theirs to replace, so `POST /ext/key` takes one only with the machine's
button held, the way unsigned firmware is installed. The key itself is
written to a file and handed to the host as a path, never as an argument,
and the host parses it as an Ed25519 public key (fwup's base64, or 32 raw
bytes) before it lands: what cannot be read as a key never becomes a trust
anchor. A name is letters, digits, dash, underscore, and dot, at most 48
bytes, and the file under `keys/` is that name with `.pub` after it.

`POST /ext/key/remove` takes one away. A package installed under a key
that is then removed stays as it was: the key decides what an **archive**
reads as at the moment it is inspected, not what an installed package is.
`GET /ext/status` lists the keys with each one's id, the same id a
package's `key` names.

## The extension API

A package reaches the machine through the host or not at all: no listener
of the machine answers a pool account
([the extension sandbox](image-and-bsp.md#the-extension-sandbox)). Every
running service has one Unix stream socket, `/run/forgefirm/ext/api/<id>.sock`,
owned by root and the package's account at mode `0660`, and named in its
environment as `FFX_API`. The account is the only one that can connect, the
socket says which package is calling, and the host checks the caller's
credentials against it anyway. The socket exists before the service starts
and goes when it ends.

The API is version `0.1` and carries no stability promise. One request per
connection, HTTP/1.0 or 1.1 in a closed form, JSON both ways:

- the request line is `GET` or `POST`, one space, an origin-form path of
  letters, digits, `/`, `.`, `-`, and `_` (no query, no escape, no `..`), one
  space, the version;
- lines end in CRLF; no continuation lines, no transfer coding, one
  `Content-Length`, nothing after the body;
- the head is at most 4096 bytes and the body at most 4096.

What does not fit is refused with a status and a sentence
(`{"error": "..."}`), never guessed at.

| Request | Needs | Answers |
|---|---|---|
| `GET /v0/self` | | `id`, `version`, `api`, and `capabilities`: the ones the package may use (those that need no grant, and its grants) |
| `GET /v0/machine/status` | `machine.read` | forgectrl's `GET /status` |
| `GET /v0/machine/cool` | `machine.read` | forgectrl's `GET /cool/status` |
| `GET /v0/machine/mode` | `machine.read` | forgectrl's `GET /mode` |
| `GET /v0/settings` | `settings.own` | `settings` (every declared key with its value) and `schema` |
| `POST /v0/settings` | `settings.own` | A patch of settings, applied whole or not at all; the same answer |
| `GET /v0/hold` | `hold`, granted | `{"raised": bool, "reason": "..."}` |
| `POST /v0/hold` | `hold`, granted | The body `{"raised": bool, "reason": "..."}` (those two keys and no other; the reason at most 95 bytes of printable ASCII without the quote and the backslash) raises or clears the package's hold; the new state |
| `POST /v0/events` | `events` | The body `{"since": n, "wait": s}` (those two keys and no other, both optional) asks for the machine's events after `n`, waiting up to `s` seconds for one; `{"next": n, "dropped": n, "connected": bool, "events": [{"seq": n, "event": "...", "data": {...}}]}`. See [The events a package reads](#the-events-a-package-reads) |

A capability the package does not hold is `403` in words, a path the API
does not have is `404`, and the machine routes are relayed only as JSON
objects (`502` when forgectrl does not answer, or answers anything else).
The broker runs on a thread of its own, so a slow answer from forgectrl
delays other packages' requests and never the supervisor's turn. Each
package has 20 requests a second (`429` beyond that, after the request has
been read) and 4 of the broker's 16 connections; a request that has not
arrived in 5 s is `408`.

### A package's own settings

A package's data directory is its own and it could keep a file there
without asking anybody. These are the settings that are **not only its own
business**: the ones the operator is shown and may change, and the ones
that must outlive the package being updated or reinstalled. They are never
keys of `forgefirm.conf`, and a package can reach no key but the ones its
own manifest declares.

The manifest is the schema. A `settings` object names at most 16 of them;
each key is lower-case letters, digits and `_`, starting with a letter, at
most 32 bytes:

```json
"settings": {
  "webhook":   { "type": "string", "default": "", "max": 128, "label": "Where to post" },
  "threshold": { "type": "number", "default": 40, "min": 0, "max": 100 },
  "loud":      { "type": "bool",   "default": false },
  "when":      { "type": "choice", "default": "end", "choices": ["start", "end", "never"] }
}
```

| Type | Takes | Also |
|---|---|---|
| `string` | Printable text with no control characters, at most `max` bytes (128 unless it says otherwise, and never more) | |
| `number` | A number, within `min` and `max` when either is given | |
| `bool` | `true` or `false` | |
| `choice` | One of `choices`: 2 to 6 short tokens | `choices` is required |

`default` is required and is held to the setting's own rule, so a package
cannot declare a default its schema would refuse. `label` is what the
operator is shown, and is the key's name when it says nothing. Anything
else in a setting, a type there is none of, a `min` on a string, or
`choices` on anything but a choice is a manifest refused with words.

The values live in one file per package under the extension root, owned by
root at 0600. **The package never touches that file**: it reads and writes
through its API socket, so it cannot put in what its own schema refuses.
A write is **all or nothing** - a patch naming one key the schema does not
declare, or one value that does not fit, changes none of them, because
half an applied patch is a state the package never asked for. A patch
leaves alone every key it does not name.

The schema is read from the installed manifest each time, so an update
that changes it changes what the settings are from that moment. A value
the new schema no longer takes reads as its default, and a key it no
longer declares is gone. Removing a package removes its settings.

### The events a package reads

forgectrl publishes the machine's edges as a stream and caps the streams,
because each one holds a thread of the daemon for hours
([The event stream](forgectrl.md#the-event-stream)). The host takes **one**
subscription, in the slot forgectrl keeps for it, and every package reads
from the ring it fills: a machine with ten packages still costs forgectrl one
stream. The host holds that subscription only while some running service
holds `events`, because forgectrl's sampler sleeps when nobody listens.

A package reads the ring with `POST /v0/events`, which is a poll and not a
stream. It says the sequence number it has and is answered with what came
after it. It is a `POST` because the request reader above refuses a query
string on purpose and a poll needs its numbers; the body carries them
instead.

| The body | Asks for |
|---|---|
| `{}` or `{"wait": s}` | Where the present is: the answer is `next` at the head, no events. A package that does not want the past starts here |
| `{"since": n}` | What came after `n`, at once |
| `{"since": n, "wait": s}` | The same, but when `n` is the head the answer waits up to `s` seconds (at most 30) for an event, and comes back with an empty list if none comes |

`since: 0` is the beginning of what the host still holds, which is a
different question from asking where the present is: a package that started
before the first event stands at 0, and it has to be able to be told of the
events it was there for. A `since` past the head is a feed that started over
under the reader (the host was restarted): the answer comes at once with
`next` back at the head, and a reader that compares the two sees the rewind.

At most 32 events come back at a time and the rest waits for the next call.
The host holds the last 64; a reader that falls a whole ring behind is told
how many it lost in `dropped` and handed the oldest still held, never a stale
event as if it were new. `connected` says whether the host has the machine's
stream at that moment. Each event's `data` is forgectrl's own JSON, passed on
as it was written.

## The command line

`forgeext` answers every command with one JSON object and exits 0 when
`"ok"` is true. A command it does not know, or one missing an argument, is
the exception: that is a usage error, printed as plain text on standard
error with exit 2. `key-add <name> -` reads the key from standard input.
`forgeext --help` prints the whole of it, the global options (`--root`,
`--fwup`, `--official-key`, `--firmware-key`, `--nft`, `--budget-mib`,
`--no-reserve`) and `run`'s own included.

| Command | Does |
|---|---|
| `inspect <file.ffx>` | Everything an install checks short of consent and grants, with nothing left behind: the tier, the manifest, what needs a grant, what is new against the installed version, whether it is a downgrade |
| `install <file.ffx> [--grant <capability>]... [--consent-community] [--consent-unverified]` | Installs, or refuses in words |
| `list` | What is installed |
| `check [<id>]` | The integrity check |
| `remove <id> [--keep-data]` | Removes the package and, unless told otherwise, its data |
| `enable <id>`, `disable <id>` | The operator's switch for one package. Disabled, it keeps its files, its data, its grants, and its account, and its service and its hold are gone; enabling it also lets it out of quarantine |
| `hold <id> required\|advisory` | What the package's hold does when the package cannot speak for itself: stand, or drop |
| `keys`, `key-add <name> <file.pub>`, `key-remove <name>` | The owner's keys. `key-add` parses the file as an Ed25519 public key before it is written |
| `caps` | The capability list and the API version |
| `net-check` | Whether the image's deny table is loaded |
| `net-allow <uid> [--listen <port>] [--dns] [<host>:<port>]...` | A service's chain in the deny table, as the host installs it when a service starts |
| `net-revoke <uid>` | Takes that chain away again |
| `run` | The extension host, above |
