---
title: Image and BSP
---

# Image and BSP

ForgeFIRM is a Yocto image for the factory Glowforge control board. This
page describes what the image is made of: the layers, the distro, the two
images, the kernel and its configuration, the device tree, the reserved
motion-memory pool, and the design facts behind the real-time and camera
choices. How to build it is on [Build](../../developers/building.md).

## Layers

| Layer | Repository | What it holds |
|---|---|---|
| `meta-forgefirm` | [forgefirm](https://github.com/openglow-org/forgefirm) | The ForgeFIRM layer: the `forgefirm` distro, the two images, the ForgeFIRM components (`forgectrl`, `grblhal-glowforge`, `forgefirm-app`, `forgefirm-keys`, `forgefirm-logging`, `forgetest`, `ffboot`, `slotmigrate`), and the supporting recipes (`fwup`, `ulfius` with `orcania` and `yder`, `libmicrohttpd`, `rsyslog`, `firmware-imx`) |
| `meta-glowforge-bsp` | [meta-openglow](https://github.com/openglow-org/meta-openglow), branch `scarthgap` | Machine `glowforge`: the factory NXP i.MX6 control board (kernel, device tree, U-Boot, board recipes, the `kernel-module-glowforge` recipe, `python3-gfhardware`) |
| `meta-openglow-core` | [meta-openglow](https://github.com/openglow-org/meta-openglow), branch `scarthgap` | Distro-neutral recipes shared by the images built on it: the Glowforge service utilities (`python3-gfutilities`), base-files, networking |

Both `meta-openglow` layers target the Yocto `scarthgap` release and are
consumed by the ForgeFIRM build. The upstream layers kas clones are `poky`
(`meta`, `meta-poky`), `meta-openembedded` (`meta-oe`, `meta-python`,
`meta-networking`), `meta-freescale`, and `meta-freescale-distro` (which
provides `fslc-base.inc`, required by the distro). The build entry point is
`kas/forgefirm-glowforge.yml`; the debug-kernel variant is
`kas/forgefirm-glowforge-debug.yml`. The `kernel-module-glowforge` sources
are not a layer: the recipe fetches them at a pinned revision
([Release flow](../../developers/release-flow.md)).

The `meta-openglow` layers are experimental and are not supported or
endorsed by Glowforge.

## The distro

The distro is `forgefirm`, built on `fslc-base.inc`. It removes the
features the board has no use for (`3g alsa avahi bluetooth bluez5 ext2
irda nfc nfs pci pcmcia pulseaudio vulkan wayland x11 zeroconf`) and keeps
`opengl`: forgectrl's camera demosaic runs as GLES2 fragment shaders on the
GC880 (etnaviv) through surfaceless EGL, with no display stack. Mesa is
trimmed to that (`opengl gles egl gbm gallium etnaviv`: the etnaviv gallium
driver, GLES, EGL, GBM; no GLX, no X11 or Wayland platforms). The udev
hardware database is dropped (`eudev-hwdb`, 7.7 MB of USB and PCI
identities; the board has neither bus).

rsyslog replaces the busybox syslogd and klogd
(`VIRTUAL-RUNTIME_base-utils-syslog`), trimmed to `rsyslogd rsyslogrt klog
inet regexp`: the local socket and kernel inputs, file output, plain UDP and
TCP forwarding, and rainerscript filters; no TLS, database, HTTP, or signing
modules ([Logging](logging.md)).

## The images

Two images come from one bitbake run: `forgefirm-image` (the release image)
and `forgefirm-image-dev` (the dev image, a strict superset that the bench
runs). Both build on the BSP's `glowforge-image`. The dev image adds a root
login without a password, the python3 `mmap` and `ctypes` modules, gdb and
strace, the acceptance tool `forgetest`, and the bench tools; a release
image never has them (it does carry the interpreter and the modules the
cloud controller and the homing runner import), and
`release.sh` refuses a release rootfs whose `sshd_config` permits a root
login or an empty password, and one whose root entry carries a password
(root has none and works at the console only)
([Build](../../developers/building.md)).

The release image installs, on top of the BSP base:

- `grblhal-glowforge`: the grblHAL motion controller (Grbl over TCP:23).
- `forgectrl`: the machine-services daemon (HTTPS :443, HTTP :80).
- `gfhome`: one-shot Glowforge web-service homing, invoked by the controller
  for `$H` when `homing_mode = gfcloud`.
- `gfcloud`: the full Glowforge web-service controller daemon, started when
  `controller_mode = cloud`; mutually exclusive with grblHAL. It pulls
  `python3-ffmachine`, the shared web-service machine glue.
- `v4l-utils`: `media-ctl` and `v4l2-ctl` for the imx-media pipeline.
- `fwup`: applies signed `.fw` archives to the inactive rootfs slot.
- `ffboot`: boot-slot inventory and switching (also ships `fw_env.config`).
- `slotmigrate`: the boot-time reclaim of the legacy p4 layout.
- `forgefirm-logging`: renders the per-logger rsyslog rules from the
  settings before rsyslog starts, and drives size-capped rotation.
- Mesa GLES2 and EGL on etnaviv (`libegl-mesa libgles2-mesa libgbm
  mesa-megadriver`) for forgectrl's GPU demosaic, loaded with `dlopen` at
  runtime; without them forgectrl falls back to the NEON path.
- `firmware-imx-lic`: the NXP firmware EULA text at
  `/usr/share/licenses/firmware-imx/EULA`, next to the VPU blob.

The factory cloud client `gfui-client` is removed (it connects to
Glowforge's servers; its role is filled locally by forgectrl and the
controllers). The `python3` meta-package is removed; each Python recipe
declares the standard-library module packages it imports. `python3-asyncio`
is installed on top of those: no ForgeFIRM program imports it, and it is there
for extensions, which run on the image's interpreter. `nano` is trimmed
from the release image (8.7 MB, mostly libmagic) and kept on the dev image.

The release rootfs must fit a 200 MiB factory eMMC slot (409600 blocks).
The image recipe deploys a raw ext4 beside the wic, sizes it as content plus
40 MiB working space (`IMAGE_ROOTFS_EXTRA_SPACE = "40960"`,
`IMAGE_OVERHEAD_FACTOR = "1.0"`), and hard-caps it at the slot size
(`IMAGE_ROOTFS_MAXSIZE = "204800"`): the build fails rather than emit an
unflashable image. `scripts/mkfw.sh` packs the ext4 into the signed `.fw`
([Install and update](install-and-update.md)). Each image carries
`/etc/forgefirm-manifest.json`, the build-input identity the acceptance
tool and the release gate compare
([Acceptance](../../developers/acceptance.md)), and `/etc/forgefirm-version`.

The version also goes under the machine mark in the two files a person
reads: `/etc/issue`, the serial-console login prompt, and `/etc/motd`,
which every login prints, the network ones included. The mark keeps its
color in the motd, which a login writes out as it is. `/etc/issue` is
parsed by the getty that prints it, so a backslash or a percent sign in it
is written twice. There is no pre-authentication banner: a client that has
not logged in is told nothing about the machine.

## The read-only root filesystem

Both images mount the root filesystem read-only. The booted slot (eMMC p1
or p2, or the SD card on the bench) is never written while it runs. `/data`
(p3) is the one writable partition: the machine state, the logs, and the
staged updates ([Install and update](install-and-update.md#the-update-manager)).

The `read-only-rootfs` image feature of poky carries the mechanics. The
root line of `/etc/fstab` is `ro` (the BSP's `base-files` fstab), and
`/etc/default/rcS` says `ROOTFS_READ_ONLY=yes`. The volatile links are made
at build time: `/etc/resolv.conf` points into `/run`, and `/tmp`,
`/var/tmp`, and `/var/log` point into `/var/volatile` (tmpfs, empty at every
boot). From the first boot script on, `/var/lib` is a writable copy in RAM
(the ntp drift file, nothing that must last). A package whose post-install
step needs the machine fails the build. The packages a read-only rootfs
cannot use are dropped: `shadow`, `base-passwd`, `update-rc.d`, and
`update-alternatives`; the account files and the init links stay.

What must last a reboot, or change at run time, is handled file by file:

| What | Where | How |
|---|---|---|
| The operator accounts | `/etc/passwd`, `/etc/shadow`, `/etc/group`, `/etc/gshadow` | `forgefirm-users` renders the four files from the record `/data/forgefirm/users` into `/run/forgefirm/accounts` and bind-mounts each copy over its `/etc` file: at boot (S05, before sshd) and at every `reload` forgectrl asks for. The copies hold the image's own accounts plus the record's; a render writes through the mount, so a login that arrives mid-write is refused, never given a stale account. Until the first render the image's files are in effect, so root works at the console from the first second. The home directories are under `/data/forgefirm/home` (each `0700` and its account's; the directory of homes `0755`). An account walks through `/data/forgefirm` to get there, so every render gives that directory the search bit for group and others, whoever made it and under whatever umask: nothing is taken away, nothing in it becomes listable, and what is private in it is closed file by file. |
| The machine's name | `/etc/hostname` | `forgefirm-hostname` names the machine `forgefirm-<xxxx>`, from the last four hex digits of the wlan0 MAC address (eth0 on a machine with no WiFi), at S38 in rcS: before poky's `hostname.sh` reads the file and before the network starts. The rootfs is read-only, so the file shows a bind-mounted copy under `/run/forgefirm`. The DHCP client sends the name as the hostname option, so a network with dynamic DNS publishes it. |
| The console banner | `/etc/issue` | `forgefirm-banner` bind-mounts a copy under `/run/forgefirm` at the first address change after boot and writes the whole banner through it: the image's own lines, kept in a second copy, and one panel URL per global address ([forgectrl](forgectrl.md#http-api)). |
| The sshd host keys | `/data/forgefirm/ssh/` | Made at the first start of sshd, kept across updates: the fingerprint of the machine does not change with a release. |
| The boot timestamp | `/data/forgefirm/timestamp` | Written at shutdown and restored at boot when it is later than the clock; the board has no battery-backed RTC (`forgefirm-persist`). |
| The random seed | `/data/forgefirm/random-seed` | Carried from shutdown to the next boot (`forgefirm-persist`). |
| The logrotate state | `/var/run/forgefirm-logrotate.status` | Fresh at every boot. The rules are size-capped, so nothing depends on it ([Logging](logging.md)). |
| The rendered rsyslog rules, the settings, the records, the TLS key, the panel token, the GRBL settings store | `/data/forgefirm/` | Unchanged ([Install and update](install-and-update.md#the-update-manager)). |

Everything else the daemons and the controllers write is under `/data`,
`/run`, `/tmp`, or sysfs. The acceptance test `image.health` checks the
mounts, and `release.sh` refuses a release rootfs whose fstab does not mount
`/` read-only, mounts a factory slot, or keeps the host keys elsewhere.

**The dev image** also mounts the two factory rootfs slots read-only under
`/factory/img1` and `/factory/img2`, a bench convenience for reading a
factory image in place (the `ffboot` inventory reuses the mounts). The
release image has no `/factory` mounts; `ffboot -l` reads a slot through a
temporary read-only mount.

**To change a file on the rootfs**, a hot copy of a binary or a script on
the bench, remount it writable for the copy and put it back:

```sh
/etc/init.d/forgectrl stop; while pidof forgectrl >/dev/null; do sleep 1; done
mount -o remount,rw /
cp /tmp/forgectrl /usr/bin/forgectrl && chmod 755 /usr/bin/forgectrl
mount -o remount,ro /
/etc/init.d/forgectrl start
```

The remount back to read-only answers "Device or resource busy" while any
file on the rootfs is open for writing. A daemon that is still exiting is
the usual holder (the init script's stop returns before the daemon has
gone), so wait for the exit before the remount, or repeat the remount.
`/data` and `/tmp` need no remount. A file under `/etc` that a bind mount
covers (the account files, `/etc/hostname`, `/etc/issue`) is reached on the
rootfs only after
`umount` of the mount.

## The machine

Machine `glowforge` is the i.MX6 Solo SOM in the Basic, the Plus, and the
Pro (`MACHINEOVERRIDES =. "mx6:mx6dl:"`, tuned for the Cortex-A9). The
kernel is `linux-fslc` 6.12 (mainline LTS, from meta-freescale) and the
device tree is `nxp/imx/glowforge.dtb`. The legacy `linux-glowforge`
4.14.98 recipe (the factory vendor kernel) is kept for reference only and is
not built. U-Boot builds from `glowforge_defconfig` for reference only; the
factory bootloader stays on the eMMC in every install flow
([Boot and storage](../machine/boot-and-storage.md)). The serial getty is
on `ttymxc0`; the kernel has no virtual console (no display), so there is no
getty on `tty1`.

Firmware: the WL18xx blobs (`linux-firmware-wl18xx`) and the VPU blob for
the i.MX6 Solo (`vpu_fw_imx6d.bin`). The e-paper controller firmware and the
SDMA RAM firmware for the i.MX6 are removed: no EPDC, and an SDMA that runs its ROM
scripts by design (the built-in driver probes before the rootfs, and every
client on the board uses ROM scripts; the pulse script is loaded by
`glowforge.ko` itself).

Kernel modules are named explicitly instead of the `kernel-modules`
meta-package, which would drag every module the kernel builds onto the
rootfs: `kernel-module-glowforge` (essential), `wl18xx`, `wlcore-sdio`,
`ov5648`, `ov8856`, `video-mux`, `mux-gpio`, `mux-mmio`, `imx6-media`,
`imx6-media-csi`, `imx6-mipi-csi2`, `coda-vpu`, `lm75`, and
`st-accel-i2c`. Modules these pull in through `modules.dep` (wlcore,
mac80211, cfg80211, libarc4, crc7, mux-core, imx-media-common, v4l2-jpeg,
imx-vdoa, videobuf2, st-accel, st-sensors, ...) come along as package
dependencies. Anything a driver loads by alias instead (the Wi-Fi ciphers)
is built into the kernel by the config fragment.

## Kernel configuration

The kernel configuration is `imx_v6_v7_defconfig` with the fragment
`glowforge.cfg` merged on top. That defconfig targets every i.MX6 and i.MX7
board NXP shipped; the fragment turns the result into the kernel for one
board: an i.MX6 Solo with UART, eCSPI2 (the PIC), I2C1, I2C2, and I2C4,
three uSDHC ports (WL1805 SDIO, SD, eMMC), PWM1, PWM2, and PWM4, EPIT1 and
EPIT2, SDMA, MIPI CSI-2 into the IPU, the VPU, the GPU, CAAM, OCOTP, the
SNVS RTC, WDOG1, and the glowforge nodes. Every line in the fragment is
expected to survive the merge as written.

What the board needs turned on:

| Option | Why |
|---|---|
| `CONFIG_IMX_SDMA=y` | The i.MX6 SDMA underpins the factory step-stream playback ForgeFIRM reuses. The engine runs on its ROM scripts; the driver is built in and probes before the rootfs exists, so no RAM firmware is shipped. |
| `CONFIG_PREEMPT=y` | Full kernel preemption, as the factory kernel ran (the defconfig gives only `PREEMPT_VOLUNTARY`). Bounds the wakeup latency of the `SCHED_FIFO` pulse feeder and the softirq hrtimers (ramp updates, the safety sampler, the HV-watchdog feed). See [Real time](#real-time). |
| `CONFIG_PANIC_ON_OOPS=y`, `CONFIG_PANIC_TIMEOUT=10`, `CONFIG_DETECT_HUNG_TASK=y`, `CONFIG_BOOTPARAM_HUNG_TASK_PANIC=y`, `CONFIG_SOFTLOCKUP_DETECTOR=y`, `CONFIG_BOOTPARAM_SOFTLOCKUP_PANIC=y` | An oops becomes a panic so the laser-safing panic notifier in `glowforge.ko` runs (EPIT stop, FIRE parked, charge pump low, steppers de-energized). Without this a NULL dereference in any driver mid-cut kills only the offending task and leaves the SDMA + EPIT engine clocking FIRE bits out of the ring. A hung task and a soft lockup panic on the same reasoning. The panic reboots the machine after ten seconds (the boot arguments carry `panic=10` as well). |
| `CONFIG_PSTORE=y`, `CONFIG_PSTORE_RAM=y`, `CONFIG_PSTORE_CONSOLE=y` | The crash record: the oops text and the tail of the console log are kept in the ramoops region the device tree reserves (the 1 MiB at the top of DRAM that the bootloader holds back from the memory node) and come back on the next boot under `/sys/fs/pstore`. |
| `CONFIG_IMX2_WDT=y` | U-Boot arms WDOG1 with a 60 s timeout before Linux starts. The driver must be pinned; without it nothing adopts the running watchdog and every boot dies in a 60 s reset loop. With the driver in and `/dev/watchdog` left unopened, the kernel core keeps the boot-armed watchdog fed. It is a boot and system watchdog only, never a laser-safety mechanism ([forgectrl](forgectrl.md#watchdog-scope)). |
| `CONFIG_CMA=y`, `CONFIG_DMA_CMA=y` | CMA stays on for the camera and imx-media path (the 64 MiB `linux,cma` node) and as the fallback allocator if the dedicated pulse-ring pool fails to attach. |
| `CONFIG_MXC_EPIT_API=y` | Exposes EPIT1 and EPIT2 to `glowforge.ko` (`arch/arm/mach-imx/epit_api.c`). |
| `CONFIG_PM=y`, `CONFIG_REGULATOR=y`, `CONFIG_REGULATOR_FIXED_VOLTAGE=y`, `CONFIG_REGULATOR_ANATOP=y`, `CONFIG_ARM_IMX6Q_CPUFREQ=y`, `CONFIG_EXT4_FS=y` (with POSIX ACL and security) | Pinned because the defconfig gets them selected by symbols the fragment turns off. PM carries runtime PM and the GPC power domains (the GPU/VPU rail), and the camera sensor drivers depend on it. The regulator core carries the fixed rails (12 V, 40 V, WLAN enable, camera supplies) and ANATOP (VDDARM for cpufreq). ext4 is the rootfs, `/data`, and the factory slots; with ext2 and ext3 off it mounts those formats too. |
| `CONFIG_CRYPTO_AES/CCM/GCM/CTR/GHASH/CMAC/SHA256=y` | The ciphers mac80211 asks the crypto API for by name at association time (CCMP, GCMP, BIP/CMAC) and SHA-256 for the signed regulatory database, built in so nothing depends on a module found by alias. |
| Media: `CONFIG_MEDIA_SUPPORT=y`, `MEDIA_SUPPORT_FILTER=y`, `MEDIA_SUBDRV_AUTOSELECT=y`, `MEDIA_CAMERA_SUPPORT=y`, `MEDIA_PLATFORM_SUPPORT=y`, `MEDIA_CONTROLLER=y`, `VIDEO_DEV=y`, `VIDEO_V4L2_SUBDEV_API=y`, `V4L_PLATFORM_DRIVERS=y`, `V4L_MEM2MEM_DRIVERS=y`, `VIDEO_CODA=m`, `VIDEO_OV5648=m`, `VIDEO_OV8856=m`, `STAGING_MEDIA=y`, `VIDEO_IMX_MEDIA=m`, `VIDEO_MUX=m`, `MULTIPLEXER=m`, `MUX_GPIO=m`, `MUX_MMIO=m` | Mainline OV5648 (5 MP) and OV8856 (8 MP, "HD" units) subdevs behind the imx6 IPU and MIPI-CSI2 (imx-media) capture path, with a GPIO video-mux modeling the factory CAM_SEL MIPI switch (lid/head). Both sensors share the `camera@36` dual-compatible node; whichever matches the chip id binds. `MEDIA_SUPPORT_FILTER` narrows the media stack to camera and platform drivers. `VIDEO_IMX_MEDIA` covers the whole 6.12 imx6 capture path (IPU CSI plus the imx6-mipi-csi2 receiver). The GPIO mux is CAM_SEL; the MMIO mux is the IPU CSI source select in IOMUXC_GPR. |
| WiFi: `CONFIG_CFG80211=m`, `MAC80211=m`, `WLAN_VENDOR_TI=y`, `WLCORE=m`, `WLCORE_SDIO=m`, `WL18XX=m`; `CFG80211_DEFAULT_PS` not set; `RFKILL_INPUT` not set | cfg80211 and mac80211 as modules, so they load with wlcore after the rootfs is mounted and the regulatory database loads directly. Power save default-off: a mains-powered machine gains only latency and dropouts from it (forgectrl also pins it off at startup). The `doors` switch is EV_SW code 3 in the factory switch numbering, which collides with the Linux `SW_RFKILL_ALL` code: with the rfkill-input handler built in, every lid-open would soft-block all radios and drop the WLAN mid-session. The switch code is fixed UAPI (the factory DTB and gfhardware both use it), so the handler goes instead. |
| `CONFIG_CGROUP_SCHED=y`, `FAIR_GROUP_SCHED=y`, `CFS_BANDWIDTH=y`, `MEMCG=y`, `CGROUP_PIDS=y`; `RT_GROUP_SCHED` not set; `CONFIG_SECURITY=y`, `SECURITY_LANDLOCK=y`; `CONFIG_NF_TABLES=y`, `NF_TABLES_INET=y`, `NFT_REJECT=y`, `NFT_LIMIT=y` | The kernel's share of [the extension sandbox](#the-extension-sandbox): the cgroup v2 cpu, memory, and pids controllers, landlock, and nftables, beside the seccomp filters and the cgroup core the defconfig already gives. |
| `CONFIG_SMP` not set | One core. The i.MX6 Solo has a single Cortex-A9, so the SMP kernel's spinlocks, IPIs, and per-CPU machinery buy nothing. The TWD stays the tick and the GPT the clocksource. |
| `CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE=y`; the ondemand, conservative, powersave, and userspace governors not set | The CPU runs at its full 996 MHz always. A single core with a `SCHED_FIFO` step producer gains nothing from idling at 396 MHz and waiting for ondemand's sampling to notice a job, and the SoC sits at half its passive trip point at full clock. |
| `CONFIG_ARCH_MULTI_V6` not set | Only the Cortex-A9 (ARMv7) i.MX6 Solo runs this kernel; ARMv7 alone gives the compiler the real target. |

What the defconfig turns on that the board has no hardware or consumer for
is turned off: the other i.MX SoCs (i.MX50/51/53, 6SL/6SLL/6SX/6UL, 7D,
7ULP, 8M, VF610), USB (no controller is enabled; usbotg and usbh1 stay
disabled, as in the factory tree), HID, Ethernet, CAN, Bluetooth (the
WL1805 is Wi-Fi only) and every other WLAN vendor, SATA, SCSI, PCI, MTD, RAM
disks, network filesystems, FUSE, quota, optical formats, the display path
(DRM_IMX, HDMI, LVDS, panels, bridges, the framebuffer layer, the virtual
console, backlights; the GPU and the IPU core stay: DRM plus etnaviv for the
demosaic and the IPU for CSI capture), sound (the factory buzzer driver is
not part of ForgeFIRM), input beyond the gpio-keys switch block
(touchscreens, mice, HID, the evbug handler), non-camera media (analog and
digital TV, radio, SDR, CEC, PXP, other sensors), PMICs and GPIO expanders
for other boards, LED triggers, ATAGs, suspend (which also hides kexec and
the crash kernel; pstore is the crash record), swap, initrd formats beyond
gzip, high memory (512 MB fits below the 3G/1G split), the BFQ and Kyber
I/O schedulers, and the connector.

The debug fragment `glowforge-debug.cfg` (`CONFIG_DEBUG_MUTEXES`,
`CONFIG_PROVE_LOCKING`, `CONFIG_DEBUG_ATOMIC_SLEEP`,
`CONFIG_DEBUG_SPINLOCK`) is applied only when `FORGEFIRM_KERNEL_DEBUG = "1"`
(the kas debug variant). It carries a large runtime cost and belongs on a
one-time drill image, never on a shipped one
([Build](../../developers/building.md#the-debug-kernel-variant)).

## Kernel patches

The factory board runs an NXP vendor kernel (linux-imx 4.14.98) with a set of
out-of-tree changes. Each one the board needs is re-derived against mainline
6.12 as a patch in `recipes-kernel/linux/linux-fslc/`, never applied as the
old 4.14 patch. The ones mainline already covers (the OV5648 sensor, the
LIS2HH12 accelerometer) bind to in-tree drivers, and the bus-frequency
scaling disable has no mainline counterpart to disable. The patches are
scoped to `MACHINE=glowforge`.

| Patch | What it does |
|---|---|
| `0001-arm-dts-imx-register-glowforge-dtb` | The Makefile hook that registers `glowforge.dtb` |
| `0002-mach-imx-add-glowforge-epit-api` | Exposes the EPIT timers to `glowforge.ko` |
| `0003-imx-sdma-expose-glowforge-api` | Exposes the SDMA engine to `glowforge.ko` |
| `0004-spi-imx-glowforge-pic-periodreg-delay` | The spi-imx PIC inter-word delay (re-derived from the factory "Add delay to SPI") |
| `0005-media-video-mux-forward-get_mbus_config` | The video-mux forwards `get_mbus_config` |
| `0006-media-ov5648-implement-get_mbus_config` | OV5648 implements `get_mbus_config` |
| `0007-media-imx6-mipi-csi2-link-freq-behind-mux` | The CSI-2 receiver finds the link frequency behind the mux |
| `0008-imx-sdma-preallocate-glowforge-datamem-bounce` | The SDMA live-feed hardening |
| `0009-pwm-imx27-glowforge-extra-prescale` | The laser-PWM extra prescaler (the ~40 kHz laser carrier; factory patch 1001) |
| `0010-media-imx-capture-allow-cache-hints` | The capture-queue cache-hint opt-in, so forgectrl can request CPU-cached capture buffers |
| `0011-media-ov8856-implement-get_mbus_config` | OV8856 implements `get_mbus_config` (the same gap 0006 closes for ov5648) |
| `0012-media-ov8856-24mhz-xvclk` | The 24 MHz xvclk the board's sensor oscillator runs at |
| `0013-media-ov8856-2-lane-raw8-modes` | The 2-lane RAW8 modes that put full 8 MP resolution inside this SoC's 1 Gbps/lane CSI-2 receiver |
| `0014-spi-imx-no-dma-described-is-not-an-error` | Quiet fallback to PIO when a controller describes no DMA channels (the PIC's ecspi2 has none on purpose) |
| `0015-wlcore-nvs-is-optional-request-it-without-a-warning` | wlcore asks for its optional NVS file without a loader warning (the rootfs ships none; the MAC is fused) |

The bbappend header lists the patches, and `glowforge.cfg` describes the
configuration, in the `meta-openglow` repository.

## Device tree

The device tree is `glowforge.dts` with `openglow_common.dtsi`, overlaid
into `arch/arm/boot/dts/nxp/imx/` (6.12 keeps 32-bit device trees there).
The Solo has one core, so the tree deletes the base include's `cpu@1`. The `chosen` node carries `console=ttymxc0,115200` only, as a
fallback: U-Boot always overwrites `bootargs` from its environment
(`mmcargs` carries the real `root=`). There is no `root=` in the tree, so a
boot that fell through to it would stop at a visible rootfs panic instead of
silently booting a hardcoded slot, and no `quiet`, because the recovery
ladder ends at the serial console, which must show the early boot output.

The switch inputs are a `gpio-keys` node ([forgectrl](forgectrl.md#switches-and-button)).
The camera sensors share the `camera@36` dual-compatible node behind a GPIO
video-mux ([Video pipeline](video-pipeline.md)). The factory DTB is ground
truth for the board; the hardware pages under
[The machine](../machine/index.md) describe what it maps.

### The reserved motion-memory pool

The board has 511 MiB of usable DRAM, `0x10000000` to `0x2fefffff`. Memory
reserved for DMA is a dedicated pool for the cnc SDMA pulse ring plus the
default CMA for camera, IPU, and VPU capture buffers: **96 MiB in all**,
leaving about 454 MiB to Linux. `MemTotal` reads about 464 MiB on the
board-only kernel, and a machine idling in GRBL mode with the daemon and the
controller up uses about 100 MiB of it.

One more region sits above the memory node: the **1 MiB at `0x2ff00000`** that
the factory bootloader already holds back. ForgeFIRM uses it for
pstore/ramoops, so a panic leaves its reason where the next boot can read it:
32 KiB dump records, a 256 KiB console record, 16-byte ECC, mounted at
`/sys/fs/pstore` from `fstab` and staged into the log export
([Logging](logging.md)).

A **size-aligned no-map reserved pool** in the device tree backs the pulse
ring: `cnc_reserved: cnc-pulsebuf`, `compatible = "shared-dma-pool"`,
`no-map`, size 32 MiB (`0x02000000`, the factory ring size), alignment
32 MiB (a size-aligned base, so it lands at `0x2c000000`). The
`glowforge,cnc` node references it via `memory-region`, and `cnc.c` attaches
it with `of_reserved_mem_device_init()`. Pulling the ring from the shared CMA fails
once boot has fragmented it (`cma_alloc -EBUSY`), because the out-of-tree
module probes late; a non-reusable shared-dma-pool (which must be no-map) is
never touched by movable allocations and, size-aligned, satisfies
`dma_alloc_coherent()` deterministically. `no-map` means the whole pool
leaves the kernel's memory map at boot whether the ring uses it or not; on
the 512 MB SOM that is affordable and buys a deterministic allocation.

The module's `ring_mb` parameter sets the ring size and must fit the pool.
The live feed keeps only a few KB in flight, so the pool size matters for
cloud mode, which preloads as much of a job as the ring holds (about 1 MiB
per 100 s at 10 kHz, so 32 MiB is about 56 min) and tops it up as it drains
([Pulse feeder contract](pulse-feeder-contract.md#ring-size-and-the-reserved-pool)).

The reusable CMA (`linux,cma`, `linux,cma-default`) is 64 MiB
(`0x04000000`): a 2592x1944 SBGGR8 frame is about 5 MiB and an 8 MP
machine's 3264x2448 frame is about 8 MiB, so the deepest capture queue is
about 32 MiB, and 64 MiB leaves room for that plus the VPU JPEG contexts.

## Real time

`CONFIG_PREEMPT=y` with a deep ring and a `SCHED_FIFO` feeder is the
real-time design. PREEMPT_RT is not selectable on arm32 6.12 (no
`ARCH_SUPPORTS_RT`), and the buffer arithmetic makes it unnecessary.

**The argument is about queue depth, not ring size.** The ring drains at one
byte per timer tick, which is at most 200 KB/s even at the engine's 200 kHz
ceiling. The live feeder's bounded queue of 50 to 200 ms is therefore only a
few kilobytes in flight, and it rides out worst-case scheduling latency with
orders of magnitude to spare. Measured under a full processor and I/O load:
100 kHz for 120 seconds, a 150 ms queue, a worst write latency of 0.2 ms, and
zero underruns. The worst a loaded system can do is fail to supply bytes in
time, and that case is detected and treated as a fault, never as silent damage
([Pulse feeder contract](pulse-feeder-contract.md#pacing-and-backpressure)).

The ring's own size is a capacity for cloud mode's preload, not a latency
figure: 32 MiB is about 168 seconds of stream at the 200 kHz ceiling and about
56 minutes at the 10 kHz print tick.

Revisit RT only if the underrun bench ever contradicts this arithmetic.

## The extension sandbox

The image holds ready what contains a process that is not part of the
firmware: accounts for it to run as, a cgroup tree to limit and freeze it in,
network rules that refuse what it sends, and the two kernel facilities a
process uses to give up its own reach. They are in place from boot, before
anything that would use them starts. The recipe is `forgefirm-sandbox`.

**The account pool.** Thirty-two system accounts, `ffx0` to `ffx31`, uid and
gid 800 to 831, one group each, created when the image is built. No home
(`/nonexistent`), no shell (`/bin/false`), a locked password. The block sits
below 1000 on purpose: the [account render](#the-read-only-root-filesystem)
replaces only the accounts from 1000 up, so an account reset leaves the pool
alone, and the read-only rootfs never needs an account made at run time. The
image's other system ids count down from 999 and come nowhere near it.

**The cgroup tree.** `forgefirm-sandbox` runs at S30 in rcS. It mounts cgroup
v2 at `/sys/fs/cgroup`, hands the cpu, memory, and pids controllers down to
`/sys/fs/cgroup/ffx` and from there to the groups made under it, and marks
`ffx` idle-class (`cpu.idle`), so a runnable task in the root group always
runs before anything under `ffx`. forgectrl, the controller, and every other
process of the firmware stay in the root group, which has no limit and no
controller file that could give it one. A group under `ffx` takes `cpu.max`,
`memory.max`, and `pids.max`, and `cgroup.freeze` stops every process in it
(the freezer is part of the v2 core; the v1 freezer controller is not built).

**No realtime group scheduler.** `CONFIG_RT_GROUP_SCHED` stays off, and that
is part of the [real-time design](#real-time), not an omission. With it, a
`SCHED_FIFO` thread runs only inside a group that was given realtime runtime,
and the cpu controller cannot be enabled while a realtime thread sits outside
the root group. The pulse feeder is `SCHED_FIFO` and needs nobody's leave to
run.

**The deny rules.** The same script loads `/etc/forgefirm/ffx.nft` with `nft`
(nftables is built into the kernel, so nothing waits on a module), and rcS
runs before the network starts, so no pool uid ever has an interface to send
on with the rules absent. The table is `inet ffx`, one table for IPv4 and
IPv6:

```
chain output   type filter hook output priority filter; policy accept;
               meta skuid 800-831 jump pool
chain pool     oifname "lo" jump refuse
               meta skuid vmap @allow
               jump refuse
chain refuse   meta l4proto tcp counter reject with tcp reset
               counter drop
map allow      uid : verdict
```

Every packet sent from a socket a pool uid owns is refused: on loopback, to
the machine's own LAN address, anywhere. That keeps such a process off the
Grbl port, off forgectrl's listeners, and off the
[controller's report route](cooling-engine.md#job-state-reports). A refused
TCP connect is answered with a reset, so it fails at once and does not time
out; anything else is dropped, which the sender sees as `EPERM`. The rules
match the sending socket's uid on the output hook, which needs no connection
tracking, so none is built, and a packet of the firmware's own costs one
comparison. The way through is the `allow` map: a uid mapped to a chain that
accepts that process's permitted destinations; what the chain does not accept
returns to `pool` and is refused. **The machine itself is never a
destination, whatever the map says:** everything a host sends to one of its
own addresses, the LAN one included, leaves through `lo`, and `pool` refuses
that before it looks at the map. An allowlist names addresses, and the
machine's own address can change under it with a new DHCP lease; this rule
does not depend on knowing the address.

**A listening port is answered from, never dialed out of.** A package with
`net.listen` gets a rule for its port in that chain, and the rule matches the
*source* port, so on its own it would let the process reach any destination at
all by binding a connection to that port - the declared destinations undone by
a capability that has nothing to do with them. The TCP flags tell the two
apart without connection tracking: a lone `syn` is a connection the process is
opening and is refused, and every other segment - the `syn`+`ack` that answers
a caller, and the rest of that conversation - is its listener speaking and is
let out.

Loading the file again replaces the table, allowlists included: it fails
closed. The kernel's `limit` expression is
built for a transmit rate limit. nftables on the image is the `nft` binary
and its library with JSON output (`nft -j`), no interactive shell and no
Python binding.

**What a process does to itself.** seccomp filters (from the defconfig) and
landlock (`CONFIG_SECURITY_LANDLOCK`, first in the defconfig's `CONFIG_LSM`
list; ABI 6 on this kernel, which includes the TCP bind and connect rules)
need no privilege and no policy file: a process that has set `no_new_privs`
narrows its own system calls, its own view of the file tree, and its own TCP
connects, and its children inherit the result.

`forgefirm-sandbox status` prints the state of both halves and exits nonzero
when either is missing. The acceptance test `exthost.platform` proves each
piece on a probe process, and `scripts/sandbox-rules-test.py` in the
`forgefirm` repository proves the rule file on real traffic in a network
namespace, in CI.

## Cameras

The camera path is mainline `ov5648` + `video-mux` + `imx6-mipi-csi2` +
`imx-media` (the IPU CSI), not the factory NXP `ov5648_mipi.c`, with the
CODA960 VPU for JPEG and H.264 encoding. forgectrl owns the pipeline
([Video pipeline](video-pipeline.md)). The 8 MP "HD" (OV8856) capture path
is written and expected to work; it is untested only because no HD machine
has been on the bench ([Cameras](../machine/cameras.md)).

## The Python components

`python3-gfhardware` provides the `gfhardware` Python hardware library (with
its `_cam` capture extension) and, from its `forgefirm-app/` directory, the
cloud-mode applications `gfhome.py`, `gfcloud.py`, and `ffmachine.py`.
`python3-gfutilities` is the factory protocol and service layer they use.
Both are described on [Cloud mode](cloud-mode.md).
