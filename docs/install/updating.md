---
title: Updating
---

# Updating

ForgeFIRM updates the way the factory firmware does: a signed archive is
applied to the inactive slot, verified, and then selected for the next
boot. This page tells you what a release is and how the update manager in
the control panel applies one.

## What a release is

A ForgeFIRM release is a GitHub release in the
[`forgefirm` repository](https://github.com/ScottW514/forgefirm/releases).
Its assets have fixed names, and the installer and the update manager
download them by those names:

| Asset | Contents |
|---|---|
| `forgefirm.fw` | The signed release archive, in the `fwup` format the factory uses. The version is in the archive's metadata and equals the release tag `v<semver>`. It carries the tasks `upgrade.a` and `upgrade.b`, one per slot. |
| `sha256sums.txt` | Checksums of the assets. |
| `forgefirm-image-glowforge.rootfs.wic.gz` | The same image as a disk image for an SD card. |
| `acceptance.json`, `acceptance.md` | The release acceptance record that authorized the rootfs ([Acceptance](../developers/acceptance.md)). |

The archive fits the 200 MiB slot. The build fails past the size gate rather
than producing an unflashable release.

### The signature

Release artifacts are built and signed by the maintainer, and uploaded to
GitHub. The Ed25519 signing key is held offline and never leaves the
maintainer. GitHub is untrusted hosting, so a machine verifies the signature
before it applies anything. The public key is embedded in the installer and
shipped in the image at `/etc/forgefirm/keys`, next to the Glowforge keyring
that a factory restore verifies against. Automatic paths (the release
updater and the cloud restore) require a valid signature: ForgeFIRM's or
Glowforge's, respectively.

Development archives (`forgefirm-dev.fw`) are signed with a separate dev
key, never left unsigned. A machine with the release key rejects a
dev-signed archive. A manual upload may be unsigned, behind an explicit
"unsigned dev image" warning and with the physical button held.

The release pipeline, its gates, and the version contract are in
[Release flow](../developers/release-flow.md).

## The update manager

The **System** tab of the control panel is the update manager. Every
function runs on one background job, and the tab polls its status. Every
slot write takes the update lock (`/data/forgefirm/update.lock`, shared with
the installer), requires the machine idle with no diagnostic running,
refuses the slot the machine booted from, verifies the signature before
writing, and re-verifies the written filesystem afterward. Every
state-changing action is behind the panel's authentication (the panel token
and origin checks).

### Inventory

The slot contents, the current and next boot selection, and the presence
and version of the factory archive, from the same probe that `ffboot -l`
uses ([Recovery](recovery.md#ffboot)).

### Update check

A manual **check** button, and a periodic check while the machine is idle.
The check is offline-tolerant. The release version resolves from the
fixed-name asset redirect on GitHub
(`.../releases/latest/download/forgefirm.fw` redirects to
`.../download/v<ver>/...`), so no GitHub API call and no rate limit is
involved.

### Apply a release

The manager downloads `forgefirm.fw` to `/data`, verifies its signature,
applies it to the inactive slot, and verifies the written slot. The boot
selection changes **only on your explicit confirmation**, and the manager
then prompts for a reboot.

### Upload

An upload streams to `/data`; it is never buffered in RAM. The manager
accepts a `.fw` (verified, with a warning if it is unsigned) and, for
development, a `.wic.gz` or `.ext4.gz` (with size and superblock sanity
checks).

### Boot selector

The boot selector chooses the next boot among the slots and an SD card,
with warnings, and refuses targets that fail the probe. It is the rollback
lever after a bad update: select the previous slot
([Recovery](recovery.md)). It is not the way back to the factory firmware;
that is a factory restore ([Back to the factory firmware](factory-restore.md)).

### Factory restore

A restore returns the machine to the factory firmware without a shell, from
one of two sources:

- **The archive on `/data`**, offline. The installer writes it before it
  overwrites anything
  ([Installation](index.md#the-factory-firmware-is-archived-first)). The
  manager checks the archive's md5 before it writes.
- **The latest factory firmware from the Glowforge service.** The machine
  authenticates as a Glowforge device, downloads the Glowforge-signed `.fw`,
  and verifies it with the Glowforge public keys.

Either way the firmware goes to the inactive slot, and the boot selection
then switches to it. An optional cleanup removes ForgeFIRM's residue in
`/data` for a true factory condition.

### Reboot

A reboot button, for after an update or a slot switch.

## Cloud-mode compatibility warning

The cloud client records, at connect time, the firmware version that the
Glowforge service publishes and the version ForgeFIRM is tested against
(the firmware version the cloud client advertises to the service), in
`/data/forgefirm/gf-latest.json`. The panel warns when the live service
has moved past the tested version: cloud mode may break until a ForgeFIRM
release catches up ([Cloud mode](../usage/cloud-mode.md)).

??? note "The HTTP routes behind the tab"

    | Route | Function |
    |---|---|
    | `GET /slots` | The slot inventory. |
    | `POST /boot` | Select the next boot target (probe-gated). |
    | `POST /update/check` | Check for a release. |
    | `POST /update/download` | Download a release archive to `/data`. |
    | `POST /update/apply` | Apply a downloaded archive to the inactive slot. |
    | `POST /update/upload` | Upload an archive or an image. |
    | `GET /update/status` | The state of the background job. |
    | `POST /restore/factory` | Factory restore from the archive or the service. |
    | `POST /system/reboot` | Reboot. |

    The rest of the daemon's HTTP surface is in
    [forgectrl](../technical/forgefirm/forgectrl.md).
