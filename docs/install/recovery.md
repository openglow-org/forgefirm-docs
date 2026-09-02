---
title: Recovery
---

# Recovery

This page tells you what to do when a slot does not boot, and what the
factory recovery mode is. The eMMC layout and the boot sequence behind it
are in [Boot and storage](../technical/machine/boot-and-storage.md).

## The recovery ladder

Work down the ladder. Each step is more involved than the one before it.

1. **The previous slot.** After a bad update, roll back: select the previous
   slot with the panel's boot selector
   ([Updating](updating.md#boot-selector)) or with `ffboot` (below). No
   flash path ever writes the slot that is running, and a written slot is
   verified before the boot selection moves to it, so the slot you came
   from is intact.
2. **The factory recovery mode**, below.
3. **An SD card.** The bootloader can boot from an SD card that carries the
   release disk image (`forgefirm-image-glowforge.rootfs.wic.gz`). The boot
   selector and `ffboot` list the card as a target
   ([Build](../developers/building.md) for how the image is written).
4. **The serial console.** Log in at the console
   ([Serial access](serial-access.md)). From the factory firmware,
   rerunning the installer recovers a broken ForgeFIRM install: it skips
   the archives it already has and rewrites the ForgeFIRM slot
   ([Install](install.md)).

## `ffboot`

`ffboot` is the boot-slot tool. It is on the `PATH` in ForgeFIRM, and the
installer places it at `/data/ffboot` on the factory firmware:

```sh
ffboot -l     # inventory: what is in each slot, what boots next
ffboot -e2    # select slot 2 for the next boot (-e1 for slot 1)
```

`ffboot -l` inventories every candidate (the eMMC slots, a legacy `p4`, and
an SD card) by a read-only mount: the version file of the system in it, and
the presence of a kernel, plus the current selection in the saved
environment. The output is machine-parsable; the control panel and the
installer reuse the same probe.

A target is probed first. `ffboot` refuses to select a slot that does not
look bootable (no kernel, or no recognizable rootfs); `-f` overrides. The
switch is atomic: one transaction sets all four environment variables
(`mmcdev`, `mmchwpart`, `mmcpart`, `mmcroot`). Rollback from a bad slot is
the same operation: select the previous slot. The eMMC has two 200 MiB rootfs
slots, `mmcblk2p1` (slot 1) and `mmcblk2p2` (slot 2); the saved U-Boot
environment selects the one that boots, and an SD card is a third boot
target.

## The factory recovery mode

The factory recovery is a small system in the eMMC hardware boot
partitions, separate from both rootfs slots. It is never updated in the
field, so every machine runs its as-manufactured recovery. The ForgeFIRM
installer never writes those partitions; it archives them
([Installation](index.md#the-factory-firmware-is-archived-first)). Two paths
lead into recovery mode:

- **The button at power-on.** U-Boot polls the button at power-on for a
  recovery request.
- **A blank or corrupt boot environment.** The compiled-in default
  environment boots recovery, so a machine with no usable saved environment
  lands in recovery mode, not in a brick.
- **A hardware watchdog timeout.** U-Boot arms the SoC watchdog with a 60 s
  timeout before Linux starts. A kernel hard hang lets it reset the SoC,
  and the bootloader reads the timeout flag and boots recovery. Power-cycle
  the machine to boot normally again; the flag clears on a power-on reset.
  The serial console shows nothing from the hang through the recovery boot:
  the purple button is the sign. The recovery image takes the machine's
  network lease and answers ping, with no SSH; about two minutes pass from
  the hang to that point.

The recovery boots the factory's recovery kernel (3.14.28) and device tree
from the boot partitions, and runs the factory setup application: WiFi
setup and an access point, a log export, the firmware version, and a `.fw`
upload. An uploaded archive goes through the factory updater: `fwup` checks
its signature, writes it to slot A, and switches the boot environment to
that slot. The check uses the Glowforge keys, so the factory recovery
installs Glowforge firmware.

## Planned: the recovery refresh

A refreshed recovery is planned. It replaces only the recovery userspace in
the boot partitions: the factory U-Boot, device tree, and recovery kernel
stay in place, and the tool never writes the bootloader region. From the
button hold, the refreshed recovery raises the access point and a web page
with the factory's user experience: upload a `.fw` verified against the
ForgeFIRM **and** the Glowforge keys (so a ForgeFIRM release and a factory
restore can both be installed from it), install from the archive on
`/data`, set the boot target, and export logs. The recovery ladder then
reads: previous slot, button-hold recovery, SD card, serial console.

??? note "Scope of the planned refresh"

    - Only the recovery squashfs in boot0 is replaced (the boot1 `/usr`
      only if needed). Nothing is written below offset 0xC0000 in boot0, so
      U-Boot is physically untouchable by the refresh tool. The factory DTB
      and the 3.14.28 kernel stay.
    - The userspace is a static busybox, `fwup`, a small C web application
      (ulfius), and `hostapd`/`wpa_supplicant`. No Python. It must carry WiFi
      modules matched to kernel 3.14.28; whether they are lifted from the
      factory recovery or rebuilt from Glowforge's published GPL kernel
      source is an open decision.
    - The flash tool archives boot0 and boot1 first (the installer already
      does), unlocks `force_ro`, writes the high regions only, and verifies
      by readback. If both partitions are written, boot1 goes first and
      boot0 last.

    The invariants and contracts behind this are in
    [Install and update](../technical/forgefirm/install-and-update.md).
