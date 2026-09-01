---
title: Legacy migration
---

# Legacy migration

Machines installed with the earlier, partition-carving ForgeFIRM installer
have a legacy layout: the `/data` partition shrunk, and a fourth partition
(`p4`) holding ForgeFIRM. This page tells you how such a machine reaches the
factory slot scheme, and what the migration does.

## The procedure

Machines with the legacy dual-partition install migrate automatically:

1. Switch to the factory firmware and run the installer from there
   ([Install](install.md)). Both factory slots are intact on a legacy
   machine. The installer archives them and writes ForgeFIRM to the inactive
   slot, exactly as on a fresh install.
2. On ForgeFIRM's first boot from its new slot, the legacy partition is
   reclaimed, and `/data` grows back to the full factory size.

`/data` contents are preserved throughout.

## What the migration does

The reclaim is a boot-time step that runs before `/data` mounts. It runs
only when both conditions hold:

- the machine booted from an eMMC rootfs slot (`mmcblk2p1` or `p2`), never
  from an SD card and never from `p4`; and
- the legacy geometry is present: `p4` exists, or `p3` ends short of the
  disk.

It then deletes `p4`, extends the end of `p3` to the end of the disk (the
start is unchanged), and grows the filesystem with `resize2fs`. Every step
is keyed off the actual disk state, so the migration is idempotent and
power-safe: interrupted, it runs again on the next boot and finishes, and on
a migrated machine a reboot is a no-op. The result is the byte-exact
factory geometry ([Boot and storage](../technical/machine/boot-and-storage.md)).
