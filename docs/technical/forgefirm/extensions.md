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
| **Community** | A key the owner added under `/data/forgefirm/ext/keys/`, or the author's key that the [signed index](#the-signed-index) endorses for that package's id | The operator's typed consent |
| **Unverified** | Nobody this machine trusts: unsigned, or signed by a key it does not hold | The machine button held, as for unsigned firmware |

- The ids under `org.openglow.` and `org.forgefirm.` belong to the official
  tier: an archive that claims one and is not signed with the OpenGlow
  extension key is refused.
- **An update is signed by the key that signed the installed version.** A
  package cannot change its signer, or lose its signature, by updating;
  the owner removes it first.
- Nothing updates itself. An update is the operator's act, and what it asks
  for that the installed version did not is shown as new.

## The signed index

The catalog the panel shows is one file, `index-1.ffi`: an archive of the
package container's own form whose `meta-product` is
`ForgeFIRM extension index`, signed with the OpenGlow extension key and by
nothing else, holding one file, `index.json`, of at most 1 MiB. Its
`meta-version` is the index's own version, `YYYY.MMDD.N`. No owner key and
no endorsed key speaks for an index, and the product gate holds both ways:
an index is never a package, and a package is never an index.

**One index serves every firmware.** `index.json` is
`{"index": 1, "packages": [...], "withdrawn": [...]}`. The `1` is the
schema, and the file's name carries it too: a catalog that changes its form
publishes `index-2.ffi` beside `index-1.ffi`, and each machine goes on
reading the file its firmware knows. A field the host does not know is
passed over at every level, so a catalog that adds one is still kept by an
older machine.

The index lists at most 512 packages, each id once:

| Field | Holds |
|---|---|
| `id` | The package id |
| `name`, `author` | Text, at most 64 and 128 bytes |
| `description`, `license` | Text, optional, at most 256 and 64 bytes |
| `homepage` | Optional, `https://` |
| `key` | The author's Ed25519 public key, as fwup writes it: required for an id outside OpenGlow's namespace, and refused for one inside it |
| `versions` | 1 to 16 listed versions, each version once |
| `withdrawn` | Optional: at most 64 versions that OpenGlow withdrew, each `{"version", "reason"}`, none of them also listed |

Each listed version:

| Field | Holds |
|---|---|
| `version` | The version |
| `url` | Where the archive is fetched: `https://`, no user or password, at most 1024 bytes |
| `sha256`, `size` | The archive's SHA-256 (64 lowercase hex digits) and its size in bytes |
| `capabilities` | What its manifest asks for: at most 64 names, each printable text with no space |
| `api` | Optional: the extension API its manifest names |
| `core` | Optional: the firmware range its manifest names, `{"min", "max"}`, each a version. The catalog can narrow a range after the listing, and never widens it |

The top-level `withdrawn` names the packages that OpenGlow withdrew whole,
at most 512, each `{"id", "key", "reason"}`. The `key` follows the rule of a
listed package, and no id is both listed and withdrawn.

An index whose form breaks any of these rules is refused whole, and the
index kept stays. The form is all that keeping an index judges.

**Judged when read.** Whether a version runs on this firmware is judged
when the index is read (`forgeext index`), never when it is kept. Thus a
newer catalog never stops an older machine from keeping it, and after a
firmware update the machine sees what it now runs with no new fetch. A
version is usable when all of these are true:

- The firmware's version is inside the version's `core` range. A dev
  image's version is a build stamp and not a version, so no range is
  judged there, and the answer's `core_checked` says so.
- Its `api` is the extension API this firmware serves.
- This firmware has every capability it asks for.
- Its size is at most what this firmware takes, 32 MiB.

Each version gets `usable`, and `why` when it is not usable. Each package
gets `offer`, the newest usable version, or null. With no offer, the
package also gets `why`: the newest listed version, and what keeps it off
this firmware. The judgment belongs to the reading, and it is never written
into the index kept.

**The endorsement.** A package signed with the key that the index names for
its id reads as **Community** on a machine whose owner never added that
key, and `inspect` says `endorsed: true`. One author's key can be named for
several ids, and it speaks for each of them. It speaks for those ids alone:
an archive under another id signed with it is judged as signed by nobody.
Pinning holds as for every package: an update is signed by the key that
signed the installed version.

**Never back.** An index older than the one kept is refused, however well
it is signed. An index that OpenGlow signed once stays signed, so a copy of
an old one would list again what was withdrawn after it. The same version
again is kept.

**Withdrawn.** A withdrawal names the listed package: its id, signed with
the key that the index names for it (in whichever key directory the machine
finds that key), or with the OpenGlow extension key in OpenGlow's own
namespace. An archive of the same id under another key is another package.

- A **withdrawn version** does not install, from the catalog or from a
  file: `inspect` and `install` refuse it in OpenGlow's words, with its
  reason.
- A **package withdrawn whole** is out of the catalog, and its key endorses
  nothing. An archive signed with that key reads as unverified, unless the
  owner added the key. Then the owner's key speaks for it, and `inspect`
  shows the withdrawal (`withdrawn`, with the reason) for the owner to
  judge.
