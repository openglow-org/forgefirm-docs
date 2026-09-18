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
[`forgefirm` repository](https://github.com/openglow-org/forgefirm/releases).
Its assets have fixed names, and the installer and the update manager
download them by those names:

| Asset | Contents |
|---|---|
| `forgefirm.fw` | The signed release archive, in the `fwup` format the factory uses. The version is in the archive's metadata and equals the release tag `v<semver>`. It carries the tasks `upgrade.a` and `upgrade.b`, one per slot. |
| `sha256sums.txt` | Checksums of the assets. |
| `forgefirm-image-glowforge.rootfs.wic.gz` | The same image as a disk image for an SD card. |
| `acceptance.json`, `acceptance.md` | The release acceptance record that authorized the rootfs ([Acceptance](../developers/acceptance.md)). |
| `forgefirm-source-v<semver>.tar.gz` | The source of the software in the image: the upstream source of each recipe, the patches, the recipes, and the license manifests. The machine does not download it ([Release flow](../developers/release-flow.md), "The source bundle"). |

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

### Installing your own build

ForgeFIRM is free software, and the machine will run a build you made
yourself. Nothing in the boot path forbids it: the boot loader is the
factory U-Boot and verifies no signature, the kernel loads unsigned
modules, and the signature check on a firmware archive is a ForgeFIRM
policy that an operator standing at the machine can waive. There are two
ways in.

**From the control panel.** Upload your `.fw` on the System tab. An
archive that no key on the machine verifies is classified unsigned: the
panel says so, and the install proceeds when you **hold the machine
button** while you confirm it. Physical presence takes the place of the
signature; no key is needed.

**From a root shell.** The serial console gives a root shell with no
password ([Serial access](serial-access/index.md)), and `fwup` is stock
upstream. Write your archive to the slot the machine is not running from,
then select it:

```
fwup -a -d /dev/mmcblk2p2 -i my-build.fw -t upgrade.b
ffboot b
```

`upgrade.a` writes slot A (`/dev/mmcblk2p1`) and `upgrade.b` writes slot B
(`/dev/mmcblk2p2`); `ffboot -l` shows which one is running
([Recovery](recovery.md#ffboot)). Or write
`forgefirm-image-glowforge.rootfs.wic.gz` to an SD card and boot from that.

**The trust anchor is yours to replace.** `/etc/forgefirm/keys` holds
public keys only, as ordinary world-readable files. Put your own public
key in `forgefirm-release.pub` and the automatic paths verify against your
key instead: sign your builds with `fwup -S` and they install with no
button held.

Building the image is documented in
[Building](../developers/building.md), and every release carries the
source of everything in it
([Release flow](../developers/release-flow.md), "The source bundle").

## The update manager

The **System** tab of the control panel is the update manager. Every
function runs on one background job, and the tab polls its status. Every
slot write takes the update lock (`/data/forgefirm/update.lock`, shared with
the installer), requires the machine idle with no diagnostic running,
refuses the slot the machine booted from, verifies the signature before
writing, and re-verifies the written filesystem afterward. Every
state-changing action is behind the panel's authentication (a login session
and origin checks; [The control panel](../usage/control-panel.md#access)).

### Inventory

The slot contents, the current and next boot selection, and the presence
and version of the factory archive, from the same probe that `ffboot -l`
uses ([Recovery](recovery.md#ffboot)).

### Update check

The machine checks for a new release once a day, and when you press
**Check now**. The check asks the GitHub releases API for the latest
published release (one unauthenticated read, with no token; it does not
request the firmware file, so GitHub's download counter counts installs
only). The check is offline-tolerant: a machine without a route to the API
keeps its last answer and tries again an hour later.

A release is newer than the installed version by version order
(`v<major>.<minor>.<patch>`). A development build counts as older than
every release. When the latest release is newer, the panel shows an alert
on every tab. The alert stays until you install the release or dismiss it;
a dismissal is for that release only, and a later release raises the alert
again. **Show the alert again** on the System tab undoes a dismissal.

### Apply a release

The alert and the **Install** button on the System tab open the release
dialog: the installed version, the release, its date and size, and its
release notes. **Install and restart** runs the whole update:

1. Download `forgefirm.fw` to `/data`.
2. Verify its signature against the release key.
3. Write it to the firmware slot that is not running, and verify the
   written slot.
4. Select that slot for the next boot.
5. Restart the machine.

The dialog shows each step and a progress bar. Do not switch the machine
off while it runs. When the machine is back, the page reloads on its own so
the browser loads the panel the new firmware serves. The firmware that was
running stays in its slot: the boot selector can go back to it
([Recovery](recovery.md)). The dialog names the reason when a step fails,
and nothing after the failed step runs.

### Upload

An upload streams to `/data`. The manager accepts a `.fw` archive
(verified, with a warning if it is unsigned) and nothing else. The
development image does not come this way: it is larger than a slot and runs
from an SD card instead
([Install and update](../technical/forgefirm/install-and-update.md)).

### Boot selector

The boot selector chooses the next boot among the slots and an SD card,
with warnings, and refuses targets that fail the probe. It is the rollback
lever after a bad update: select the previous slot
([Recovery](recovery.md)). It is not the way back to the factory firmware;
that is a factory restore ([Back to the factory firmware](factory-restore.md)).

### Factory restore

A restore returns the machine to the factory firmware without a shell, from
**the archive on `/data`**, offline. The installer writes it before it
overwrites anything
([Installation](index.md#the-factory-firmware-is-archived-first)). The
manager checks the archive's md5 before it writes. The firmware goes to the
inactive slot, and the boot selection then switches to it. ForgeFIRM's own
files under `/data/forgefirm/` stay; a restore from the Glowforge service is
planned, not shipped.

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
    | `GET /update/release` | The last answer of the release check, with the installed version, whether the release is newer, and whether its alert is dismissed. |
    | `POST /update/check` | Check for a release now; the answer is the same as `GET /update/release`. |
    | `POST /update/dismiss?version=<tag>` | Dismiss the alert for that release; an empty version undoes it. |
    | `POST /update/download` | Download a release archive to `/data`. |
    | `POST /update/apply` | Apply a downloaded archive to the inactive slot. |
    | `POST /update/upload` | Upload an archive or an image. |
    | `GET /update/status` | The state of the background job. |
    | `POST /restore/factory` | Factory restore from the archive or the service. |
    | `POST /system/reboot` | Reboot. |

    The rest of the daemon's HTTP surface is in
    [forgectrl](../technical/forgefirm/forgectrl.md).
