---
title: Boot and storage
---

# Boot and storage

This page describes the factory eMMC layout, the boot partitions, U-Boot and
its saved environment, the factory A/B rootfs slots, the factory recovery mode,
and the factory `.fw` package format, as machine facts. How ForgeFIRM uses them
is on [Install and update internals](../forgefirm/install-and-update.md); the
operator procedures are on [Updating](../../install/updating.md),
[Back to the factory firmware](../../install/factory-restore.md), and
[Recovery](../../install/recovery.md).

## The eMMC

The eMMC (`mmcblk2`) has a 3.6 GiB user area plus two 16 MiB hardware boot
partitions (`mmcblk2boot0`, `mmcblk2boot1`).

The factory user-area MBR (per the factory `.fw` manifest):

| Partition | Content | Geometry |
|---|---|---|
| p1 | rootfs slot A | 200 MiB at block 8192 |
| p2 | rootfs slot B | 200 MiB at block 417792 |
| p3 | `/data` | from block 827392 to the end of the disk |

`/data` holds the machine's settings, credentials and logs. The factory
`rootfs.ext4` is 65 MiB; the ForgeFIRM release rootfs uses about 89 MiB, so it
fits a 200 MiB slot with headroom. ForgeFIRM never repartitions: it lives in
the two rootfs slots, and `/data` keeps its full factory size.

A watchdog-timeout reboot is special: U-Boot arms WDOG1 (60 s) before Linux
starts, and after a timeout reset it boots the factory recovery instead of
the selected slot, until the next power-on reset
([Recovery](../../install/recovery.md#the-factory-recovery-mode)).

The watchdog is armed in hardware, not by any process: WDOG1's own control
register reads `0x771f` (enabled, with the external reset output on, a 60 s
period), the kernel's `imx2_wdt` driver adopts the running watchdog when it
probes, and the kernel core feeds it because nothing in userspace ever opens
`/dev/watchdog`. Its sysfs `state` therefore reads `inactive`, which says only
that no process holds the device; the control register is the proof that it is
armed. It is a boot and system watchdog and never a laser-safety mechanism
([forgectrl](../forgefirm/forgectrl.md#watchdog-scope)).

## Machine identity

Every machine carries an unchangeable identity in the SoC's one-time
programmable fuses, and the factory firmware, the Glowforge service and
ForgeFIRM all use it:

- **The serial number** is `HW_OCOTP_MAC0`.
- **The hostname** is that serial rendered in **base 23**, over the alphabet
  `BCDFGHJKMQRTVWXY2346789`, formatted `XXX-YYY`. It is the name on the
  factory label, verified against the fuses, and ForgeFIRM's own derivation is
  checked against the factory's over 200,000 random serials.
- **The cloud password** is `HW_OCOTP_SRK0` through `SRK7`, the eight words
  concatenated as 8-digit hexadecimal.

They are readable at `/sys/fsl_otp/` ([Cloud mode](../forgefirm/cloud-mode.md)).
The hostname is what the control panel's header shows, whatever cloud identity
override is set, and none of the three can be rotated: a fuse is burned once.
That is why ForgeFIRM's log export masks all three by default
([Logging](../forgefirm/logging.md)) and why reading them back through the
panel needs the physical button held as well as a login.

## U-Boot and the saved environment

**U-Boot lives in boot0** at 1 KiB (IMX IVT header), not in the user area. Any
boot0 rewrite below offset 0xC0000 risks the bootloader.

**The bootloader that runs is the factory's**: U-Boot 2015.07, built
2018-02-20, read back from the device. ForgeFIRM never replaces it. The BSP
carries a `u-boot_2020.01` recipe and the build deploys its binary, but that
is a source reference only: no install or boot path uses it, and none should
([Image and BSP](../forgefirm/image-and-bsp.md)).

**The saved environment** is in the user area at 0x80000, with a redundant
copy at 0x82000 (boot0's own 0x80000 region is zeros). Slot selection is the
four variables `mmcdev`, `mmchwpart`, `mmcpart` and `mmcroot`; U-Boot's
`mmcargs` takes `root=${mmcroot}` from the environment. The values are:

| Boot device | `mmcdev` / `mmchwpart` / `mmcpart` / `mmcroot` |
|---|---|
| SD card | `0` / `0` / `1` / `/dev/mmcblk1p1` |
| eMMC slot N | `1` / `0` / `N` / `/dev/mmcblk2pN` |

**The default (compiled-in) environment boots recovery**: `mmcdev=1
mmchwpart=1 boot_recovery=yes`. A blank or corrupt environment lands in
recovery mode, not a brick.

`bootcmd`: select the mmc device and hardware partition → load and import
`/boot/uEnv.txt` from the selected partition → if `boot_recovery=yes`, boot
the kernel and DTB from raw boot0 sectors, else load `/boot/zImage` from the
slot's rootfs. U-Boot polls the button at power-on for a recovery request.

## The boot partitions and recovery mode

**boot0 map**: MBR / U-Boot at 1 KiB / zeros at 0x80000 / recovery DTB at
0xC0000 (`fdt_dev_addr=0x600`, 64 KiB slot) / recovery zImage at 0x100000
(`image_dev_addr=0x800`, 5 MiB slot, kernel 3.14.28) / recovery squashfs =
`boot0p1` at 6 MiB (10 MiB slot).

**boot1 map**: MBR / squashfs at 1 KiB = `boot1p1`, mounted as the recovery
`/usr` (the python runtime) by `init.d/recovery-usr`.

**The recovery userspace** is the factory setup webapp (bottle): WiFi setup and
access point, log export, `/version`, and `.fw` upload (→ tmpfs →
`glowforge-updater -f` → fwup signature check → writes slot A → flips the
environment). The factory never updates it in the field, so every machine
runs its as-manufactured recovery. The factory U-Boot, DTB and the 3.14.28
recovery kernel stay in place under ForgeFIRM; see
[Recovery](../../install/recovery.md).

## The factory `.fw` format and updater

A factory `.fw` is a signed fwup 0.14.2 archive: a ZIP holding `meta.conf`,
`meta.conf.ed25519` and the payloads. Its tasks:

- `complete`: MBR, U-Boot to the user area, zero both environment copies,
  rootfs → slot A, zero the p2 and p3 heads.
- `upgrade.a` / `upgrade.b`: raw-write `rootfs.ext4` into a slot.

The factory updater flow: authenticated `GET <server>/update/current` →
`{version, download_url}` → resumable download to `/data/glowforge.fw` →
verify against `/glowforge/pubkeys` → apply to the **inactive** slot →
`fw_setenv mmcpart mmcroot` → reboot. fwup is the factory's own package and
apply mechanism, and ForgeFIRM uses the same format and the same flow: a signed
`.fw` applied to the inactive slot, then an environment flip (see
[Install and update internals](../forgefirm/install-and-update.md)).

## Facts about the factory firmware

- There are no `/factory/imgN` mounts.
- The generic `fw_env.config` points at the wrong device; the per-device
  `fw_env_mmcblk2.config` is the correct one.
- There is no SSH; the factory firmware is reachable at the serial console
  only, where the login is `root` with no password.
- The factory kernel cannot see the SD card.
- The factory `/etc/version` is a numeric datetime stamp, so "newest slot" is
  an integer comparison.
- Both factory rootfs slots and the recovery boot partitions can be read out
  and archived; the ForgeFIRM installer does this before it writes anything
  (see [Install](../../install/install.md)).
