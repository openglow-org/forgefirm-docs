---
title: Install and update
---

# Install and update system

ForgeFIRM installs, updates, and restores through the factory's own A/B slot
scheme, with signed `.fw` packages applied by `fwup`. This page is the
design: the decisions, the invariants every flash path obeys, the slot
installer, the legacy migration, the release pipeline, the update manager
in forgectrl, the recovery design, and the contracts.

The operator procedures are on [Install](../../install/install.md),
[Updating](../../install/updating.md),
[Back to the factory firmware](../../install/factory-restore.md),
[Recovery](../../install/recovery.md), and
[Legacy migration](../../install/legacy-migration.md). The factory eMMC
layout, the boot0 and boot1 maps, the U-Boot environment, the factory
recovery, and the `.fw` format are on
[Boot and storage](../machine/boot-and-storage.md). The release procedure
is on [Release flow](../../developers/release-flow.md); the acceptance gate
is on [Acceptance](../../developers/acceptance.md).

## Design decisions

- **Factory partition scheme, unmodified.** ForgeFIRM lives in the two
  200 MiB rootfs slots (`mmcblk2p1` and `p2`); `/data` (p3) keeps its full
  factory size. No repartitioning at install, ever.
- **A replacement, not a dual boot.** ForgeFIRM replaces the factory
  firmware; the way back is a factory restore from the archive. The slot the
  factory firmware ran from is reused by the first ForgeFIRM update, so the
  two are never operated side by side, and the factory updater's behavior
  toward foreign slot contents is irrelevant.
- **fwup is the universal package and apply format** (the factory's own
  mechanism). ForgeFIRM upgrades, factory restore, and provisioning all use
  signed `.fw` archives applied to the inactive slot, followed by a U-Boot
  env flip: exactly the factory update flow.
- **Factory firmware is archived to `/data` before any factory slot is
  overwritten.** Restore-to-factory never depends on Glowforge's servers;
  the cloud path (`GET /update/current`, implemented in gfutilities) is the
  optional "restore to *latest*" upgrade.
- **Release artifacts are built and signed locally** and uploaded as GitHub
  releases. The Ed25519 private key never leaves the build host, so GitHub
  is untrusted hosting: machines verify signatures before applying. CI does
  compile checks only, never artifacts.
- **Reinstalling ForgeFIRM from factory = run the installer again.** The
  planned recovery refresh subsumes this.