- An installed copy of either stays installed. The machine removes nothing
  on its own, and `list` names the withdrawal: `withdrawn` is
  `{"scope": "version" or "package", "reason"}`, or null. An update of a
  package withdrawn whole is judged as signed by nobody, and pinning
  refuses it.

**Kept.** `forgeext index-verify` checks the archive, lays out `index.json`
(with the index's version and each named key's id added) and one
`keys/<id>.pub` for each listed package's key, and swaps them in whole under
the host's lock. A change of owner leaves the index: it is OpenGlow's, not
the owner's.

**Where it comes from.** forgectrl fetches it only when the operator asks
([The catalog](#the-catalog)), from one fixed address:
`https://github.com/openglow-org/forgefirm-extensions-catalog/releases/latest/download/index-1.ffi`.
The hosting is not trusted; the signature and the version are. How a
package is listed, and how the index is built and published, is the
[listing policy](../../developers/extension-listing.md).

The acceptance test `exthost.catalog` proves it on the image. On a scratch
root, the machine's own `forgeext` keeps an index signed with a stand-in
for the extension key, and the key it endorses makes that one id community
and no other. Read back, a version that asks for a capability the firmware
does not have is kept and not offered, and the offer is the newest version
it runs. An older index is refused, and an index that withdraws the probe's
version makes the probe refuse to install. On the machine's own root, the
host refuses every index that key did not sign, and a package handed over
as one. forgectrl's catalog routes refuse before they fetch, and leave
nothing staged. The test never requests the index's address, because
GitHub counts every request of it as a download, and that count is the
operators'. The fetch itself is proven by forgectrl's host test with a
stand-in for curl.

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
| `core` | Optional `min` and `max` firmware versions. A package outside the range is refused at inspect and at install, when this firmware has a version to judge by ([The firmware a package needs](#the-firmware-a-package-needs)) |
| `runtime` | `data` (nothing executes), `ui` (runs in the operator's browser), `shell`, `native` (an ARMv7 hard-float binary, static or linked against the C library alone: `libc.so.6` and `libm.so.6`, with no symbol newer than the image's glibc 2.39), or `python` (inside the release image's module list) |
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
([The extension API](#the-extension-api)). Every capability this firmware
offers is served; the column stays because the vocabulary is settled
ahead of the routes, so that a package's manifest and the operator's
consent do not change shape as each one lands.

| Capability | Grants | Served | The operator's own grant |
|---|---|---|---|
| `machine.read` | The machine's status, cooling status, and mode | yes | |
| `events` | The machine's events | yes | |
| `hold` | Holding a job until the package clears the hold (pause tier only) | yes | required |
| `settings.own` | The package's own settings, declared in its manifest ([A package's own settings](#a-packages-own-settings)) | yes | |
| `camera.lid`, `camera.head` | One frame from that camera, under the privacy gate, and never while a job is armed ([A package's camera](#a-packages-camera)) | yes | |
| `motion.jog` | Dark jogs inside the jog bounds, and canceling one ([A package's jog](#a-packages-jog)) | yes | |
| `motion.job` | Running a program as the machine's one sender, under every arm gate ([A package's job](#a-packages-job)) | yes | required |
| `job_time.run` | Not being frozen while a job is armed | yes, as a limit the host applies | required |
| `ui` | A page of its own in the control panel, in a sandboxed frame ([A package's own page](#a-packages-own-page)) | yes | |
| `net.outbound:<host>:<port>` | One named destination: a lowercase DNS name, an IPv4 address, or an IPv6 address in brackets. Never the machine itself | yes, as a rule the host installs | |
| `net.outbound.operator` | The destinations the operator names for it, and no others ([The operator's destinations](#the-operators-destinations)) | yes, as a rule the host installs | |
| `net.listen:<port>` | One listening port, 1024 to 65535, never one of the firmware's, and one package per port. It answers callers and is no way out ([the deny rules](image-and-bsp.md#the-extension-sandbox)) | yes, as a rule the host installs | |
| `storage:<MiB>` | How much its data directory may hold, 1 to 256 MiB. Every service has a data directory; this says how large it may grow ([The storage quota](#the-storage-quota)) | yes, as a limit the host enforces | |
| `wizard` | A check of its own on the Setup page, run on the setup's own runner, its result the package's ([A package's check on the Setup page](#a-packages-check-on-the-setup-page)) | yes | |
| `mcode:<n>` | Answering `M<n>` in a job, one of M160 to M179: the job waits at it until the service answers ([A package's M-code](#a-packages-m-code)). One package per number, and a package that asks for one asks for `job_time.run` too | yes | (`job_time.run`'s) |

`motion.offsets` is named in the list but is **not offered**: a manifest
that asks for it is refused in those words, which is a different refusal
from the one a name the list does not hold gets. Nothing this firmware
serves is reached by it.

At most **15** outbound destinations take effect for one service, the
manifest's and the operator's together: the host's rule chain and the
sandbox's port list each hold 16, one of which a DNS lookup may take. A
manifest naming more is installed, and the ones past the fifteenth are
dropped when the service starts.

Three rules tie capabilities to the runtime. A `data` package holds none.
`hold`, `job_time.run`, `net.outbound`, `net.outbound.operator`,
`net.listen`, and `storage` belong to a service, so a `ui` package cannot
hold them. And the capabilities
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
| `index/` | The [signed index](#the-signed-index) as last verified: `index.json`, and `keys/<id>.pub` for each key it endorses |
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
`PYTHONUNBUFFERED`, and `FFX_CALL_FD` for a service whose package has a
page ([its page's calls](#a-page-and-its-own-service)). A service's output goes
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
| A service whose version, or whose operator's destinations, changed | is stopped and started again with them, outside an armed window; that is not an end that counts toward quarantine |
| Extensions off, safe mode, the host stopping | `ext.shutdown` is put in the event feed, and the services are stopped one second later ([The events a package reads](#the-events-a-package-reads)) |

**The armed window.** While the window is open, every service is frozen
with its cgroup's `cgroup.freeze`, and it is thawed when the window closes.
A package with the operator's `job_time.run` grant is not frozen: it runs
on at 3 percent of the core. The freeze follows the `armed` field of
`GET /cool/status`, read once a second. On the bench reference, across a
37.5 s window, the service's group read frozen 0.4 s after the field turned
on, 5 s before the latch unlocked for the run, and thawed 0.6 s after it
turned off.

A service that does not freeze is not left running. The host waits 300 ms
for the kernel's `frozen` flag and asks again at its next turn; after three
turns the service is quarantined, with "it could not be frozen for the armed
window" as the reason, and the operator's enable is what lets it out. The
freeze is what keeps a package off the step stream, so a group that will not
take it is a defect and not a passing condition. Job-time limits that will
not take fall back to the freeze the `job_time.run` grant lifted, and the
service is quarantined only when neither takes. A thaw that fails costs
nobody but the package itself: it is logged and tried again at the next
turn.

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
consent, the button held included. `exthost.page-call` carries a page's
calls to its own service through the relay. `exthost.events` proves the one
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
kind, the account, the manifest, `withdrawn` (what the kept index says
OpenGlow withdrew of it, or null), and `effective` - the capabilities the
package may use, which is what needs no grant together with what the
operator granted. That last one is the list anything deciding what a
package may do reads, the panel's bridge included: the manifest's own
list is what was *asked for*, which is a different question), and `destinations`, the ones the
operator named for it. `POST /ext/package` takes `id` and
`action`: `enable` (which also lets a package out of quarantine),
`disable` (its service stops and its hold goes: the way out of a hold it
has on a job), `remove`, `remove-keep-data`, `hold-required`,
`hold-advisory`. `POST /ext/dest` takes `id`, `action` (`add` or `remove`),
and `dest`, and names a destination for a package or takes one away
([The operator's destinations](#the-operators-destinations)).

Three more routes are the panel's alone, and all three refuse while
extensions are off: `GET /ext/ui` hands over a package's own page
([A package's own page](#a-packages-own-page)), `GET` and
`POST /ext/settings` read and patch a package's own settings
([A package's own settings](#a-packages-own-settings)), and
`POST /ext/call` carries a page's call to its own service
([A page and its own service](#a-page-and-its-own-service)). They are what
the frame's bridge calls reach, never the frame itself.

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

### The catalog

`GET /ext/catalog` answers the host's `index`: `index`, the kept document
judged against this firmware ([judged when read](#the-signed-index)), or
`null` when none is kept; `core_version` and `core_checked`, the firmware
version it was judged by; and `url`, the address the index is fetched from.
Nothing reaches the network until the operator asks:

- `POST /ext/catalog/refresh` fetches the index with curl (`https` alone,
  redirects included, at most 2 MiB and 30 s, under curl's own name) into
  a file beside the staging file, has the host verify and keep it, removes
  the file, and answers as `GET /ext/catalog` does. A fetch that fails is
  `502` in curl's words, and the host's refusal is `409` in its words; the
  index kept stays as it was.
- `POST /ext/catalog/get` (`id`) reads the package from the kept index,
  never from the request, and takes the version the host offers: the
  newest one this firmware runs. It fetches that version's archive from its
  `url` into the staging file, bounded by its `size` and 240 s. The bytes
  are held to that size and that SHA-256 before the host reads any of them.
  From there it is an upload: the answer is the host's `inspect` with
  `consent` and `catalog` added, and `POST /ext/install` follows as above.
  Bytes that are not the listed archive, and an archive of another package
  or another version than the one offered, are refused with `409` and not
  kept. A package with no version this firmware runs is `409`, with the
  host's reason, before anything is fetched. An id the index does not list
  is `404`, and with no index kept it is `409`.

The fetch of a package is gated as the upload is (the machine idle, no
lease in the way), and the one staging file is the upload's or the
fetch's, never both at once. All three routes are the logged-in operator's,
and none of them refuses while extensions are off.

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

### The operator's destinations

A package that talks to things on the operator's own network - a smart
plug, a Home Assistant host, an MQTT broker - cannot name them in its
manifest: only the operator knows where they are. Such a package asks for
`net.outbound.operator`, and the operator names each place it may reach,
per package, on the package's card (`forgeext dest <id> add|remove
<host>:<port>` at the console). A package that asks is given none until
then. Nothing a package does reaches the list: it is not a setting and not
a bridge call.

A destination is `host:port` in `net.outbound`'s form. A numeric address
of the machine, loopback included, is refused when it is named; a name is
judged by what it resolves to when the service starts, and the rule table
refuses the machine whatever the list says. At most 8 are named for one
package, and never more than a service's 15 with its manifest's. An update
that still asks keeps them; one whose own destinations and the operator's
would be more than 15 is refused; one that no longer asks keeps none.

A change to the list starts a running service again at the host's next
turn, outside an armed window, and the new chain and the sandbox's ports
are its. GET `/v0/self` names every destination a service may reach, its
manifest's and then the operator's, and so does the bridge's `self`, so a
package's page can show the operator what is still to be named.
`exthost.operator-destinations` proves it on the image by dialing the
machine's own DNS resolver on TCP port 53: refused inside the sandbox until
the operator names it, connected once named, and refused again when it is
taken away.

### A change of owner

The forgotten-password reset ([Setup](../../usage/setup.md#a-forgotten-password))
is where a machine changes hands, and the account step offers to take the
extension tree with it: every package, everything under `data/`, and every
key the last owner added. A package can hold that owner's tokens and
credentials, and a key of theirs would go on making their packages install
as community rather than as unverified. The offer is made only when there
is something to take and is ticked by default; the account is made either
way, and a wipe that fails is reported rather than refusing the account.

Everything under `data/` goes, not only the directories the state names: a
package removed with its data kept leaves one behind, and it holds exactly
what the wipe is for. The root's own directories stay, and the supervisor
stops whatever was running when it next reads the state.

`forgeext wipe` is the command behind it. It is the reset's alone - no
route and no panel action reaches it, because an operator who wants one
package gone removes that package.

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
| `GET /v0/self` | | `id`, `version`, `api`, `capabilities` (the ones the package may use: those that need no grant, and its grants), and `destinations` (where it may connect: its manifest's, then the operator's) |
| `GET /v0/machine/status` | `machine.read` | forgectrl's `GET /status` |
| `GET /v0/machine/cool` | `machine.read` | forgectrl's `GET /cool/status` |
| `GET /v0/machine/mode` | `machine.read` | forgectrl's `GET /mode` |
| `GET /v0/settings` | `settings.own` | `settings` (every declared key with its value) and `schema` |
| `POST /v0/settings` | `settings.own` | A patch of settings, applied whole or not at all; the same answer |
| `POST /v0/camera` | `camera.lid` or `camera.head`, for the one it asks for | The body `{"camera": "lid"\|"head", "resolution": "full"\|"half", "quality": 1-100, "lamp": 0-1023}` (the camera required, the rest optional, and no other key); **the answer is a JPEG**, not JSON |
| `POST /v0/motion/jog` | `motion.jog` | The body `{"x":, "y":, "z":, "feed":}` in millimeters and mm/min, each a number and no other key, at least one axis moving; the machine's answer |
| `POST /v0/motion/cancel` | `motion.jog` | Ends a jog; the machine's answer |
| `POST /v0/motion/job` | `motion.job`, granted | The body `{"program": "<a file of its own data>", "lit_within_s":, "timeout_s":}`; the machine's answer |
| `POST /v0/motion/job/abort` | `motion.job`, granted | Ends the running job |
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

### A package's own page

A package that asks for `ui` ships **one** self-contained HTML file at
`ui/index.html`, at most 512 KiB. Asking for `ui` without the file is
refused at install, and shipping the file without asking for `ui` is
refused too. It is one file because the frame it renders in can fetch
nothing: there would be nothing to load a second file with.

`GET /ext/ui` hands the page to the panel **as a JSON string**. The daemon
composes no markup out of a package's file; the panel is what builds the
frame.

**The frame holds nothing.** It is sandboxed **without
`allow-same-origin`** - with it, the page would hold the operator's
session and the panel token, and every other measure here would be
decoration. Without it the page is its own opaque origin: it cannot read
the panel's cookies, reach the panel's window, or navigate the top window.

The sandbox attribute alone does not stop a page reaching the network, so
the policy travels **in the document, as its first element**:

```
default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';
img-src blob: data:; connect-src 'none'; form-action 'none'; base-uri 'none';
webrtc 'block'
```

A package may add its own policy after that one and only make it stricter.

**Where a frame may go is the panel page's to say, not the frame's.** A
frame's own policy governs what it loads; it does not stop the page
navigating its frame to another address, carrying what it was shown in the
URL. Every page forgectrl serves therefore sends
`Content-Security-Policy: frame-src 'none'`: no frame of the panel may
navigate anywhere. A `srcdoc` frame still renders under it, and the panel
frames nothing else.

**The proof is a browser harness**, because what it tests is the browser:
`tools/frame_isolation.py` in the `forgectrl` repository runs the panel as
its dev server's mock serves it, installs a hostile package whose page tries
every way out, and opens that page through the panel's own frame and bridge
([Test](../../developers/testing.md#the-frame-isolation-harness)).
`forgectrl.panel-serves` holds the machine's own page to sending the header.

**WebRTC is a documented leak.** It is outside the Content Security Policy
in both browsers this project tests, and connection hints get past it at
low bandwidth. A package with a page can therefore send a little data out
of the operator's browser. That is named here and on the operator's own
page ([Extensions](../../usage/extensions.md#a-packages-own-page)), and a
package without a page cannot do it at all.

**The label above the frame is the panel's**, outside the frame: the name
and the trust tier are what the panel knows of the package, never what the
package claims. When the panel knows neither, the label says the id and
nothing more.

#### The bridge

The page reaches the machine only by asking the panel, over `postMessage`.
Three rules govern it:

- **A frame is known by `event.source`, never by `event.origin`.** Every
  sandboxed frame reports the origin `null`, so two open packages are
  indistinguishable by origin; identifying by origin would let either
  speak for the other.
- **The capability checked is the one the machine says the package may
  use**: the `effective` list of `GET /ext/status`, which is the same
  answer the package's own API socket gives a service at `GET /v0/self`.
  The manifest's list is what was asked for and is never the test. What a
  frame claims about itself is never an input either.
- **A package the operator disabled holds nothing.** Disabling is the way
  out of everything a package does: its page stops being served, and a
  frame already open is closed at the panel's next refresh rather than
  left talking to the bridge.
- **No credential ever enters a message.** The panel makes each call under
  its own session. A camera frame is fetched by the panel and handed over
  as bytes, so the camera key stays where it is.

| The page asks for | It needs | It gets |
|---|---|---|
| `self` | | its id, version, tier, the capabilities it may use, and the destinations its service may reach (the same lists `GET /v0/self` gives its service) |
| `machine.status`, `machine.cool`, `machine.mode` | `machine.read` | the machine's own answer |
| `settings.get`, `settings.set` | `settings.own` | its settings and their schema |
| `camera.frame` | `camera.lid` or `camera.head` | the frame as bytes, taken as a background capture, so it yields to a viewer and is refused while a job is armed. It takes `camera`, and optionally `resolution` (`full` or `half`, the default), `quality` (1 to 100), and `lamp` (0 to 1023); a value outside those is refused by name, and nothing else in the message is carried |
| `motion.jog` | `motion.jog` | the machine's answer, under every bound the jog already has |
| `motion.cancel` | `motion.jog` | ends a jog |
| `motion.job` | `motion.job`, granted | a program the page wrote (`program`, at most 2 MiB, with the optional `lit_within_s` and `timeout_s`) run as the machine's one sender; **who the job is from is the panel's word, the package's id**, never a name the page chose |
| `motion.job.state`, `motion.job.abort` | `motion.job`, granted | the job's record, and ending the running job |
| `frame.height` | | the page's own frame made `px` tall, inside 200 to 1400 pixels; the label and the panel around the frame do not move |
| `service.call` | `ui` | a call to **its own package's service**, whatever package the message names (`method`, `path`, and for a `POST` an optional `body` object); `{status, body}`, the service's own status and the JSON it answered ([below](#a-page-and-its-own-service)) |

Anything else is refused by name, and a capability the package does not
hold is refused in those words.

#### A page and its own service

A package that has a page and a service may have the one ask the other: a
rules editor, say, whose service is what applies the rules. Nothing about
it is a way out for either side. The page still reaches nothing but the
bridge, and the service is still reached by nothing but the host.

**The socket is the host's.** For a service whose package asks for `ui`,
the host binds `/run/forgefirm/ext/call/<id>.sock`, root's socket at mode
`0600` in a directory that is root's alone (`0700`), and hands the service
only the listening end, at descriptor 4, named in its environment as
`FFX_CALL_FD=4`. The service answers; it never names a path, so there is
no socket the host could be pointed at but the one it made. The name goes
when the service stops.

**A call is one request per connection, in a closed form.** The host
writes it: `GET` or `POST`, a path of letters, digits, `/`, `.`, `-`, and
`_` (no query, no `..`, at most 200 bytes), and for a `POST` a JSON object
of at most 4096 bytes, which the host parses and writes out again (`{}`
when the page sent none; a `GET` carries none). The service answers
HTTP/1.1 with a status and JSON, at most 64 KiB in all, within 10 s. What
comes back to the page is the service's own status and its JSON: a
service's refusal is its own, not the relay's.

**What refuses a call, in words:** a package that is not installed, one
that is disabled ("its service is not running"), one with no page or no
service, a service that is not running, one frozen for the armed window
("its service is frozen while a job is armed", said at once rather than
after the wait), an answer that is late, too long, or not JSON. A package
with the `job_time.run` grant is not frozen and answers through the
window.

The panel's bridge makes the call as `POST /ext/call` (`id`, `method`,
`path`, `body`) under its own session, with the package's id from the
frame that asked. forgectrl holds the method, the path's leading `/`, and
the body's being an object before anything runs, and the host's command
`forgeext call` judges the rest; the kit's `ffx.serve()` (Python) and
`ffx_serve_one()` (C) are the service's side
([Write an extension package](../../developers/extensions.md#a-page-and-its-own-service)).
`exthost.page-call` proves the relay on the image, forgeext's `sdk_test`
the socket, both clients of the kit, and a frozen service, and the
frame-isolation harness that a page's call is its own package's whatever
the message names.

### A package's jog

A jog is the one call in this API that **moves the machine**, and it is
the only motion a package reaches: there is no arbitrary G-code here, and
a jog is the one motion that ships dark whatever the laser's modal state
is.

It is bounded **twice**. The host refuses a jog past the bounds without
asking the machine, and the machine refuses it again: the machine owns
them and is the only thing that can enforce them, and the host keeping to
the same numbers means a package's mistake never becomes a line the
machine has to turn away.

| | At most |
|---|---|
| X and Y, one jog | 100 mm |
| Z, one jog | 5 mm |
| Feed | 10 to 12000 mm/min |

Everything the machine already enforces still stands and is the machine's
to enforce: GRBL mode only, the machine lease, and the rule that **a
sender at the controller port always wins** - a line from LightBurn
cancels a package's jog.

**The lid being open does not stop a jog**, and a jog is motion the
operator did not ask for. That is said plainly in the Extensions advisory,
because it is the one thing a package does that an operator can be
standing inside.

#### How the host is allowed to ask

A jog is a write, and the machine grants a write to nobody without a
credential. The host has one of its own: forgectrl mints it fresh every
time the daemon starts, it holds **only** what the host may relay, it is
never in the store and never in the operator's list of tokens (it is not
theirs to manage, and revoking it by accident would stop extensions), and
it dies with the daemon. It is written to `/run/forgefirm/ext-host.token`
at mode 0600, which an extension account cannot read - and could not use
if it could, since a pool account cannot reach a loopback listener at all.
forgectrl takes it **from a loopback peer only**.

The panel token is deliberately not used for this: it reaches every route,
so a flaw in the host or its broker would reach every route too.

### A package's job

`motion.job` is the widest capability a package can hold, and it is one
of the three the **operator grants by hand**, whatever the package's tier.

**A program is named, not sent.** The request reader takes 4 KiB of body
and a program is not that, so a package writes its program into its own
data directory and names the file. The name is a file name with **no
directory in it**, and the host resolves it and checks the result is
really inside that package's data directory - a link or a `..` out of it
is not a program the host will read. The program is at most 2 MiB, which
is also what the package's storage quota has to hold.

**Who the job is from is the host's word, not the package's.** The job
carries the package's id as its sender. A package that could name the
sender could make a job look as though it came from somewhere else.

Everything the machine already does to a sender it does to this one, and
those are the machine's to enforce: the job runs **under the machine
lease**, it is **refused while a sender is connected** (LightBurn holds
TCP 23 outside the lease), and **every arm gate and the button press
stand**. A program that commands no laser never opens an armed window,
so there is nothing for a press to arm; the gates are in force and are
simply never reached.

### A package's M-code

M160 to M179 belong to packages. A package that holds `mcode:<n>` answers
`M<n>` in a job: the exhaust confirmed on, the air assist's pressure, a
door, a count. Each number is one package's (an install that asks for a
number another installed package holds is refused in words), and the
package asks for `job_time.run` as well, which the operator grants: the
M-code is answered in the middle of a job, while the armed window freezes
every other service.

**Nothing answers it: the job stops where the line is parsed.** The GRBL
controller takes one of these numbers only while forgectrl says something
answers it now, and every other one is the core's `error:20`, as for any
unsupported command, before the job's motion reaches it. forgectrl tells
the controller the numbers the host's running services answer, from the
host's status file, whenever they change and every 2 s (so a controller
that restarted learns them again).

**Something answers it: the job waits there.** The M-code is a
synchronized barrier. The core drains the planner before it runs it, which
means every step is the stream's, not that the head has stopped: the kernel
is still playing the last move's tail out of its ring. So the controller
waits for the kernel to go idle (at most 5 s, or the job is held) before it
announces the M-code, and from then on the head is still and the stream
carries no fire: the laser is dark for as long as the job waits, by the
stream's own rule for a starved planner. The controller puts the M-code in
its port's state with its `P`, `Q`, and `R` words ([The controller port](controller-port.md)) and pumps the protocol as
a dwell does, so status reports, a feed hold, the door, and a soft reset all
work, and a reset or an alarm ends the wait at once. forgectrl's relay sees
it, and asks the host (`forgeext mcode`), which asks the service on its call
socket, the one a page's calls use:

```
POST /mcode
{"code": 160, "words": {"P": 1}}
```

A package that answers M-codes has the socket (`FFX_CALL_FD`) whether or
not it has a page. A 2xx answer lets the job go on, and its `message`, if it
has one, goes to the sender as `[MSG:M160: done: <message>]`. Any other
answer, the host's refusal of the call (the package disabled, frozen, or
never granted `job_time.run`), or **no answer in 30 s** holds the job with a
`[MSG:]` that says why: the operator resumes it, and it goes on without what
the M-code was for, or stops it. The host gives the service 20 s, so its
answer, or its silence, comes back inside the controller's 30. The 30 s
stays under `laser_disarm_s`'s default of 60, so a job waiting at an M-code
keeps its armed window. A port jog is refused while a job waits
(`busy:mcode`): the job is Idle there, and it is still the job.

The driver's `mcode_test.py` harness proves the controller's side on the
null-sink build: the table and its refusals, `error:20` for a number
nothing answers, the wait with the head still and a port jog refused, the
answer's words, a refusal and a timeout each holding the job, a reset
ending the wait, and **a wait under an open armed window with `M3 S500`
shipping no FIRE tick**. forgectrl's `mcode_test` and forgeext's `sdk_test`
and `install_test` prove the relay and the host. On the machine,
`exthost.mcode` runs dark jobs through a package that answers M160: the
job waits with the head still and goes on after the answer, a job naming
M161 stops at it with nothing moved, and a refusal holds the job.

### A package's check on the Setup page

A package that holds `wizard` adds a check of its own to the Setup page,
as `pkg:<id>`, after the machine's own checks. It runs on the setup's own
runner, with the same log, progress, prompts, and result a check of the
machine's has, and the runner asks the package's service for each step on
its call socket (`forgeext wizard <id> state|start|answer|abort`):

| Request | The service answers |
|---|---|
| `GET /wizard` | `{"title": "...", "done": true or false}`: the Setup page's list names the check with it |
| `POST /wizard/start` | The first step |
| `POST /wizard/answer` `{"id": "...", "answer": "..."}` | The next step, after the operator answered a prompt; a confirm is answered `yes` or `no` |
| `POST /wizard/abort` | Anything; the operator stopped the check, or it ran out of time or of form |

A step is `{"log": [...], "phase": "...", "progress": 0 to 100,
"prompt": {"kind", "id", "text", "options"}}`, the prompt's kind one of
`continue`, `confirm`, `number`, and `choice`, or, the last step,
`{"result": {"ok": true or false, "summary": "..."}}`. The runner holds a
step to its form (at most 8 log lines, a prompt's id a word, a choice with
two options at least, a text's length) and to 64 steps, and stops the check
with the reason, telling the service, when one is out of form.

**The check is the package's, and nothing of the machine's is.** Its result
is kept by the package, and the Setup page's list reads it back from
`GET /wizard`; the machine's setup record never holds it, and no package's
check is in the setup gate or is ever the next open step. It holds no
machine lease: whatever it does to the machine it does through the
package's own capabilities, under the lease like any other request of the
package's. It can gate only the package's own work.

`exthost.wizard` proves it on the image: the check listed, run through
its prompt with the lease free, the operator's Yes reaching the service as
`yes`, the result the package's summary and listed as done from its own
answer, the machine's setup record and gate unchanged, an abort reaching
the service, and a check of a package that is not installed refused.
forgectrl's `wizpkg_test` holds each step to its form and runs a check
end to end on stand-ins; forgeext's `sdk_test` runs the command against a
service.

### A package's camera

`camera.lid` and `camera.head` are separate capabilities, and the one a
package asks for is the one it must hold: a package granted the lid's
camera is refused the head's in words.

**The answer is a frame, not JSON.** `POST /v0/camera` comes back as
`image/jpeg` with the bytes, or as a JSON error with a status. It is a
`POST` for the same reason the other calls are: the request reader
refuses a query string on purpose, so the body carries the parameters.

The privacy gate stands exactly as it does for anyone else: **no camera
captures while the lid is open**, and a package is told so in the
machine's own words.

**The lamp is the camera's own light, for one frame.** `lamp` sets the
head camera's LED, or the lid camera's lamp, for the capture it is asked
with, and the machine puts its level back after it. A head-camera picture
of light wood wants little light and a dark material a lot, so the level
is the package's to choose; without it, the lamp stays where the machine
has it.

**A package's capture always yields to somebody watching.** A capture
borrows the camera mux for a frame and stutters a running stream while it
does, which is a fair price when a person asked for the picture and none
worth paying when a program did. Every capture a package makes is marked
as one nobody is waiting for, so while a stream has a client the package
is refused (`409`, again in the machine's words) and the operator's own
viewing is untouched. The package retries when they stop.

**No package takes a picture during a cut.** A capture costs kernel-side
work beside the step stream that a thread priority does not cover, which
is the same reason a service is frozen for the window. So a capture
marked as one nobody is waiting for - which is every capture a package
makes, through its API socket or through the panel's bridge - is refused
with `409` while a job is armed, and served again once the window closes.
The operator's own snapshot is unmarked and is not refused: they are
standing at the machine. The refusal follows the `armed` field of
`GET /cool/status`, the same flag the freeze follows.

**One capture runs at a time**, on a thread of its own. A capture takes
seconds, and the host's broker also carries holds and event polls that
cannot wait behind it; a second package asking while one is under way is
told so (`503`) rather than queued behind it. A capture that never comes
back frees its connection after 25 s.

Captures are request-driven: a package gets a frame because it asked for
one.

### The firmware a package needs

A manifest's `core` names the firmware versions the package works on, and
a package outside that range is refused - at inspect, so the operator is
told before they consent, and at install, so nothing installs behind the
refusal.

The range is judged only when this firmware **has** a version to judge it
by. The host reads `/etc/forgefirm-version`, the file the image build
writes, and takes its first word: a release image writes the release
(`v0.0.6`, the leading `v` being the file's form and not part of the
version), and a **dev image writes its build stamp**, which is no version
at all, and then there is nothing to compare against and the range is not
judged. The answer says which of the two happened, in `core_checked`, so
that nobody is left guessing whether the range was honored.

### The storage quota

Every service has a data directory, and `storage:<MiB>` says how large it
may grow. A service that declares no `storage` gets 16 MiB.

The host measures each running service's data directory every 30 s, by the
blocks the filesystem gave the files rather than by their apparent sizes:
a package that makes one enormous sparse file has taken nothing, and a
package that makes ten thousand small ones has taken more than their
bytes. A symbolic link is counted as a link and never followed, so a link
out of the directory adds nothing.

A service over its quota is **quarantined**: stopped, remembered as
stopped across restarts, and shown with the reason in the panel. The host
does not delete a package's data - that is the operator's, and there are
two ways out: remove the package, which takes its data with it, or clear
the data and enable the package again.

### A package's own settings

A package's data directory is its own and it could keep a file there
without asking anybody. These are the settings that are **not only its own
business**: the ones that must outlive the package being updated or
reinstalled, and the ones something other than the package may read and
change. They are never keys of `forgefirm.conf`, and a package can reach
no key but the ones its own manifest declares.

Two things reach them besides the package: `forgeext settings <id>` at the
console, and the panel's `/ext/settings`, which today serves a package's
own page through the bridge. The panel has no editor of its own for them,
so a package that wants the operator to set something ships a page.

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

The host puts events of its own into the same feed, named `ext.`:

| Event | Data | When |
|---|---|---|
| `ext.will_freeze` | | The armed window opens. A service with `job_time.run` reads it at once; a frozen one reads it when it thaws |
| `ext.thawed` | | The armed window closes |
| `ext.shutdown` | `reason` | Every service is about to be stopped: extensions off, safe mode, or the host stopping. The services are stopped one second later, so that each can read it; the holds do not wait for that second |

At most 32 events come back at a time and the rest waits for the next call.
The host holds the last 64; a reader that falls a whole ring behind is told
how many it lost in `dropped` and handed the oldest still held, never a stale
event as if it were new. `connected` says whether the host has the machine's
stream at that moment.

Each event's `data` is forgectrl's own JSON, passed on as it was written,
within what the ring holds: a name is kept to 31 bytes and `data` to 223.
Neither is the binding limit, because forgectrl writes a whole event into
256 bytes before it leaves the daemon, so nothing it publishes reaches
either. Should one ever be cut, what no longer reads as JSON is passed on
as a **string** rather than dropped, so that one odd event never costs a
package the rest of them.

## The command line

`forgeext` answers every command with one JSON object and exits 0 when
`"ok"` is true. A command it does not know, or one missing an argument, is
the exception: that is a usage error, printed as plain text on standard
error with exit 2. `key-add <name> -` reads the key from standard input.
`forgeext --help` prints the whole of it, the global options (`--root`,
`--fwup`, `--official-key`, `--firmware-key`, `--nft`, `--budget-mib`,
`--core-version`, `--no-reserve`) and `run`'s own included.

| Command | Does |
|---|---|
| `inspect <file.ffx>` | Everything an install checks short of consent and grants, with nothing left behind: the tier, the manifest, what needs a grant, what is new against the installed version, whether it is a downgrade |
| `install <file.ffx> [--grant <capability>]... [--consent-community] [--consent-unverified]` | Installs, or refuses in words |
| `list` | What is installed, with what the kept index says was withdrawn of each |
| `check [<id>]` | The integrity check |
| `remove <id> [--keep-data]` | Removes the package and, unless told otherwise, its data |
| `wipe` | Every package, everything under `data/`, and the owner's keys: [a change of owner](#a-change-of-owner), and nothing an operator reaches |
| `enable <id>`, `disable <id>` | The operator's switch for one package. Disabled, it keeps its files, its data, its grants, and its account, and its service and its hold are gone; enabling it also lets it out of quarantine |
| `hold <id> required\|advisory` | What the package's hold does when the package cannot speak for itself: stand, or drop |
| `dest <id> add\|remove <host>:<port>` | A destination the operator names for a package that asks for them, or takes away ([The operator's destinations](#the-operators-destinations)) |
| `keys`, `key-add <name> <file.pub>`, `key-remove <name>` | The owner's keys. `key-add` parses the file as an Ed25519 public key before it is written |
| `ui <id>` | The package's own page, as a JSON string ([A package's own page](#a-packages-own-page)) |
| `settings <id> [<json>]` | The package's own settings and their schema; with a patch, applied whole or not at all ([A package's own settings](#a-packages-own-settings)) |
| `call <id> GET\|POST <path> [<json>] [--call-dir <dir>] [--cg-parent <dir>]` | One call from the package's page to its own service; `status` and `body`, the service's answer ([A page and its own service](#a-page-and-its-own-service)) |
| `wizard <id> state\|start\|answer\|abort [<json>]` | One step of the package's check on the Setup page, to its service: its status and body ([A package's check on the Setup page](#a-packages-check-on-the-setup-page)) |
| `mcode <n> [<json>]` | `M<n>` of a job, with its words (an object of `P`, `Q`, and `R`), to the service that answers it: its status and body ([A package's M-code](#a-packages-m-code)) |
| `index-verify <file.ffi>` | Verifies the [signed index](#the-signed-index) and keeps it in place of the last, never one older than it; `version` and the number of `packages` |
| `index` | The index this host keeps, judged against this firmware (`usable` and `why` for each version, `offer` for each package), or `null`; and `core_version` and `core_checked` |
| `caps` | The capability list and the API version |
| `net-check` | Whether the image's deny table is loaded |
| `net-allow <uid> [--listen <port>] [--dns] [<host>:<port>]...` | A service's chain in the deny table, as the host installs it when a service starts |
| `net-revoke <uid>` | Takes that chain away again |
| `run` | The extension host, above |
