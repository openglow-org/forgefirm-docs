---
title: Install
---

# Install

This page is the install procedure: one stage, run at the factory console,
with no intermediate reboots. Read [Installation](index.md) for what you
need, and [Regulatory and legal](index.md#regulatory-and-legal) before you begin.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read
    [Safety](../safety/index.md) before you install, and before you run a
    job.

!!! warning "Beta"

    ForgeFIRM is in beta: expect problems, and expect frequent updates.
    Upgrade whenever a newer release is available ([Updating](updating.md)).

## Run the installer

Log in at the factory console ([Serial access](serial-access.md); login
`root`, no password) and run:

```sh
curl -fL https://raw.githubusercontent.com/ScottW514/forgefirm/master/scripts/install-forgefirm.sh --output /tmp/install-forgefirm.sh
sh /tmp/install-forgefirm.sh
```

For an offline install, place a `forgefirm.fw` on `/data` beforehand and
pass its path:

```sh
sh /tmp/install-forgefirm.sh /data/forgefirm.fw
```

## What the installer does

One stage, no intermediate reboots. The installer:

1. Confirms it is running on factory firmware, from a factory eMMC slot,
   with the factory partition layout.
2. Stops the Glowforge services (including the updater).
3. Archives every factory slot version and the recovery boot partitions to
   `/data/forgefirm/archive/` (manifest with checksums; a few minutes each,
   with progress).
4. Downloads the latest `forgefirm.fw` release (or uses the local file you
   passed) and **verifies its signature** before touching anything.
5. Writes ForgeFIRM to the inactive slot with the factory's own `fwup`,
   then verifies the written filesystem.
6. Installs `/data/ffboot` (the boot-slot tool) and switches the saved
   U-Boot environment to the new slot. The switch is read-back verified; on
   any failure the machine keeps booting factory firmware.
7. Reboots into ForgeFIRM.

## After the first boot

Login is `root`, no password (also via SSH). Change it.

The machine boots into ForgeFIRM. The factory firmware is in the archive on
`/data` ([Back to the factory firmware](factory-restore.md)). The control panel
is at the machine's address on HTTP port 8080
([Control panel](../usage/control-panel.md)). Routine updates do not use the
installer; they run from the panel's System tab ([Updating](updating.md)).
Rerunning the installer is only for recovering a broken ForgeFIRM install
([Recovery](recovery.md)).