- **The recovery refresh is squashfs-only** in its first version: the
  factory U-Boot, DTB, and the 3.14.28 recovery kernel stay in place; only
  the recovery userspace is replaced ([Recovery](#recovery)).

## Invariants (every flash path)

1. Never write the active (running) slot.
2. Machine idle; one flash operation at a time (lock file); no flash or
   reboot while a job runs.
3. Archive factory content before the write that would destroy the last
   copy of it (rootfs slots; boot0 and boot1 before a recovery refresh).
4. Env flips are atomic: one `fw_setenv -s` transaction setting all four of
   `mmcdev`, `mmchwpart`, `mmcpart`, `mmcroot`.
5. Automatic paths (the release updater, the cloud restore) require a valid
   signature, ForgeFIRM's or Glowforge's respectively. Manual uploads may
   be unsigned behind an explicit "unsigned dev image" warning.
6. The image must fit the 200 MiB slot; the build fails past the size gate
   rather than producing an unflashable release.
7. Boot selection refuses targets that fail the content probe (no kernel,
   no recognizable rootfs).
8. Verify a written slot (fwup on-the-fly hashes, or an explicit readback
   or mount check for raw writes) before flipping boot to it.

## Slot-agnostic images and ffboot

One image boots unmodified from p1, p2, or SD, steered only by the saved
U-Boot environment: `mmcargs` takes `root=${mmcroot}` from the env, and
`/boot/uEnv.txt` carries only entries that are not per-location (`fdt_file`
and the like). No flash path mounts the slot to edit it.

`ffboot` performs the atomic env flip (invariant 4) and the slot inventory:
`ffboot -l` lists every candidate (eMMC p1 and p2, legacy p4, SD) by
read-only mount, reading the factory `/etc/version` or
`/etc/forgefirm-version` and the kernel presence, plus the current env
selection, in machine-parsable output. The panel and the installer both
reuse this probe. `ffboot` also ships `fw_env.config`. The operator's use of
it is on [Recovery](../../install/recovery.md#ffboot).

## The slot installer

`install-forgefirm.sh` is a single-stage script run from factory firmware
(the procedure is on [Install](../../install/install.md)):

1. **Sanity.** The factory 3-partition layout, both slots 200 MiB, the
   active slot detected (`rdev`), enough `/data` space.
2. **Archive.** Every factory slot version not already archived:
   `dd | gzip` to `/data/forgefirm/archive/factory-rootfs-<ver>.img.gz`
   with a manifest line (slot, version, date, md5); also boot0 and boot1
   (32 MiB) into the archive, ahead of the recovery refresh. With both
   slots archived, any later overwrite needs no second archive step.
3. **Fetch** `forgefirm.fw` from GitHub releases (fixed asset name; the
   `releases/latest/download/` URL needs one, and the version lives in the
   fwup metadata and the release tag), or take a local file argument for
   offline and dev installs. Verify the signature against the ForgeFIRM
   public key embedded in the installer (raw 32-byte form for the factory's
   fwup).
4. **Apply** to the **inactive** slot (fwup plus the ForgeFIRM public key).
   The booted factory install is not written; the first ForgeFIRM update
   reuses its slot.
5. **Atomic env flip** (the flip logic is embedded, because the factory
   rootfs has no ffboot), then reboot.

No repartitioning, no `/data` backup and restore, no second stage. `ffboot`
returns the machine to the intact factory slot, and `/data` (factory state,
credentials, logs) is untouched.

## Legacy p4 migration

`slotmigrate` is a boot-time init script that runs before `/data` mounts. It
is gated on: booted from `mmcblk2p1` or `p2` (never SD, never p4) AND the
legacy geometry present (p4 exists, or p3 ends short of the disk). Actions:
delete p4, extend p3's end to the disk (its start unchanged), `resize2fs`.
It is idempotent and power-safe: every step is keyed off actual disk state
and re-runnable after interruption.

A machine on the legacy p4 layout reaches the slot scheme by running the
installer from its running ForgeFIRM (the same flow as above; with both
factory slots intact, the newer is archived and the older overwritten), and
the boot-time check reclaims p4 into p3 on the first slot boot. `/data`
contents stay intact and grow to full size; a further boot is a no-op. The
operator procedure is on
[Legacy migration](../../install/legacy-migration.md).

## The release pipeline

`scripts/release.sh` runs on the build host: gates, kas build, pack `.fw`,
sign, `sha256sums.txt`, staged assets, and the `gh release create` command
(`--publish` runs it where gh is authenticated). The gates are: a clean
tree, the version single-source, rootfs-vs-slot size (warn at 170 MiB or
more, fail at 195 MiB or more, under bitbake's own hard cap), the
**installer-embedded public key must match the signing key**, factory-era
fwup (0.14.2) verification of the packed archive, and the **release
acceptance gate**: `releases/v<version>/acceptance.json` (exported by
forgetest on the bench) must authorize the built rootfs. The gate recomputes
every catalog test's domain fingerprint from `/etc/forgefirm-manifest.json`
inside the release ext4. The artifact is attached to the GitHub release. The
release build also writes the source of every recipe of the image, and the
pipeline attaches it as `forgefirm-source-v<version>.tar.gz`; a recipe whose
license makes source necessary and that has no source stops the release. The
procedure and the variables are on
[Release flow](../../developers/release-flow.md); the gate's contract is on
[Acceptance](../../developers/acceptance.md).

One version source: `FORGEFIRM_RELEASE` = git tag = `/etc/forgefirm-version`
= `.fw` meta-version; the script enforces agreement. A component's version
is its pin file's `PV` (it moves with every `SRCREV` bump); version strings
inside the component sources are informational.

`release.sh --dev` packs `forgefirm-dev.fw` from the **dev image** (forgetest
and the bench tools included), signed with the dev key so it is never an
unsigned file in transit. The machine holds the release key and the Glowforge
keyring only, so a dev archive classifies as unsigned there and takes the
operator-present path: the unsigned confirmation with the machine button
held. No gate runs on it.

**The dev image is SD-only.** forgetest and the bench tools put the dev
rootfs at about 368 MiB, well past the 200 MiB slot, so it is never installed
into one: it goes on an SD card, which the boot selector carries as a
first-class location. Write `forgefirm-image-dev-glowforge.rootfs.wic.gz` to
the card, or point `fwup` at the card rather than a slot. The slot size gate
in `release.sh` therefore applies to the release rootfs alone.

**Cloud-mode compatibility baseline.** The cloud client's connect-time probe
records `{latest_gf_version, tested_against_gf}` to
`/data/forgefirm/gf-latest.json`, and forgectrl's panel warns when the live
Glowforge service has moved past the tested version (cloud mode may break).
`tested_against_gf` is the cloud client's configured firmware version
(`FACTORY_FIRMWARE.FW_VERSION`, the same value it advertises to the
service). It is **not** release metadata: neither `release.sh` nor the `.fw`
meta carries such a field ([Cloud mode](cloud-mode.md)).

GitHub Actions run per-push compile checks for grblHAL-glowforge and
forgectrl (minutes, no Yocto), and an optional `workflow_dispatch`
cold-Yocto reproducibility build whose only product is a checksum.

## The update manager

The endpoints are in forgectrl's `src/update.c`, driven from the panel's
System tab. Trust anchors live in `/etc/forgefirm/keys` (the
`forgefirm-keys` recipe: the release public key plus the Glowforge keyring).
The release check reads the latest published release from the GitHub
releases API (`GET /repos/openglow-org/forgefirm/releases/latest`, one
unauthenticated read, allowed 60 times an hour per address): the tag, the
notes, the assets and their sizes. It never requests the firmware file's
URL, which GitHub counts as a download. The daemon checks two minutes after
it starts, then every 24 hours; a check that got no answer is retried after
an hour. The download requests
`.../releases/download/<tag>/forgefirm.fw` once, for the tag the check
found. `new` in the check's answer is the version order of
`v<major>.<minor>.<patch>` tags; an installed version that is not one (a
development build's stamp) is older than every release. The dismissed
release is the settings key `update_dismissed`.

All slot writes run on one background job (polled through
`GET /update/status`), take the installer's `/data/forgefirm/update.lock`,
require idle plus no diagnostic, refuse the booted root slot, verify the
signature before writing, and re-verify the written filesystem.

| Route | Purpose |
|---|---|
| `GET /slots` | The slot inventory (the ffboot probe) |
| `POST /boot` | Set the boot target; probe-gated, refuses unprobeable targets |
| `GET /update/release` | The last answer of the release check: `available`, `version`, `current`, `new`, `published`, `bytes`, `notes`, `detail`, `checked`, `dismissed` |
| `POST /update/check` | Check the latest release now; answers as `GET /update/release` |
| `POST /update/dismiss?version=<tag>` | Dismiss the alert for that release (an empty version undoes it) |
| `POST /update/download` | Download the `.fw` to `/data` |
| `POST /update/apply` | Verify and apply to the inactive slot, verify the written slot |
| `POST /update/upload` | Streamed multipart upload to `/data` |
| `GET /update/status` | The background job's state |
| `POST /restore/factory` | Factory restore from the archive (md5 checked); `source=cloud` answers 501 until it ships |
| `POST /restore/factory-return?confirm=1` | The setup's factory-return exit (below) |
| `POST /system/reboot` | Reboot |

Every state-changing call is behind forgectrl's auth layer (a login
session, the panel token, and origin checks); unsigned installs
additionally require the physical button held
([forgectrl](forgectrl.md#http-api)).

**The factory return.** Every screen of the first-run setup carries a
footer link, "Go back to the factory firmware"
([Setup](../../usage/setup.md#go-back-to-the-factory-firmware)).
After a confirmation, `POST /restore/factory-return?confirm=1` runs. It
restores the archived factory image into the other slot, when that slot no
longer holds one. Then it moves the boot selection and reboots. It runs as
the update manager's background job, under the same lock and interlocks.
Reinstalling ForgeFIRM afterward is the installer again from the console.

**What `/data/forgefirm/` holds.** Beside the archive and the update lock:

- the setup record (`setup.json`);
- the sheet salt (`sheet.salt`);
- the TLS key and certificate;
- the account record (`users`) and the home directories (`home/`);
- the panel token (`panel.token`);
- the settings store of the GRBL controller (`EEPROM-glowforge.DAT`, the
  `$` settings);
- the sshd host keys (`ssh/`), the boot timestamp (`timestamp`), and the
  random seed (`random-seed`): the state a read-only rootfs cannot hold
  ([Image and BSP](image-and-bsp.md#the-read-only-root-filesystem)).

They live on `/data`, outside both slots, so every update and the factory
return leave them in place.

Functions of the panel page:

- **Inventory:** slot contents (the probe), current and next boot
  selection, archive presence and version.
- **Update check** against the GitHub releases API (daily, plus a manual
  button; offline-tolerant), with an alert on every tab for a newer
  release, dismissable per release.
- **Apply release:** one dialog with the release notes and one button:
  download the `.fw` to `/data`, verify the signature, apply to the
  inactive slot, verify, select that slot for the next boot, and restart;
  the page reloads when the machine is back.
- **Upload:** streamed multipart to `/data` through the framework's
  upload sink; the framework's own copy of a request body is capped at
  64 KiB. Accepts a `.fw` (verified; warns if unsigned) and nothing else.
- **Boot selector** including SD, with warnings, most prominently on
  switch-to-factory: the factory updater may auto-update and overwrite the
  other slot. Refuses unprobeable targets.
- **Factory restore:** from the `/data` archive (offline, md5 checked), to
  the inactive slot, then flip. A restore from the cloud latest and a
  cleanup of ForgeFIRM's files in `/data` are open items.
- Interlocks throughout: idle-only, the update lock, never the active slot,
  never the slot already selected for the next boot (a write there has no
  revert behind it), and rollback = flip back to the previous slot.

The operator's view is on [Updating](../../install/updating.md).

## Recovery

The recovery ladder is: the previous slot, then the factory button-hold
recovery, then an SD card, then the serial console
([Recovery](../../install/recovery.md)). The factory recovery userspace in
boot0 is what the button-hold path runs
([Boot and storage](../machine/boot-and-storage.md)).

A **recovery refresh** is planned. Its design:

- Replace only the boot0 recovery squashfs (boot1 `/usr` only if needed).
  Never write below offset 0xC0000 in boot0; U-Boot is physically
  untouchable by the refresh tool. The factory DTB and kernel 3.14.28 stay.
- Userspace: static busybox, fwup, a small C web app (ulfius), hostapd and
  wpa_supplicant. No Python. It must carry 3.14.28-matched WiFi modules
  (an open decision: lift from the factory recovery, or rebuild from
  Glowforge's published GPL kernel source).
- Functions: button-hold starts an AP and a web UI (the factory UX): upload
  a `.fw` (verified against the ForgeFIRM **and** the Glowforge public keys,
  so either firmware is installable), install from the `/data` archive, set
  the boot target, export logs.
- Flash tool: boot0 and boot1 archived first (the installer already does),
  `force_ro` unlock, write high regions only, readback verify; if both
  partitions are written, boot1 first, boot0 last.
- First flashes are bench-gated on an attached serial console.
- A `complete` full-provisioning task joins the `.fw` with this work.

The refresh is independent of the update manager and builds on the stable
slot scheme.

## Contracts

- **Artifacts** (consumers: the installer, the update manager, recovery):
  `forgefirm.fw` (fixed asset name; signed; the version in the fwup
  metadata = the release tag `v<semver>`; tasks `upgrade.a` and
  `upgrade.b`, `complete` with the recovery refresh), `sha256sums.txt`,
  `forgefirm-image-glowforge.rootfs.wic.gz` (SD burns).
- **Env:** SD = `0/0/1//dev/mmcblk1p1`; slot N = `1/0/N//dev/mmcblk2pN`
  (`mmcdev/mmchwpart/mmcpart/mmcroot`, always one transaction).
- **Archive layout:** `/data/forgefirm/archive/` holds
  `factory-rootfs-<ver>.img.gz`, `recovery-boot0.img.gz`,
  `recovery-boot1.img.gz`, and `manifest`
  (slot versions, dates, checksums).

## Decisions

- `uEnv.txt` keeps its `mmcargs` override with `root=${mmcroot}`; the image
  is slot-agnostic, steered only by the saved env.
- Modern-fwup-packed signed archives apply with the factory 0.14.2 binary
  (raw 32-byte public key form); no shipped fwup is needed on the factory
  side.
- Size gates live in two layers: bitbake fails past the 200 MiB slot;
  `release.sh` warns at 170 MiB and fails at 195 MiB.
- Dev archives (`release.sh --dev`) carry the dev key's signature, which no
  machine holds: they take the button-held unsigned path. The dev rootfs is
  too large for a slot, so it runs from an SD card and no size gate applies
  to it.
- Production signing key: held offline by the operator (never in the repo,
  CI, or cloud-synced plaintext), public key embedded in the installer.
  Production-signed archives verify with fwup 1.16 and the factory's 0.14.2
  (raw public key form); a dev-signed archive verifies against no key the
  machine has and takes the button-held path. Custody optimizes
  against compromise over loss: loss means users re-run a fresh installer;
  compromise means attacker-signed firmware on fielded machines.
- U-Boot bootcount and auto-revert are out of scope; the recovery ladder
  covers bad flips.

## Open items

- Recovery kernel modules: carried from the factory image, or rebuilt from
  the GPL source (a recovery-refresh decision).
