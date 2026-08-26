---
title: Developers
---

# Developers

This section tells you how to build, test, release, and change ForgeFIRM.
If you only want to operate the machine, read the Installation and Usage
sections instead.

| Page | Contents |
|---|---|
| [Build](building.md) | The build host, the Yocto build, the two images, and the build of each component. |
| [Release flow](release-flow.md) | The pins, the push order, the acceptance gate, and the signature. |
| [Acceptance](acceptance.md) | The release acceptance contract: the catalog, fingerprints and inheritance, campaigns, the gate. |
| [Test](testing.md) | The host tests in each repository, the CI workflows, and the coverage rule. |
| [The bench](bench.md) | The bench machine, the bench tools, the bench actuator, and the clean-up rule. |
| [Contribute](contributing.md) | The rules for code, proof, and documentation. |
| [Roadmap](roadmap.md) | The open work. |
| [This site](docs.md) | How this site is built, and where each subject goes. |

## The repositories

ForgeFIRM is a set of repositories under
[ScottW514](https://github.com/ScottW514) on GitHub. Each component has its
own repository. The `forgefirm` repository is the base of the build. Each
recipe gets its component from GitHub at a pinned revision. Thus a build
needs only two checkouts. For development, every repository is checked out
into one base working directory, `openglow-forgefirm`, as siblings
([Build](building.md)).

| Repository | Contents | License |
|---|---|---|
| [`forgefirm`](https://github.com/ScottW514/forgefirm) | The base of the build and of the release: the `meta-forgefirm` Yocto layer, the kas configuration, the image recipes, the install and release scripts, the acceptance tool (`forgetest/`), the bench actuator firmware (`fixture/`), the bench tools (`scripts/bench/`), and the release artifacts (`releases/`). Two documents stay in this repository: `docs/BRINGUP.md`, the status document and cold-start runbook until the first production release, and `docs/CAMPAIGN-LOG.md`, the dated bench record. | MIT for the layer metadata. Each component has its own license. |
| [`meta-openglow`](https://github.com/ScottW514/meta-openglow) | The BSP layers, on the `scarthgap` branch. `meta-glowforge-bsp` defines the machine `glowforge`: the kernel, the device tree, U-Boot, and the board recipes. `meta-openglow-core` has the distro-neutral recipes that the images share. The ForgeFIRM build uses it as a sibling checkout. | MIT for the layer metadata |
| [`forgectrl`](https://github.com/ScottW514/forgectrl) | The machine-services daemon, in C, on HTTP port 8080. It supervises the controller, brokers the pulse device, and gates motion liveness. It operates the cooling engine, the cameras, telemetry, settings, diagnostics, logging, the web control panel, and the A/B update system. `docs/SERVICES.md` is the machine-services contract. | MIT |
| [`grblHAL-glowforge`](https://github.com/ScottW514/grblHAL-glowforge) | The grblHAL driver for the stock control board: the controller for GRBL mode. The grblHAL core is a git submodule at `src/grbl` ([ScottW514/core](https://github.com/ScottW514/core), branch `forgefirm`). The machine constants are in `src/boards/glowforge.h`. | GPL-3.0-or-later |
| [`kernel-module-glowforge`](https://github.com/ScottW514/kernel-module-glowforge) | `glowforge.ko`: the SDMA + EPIT pulse engine, the laser latch, the safety readbacks, and the sensors. `UAPI.md` is the pulse-stream feeder contract. | GPL-2.0-or-later |
| [`python3-gfhardware`](https://github.com/ScottW514/python3-gfhardware) | The `gfhardware` Python library for the machine hardware, and the cloud-mode applications in `forgefirm-app/`: `gfcloud.py` (the cloud-mode controller daemon), `gfhome.py` (one-shot homing through the Glowforge service), and `ffmachine.py` (the hardware glue that both use). `forgefirm-app/docs/CLOUD.md` describes cloud mode. | MIT, with one LGPL-2.1-or-later component (see Licenses) |
| [`Glowforge-Utilities`](https://github.com/ScottW514/Glowforge-Utilities) | `gfutilities`, on PyPI: the factory protocol and service layer that cloud mode uses. It includes a machine emulator that speaks the real-time protocol without hardware. | MIT |
| [`forgefirm-docs`](https://github.com/ScottW514/forgefirm-docs) | This site. | CC BY-SA 4.0 |

## How the components connect

```
LightBurn / UGS / cncjs (Grbl over TCP:23)        Glowforge web service (optional)
        │                                                   │
        ▼                                                   ▼
grblHAL-glowforge  (grblHAL core + ForgeFIRM driver)   gfcloud (Python)
  ├─ gcode parser + planner + look-ahead + protocol      ├─ factory action dispatch
  ├─ STEP BACKEND: resamples step events to pulse        └─ preloads factory pulse files
  │  bytes, live-feeds the kernel ring
  ├─ LASER: power bytes + FIRE bit, operator-armed
  └─ cooling client: reports job state, enforces the verdict
        │                        exactly one runs at a time (mode)
        ▼
forgectrl  (machine-services daemon, HTTP :8080)
  supervisor (spawns/respawns the selected controller) · pulse-device broker (one
  exclusive /dev/glowforge hold; controllers inherit the fd) · motion-liveness gate ·
  cooling engine (sole thermal-hardware owner) · cameras · telemetry · settings ·
  diagnostics · web control panel · A/B updates
        │
        ▼
glowforge.ko  (SDMA + EPIT → GPIO → stepper drivers; laser latch; safety readbacks)
Cameras: mainline ov5648 + video-mux + imx6-mipi-csi2 + imx-media (IPU CSI), VPU JPEG encode
```

At build time, kas assembles the upstream layers (poky, meta-openembedded,
meta-freescale, meta-freescale-distro), the BSP layers from `meta-openglow`,
and `meta-forgefirm`. The component recipes get the source repositories at
their pinned revisions ([Release flow](release-flow.md)). One bitbake run
makes both images: `forgefirm-image`, the release image, and
`forgefirm-image-dev`, the bench image.

## Licenses

The code is free software under MIT and GPL licenses. The text of this site
is CC BY-SA 4.0. These are the details that go past a one-word license:

- **grblHAL-glowforge** is GPL-3.0-or-later. It is derived from the
  [grblHAL Simulator](https://github.com/grblHAL/Simulator): the platform
  layer, and the shape of the stream and NVS code. The grblHAL core is
  copyright Terje Io and contributors. The Simulator platform code is
  copyright Jens Geisler and Adam Shelly. The Glowforge driver is copyright
  Scott Wiederhold.
- **kernel-module-glowforge** is GPL-2.0-or-later, copyright 2020-2026 Scott
  Wiederhold and copyright 2015-2021 Glowforge, Inc. The SDMA script
  assembler (`tools/sdma_asm.pl` and `tools/mx51_sdma_set.pm`) makes
  `src/sdma.asm.h` from `asm/sdma.asm` at build time. It is by Eli Billauer,
  copyright 2011, GPL-2.0-or-later, and its headers stay unchanged. Each
  file under `src/` has an `SPDX-License-Identifier` line.
- **python3-gfhardware** is MIT, with one component under a different
  license. `gfhardware/src/bayer.c` and `bayer.h` are the Bayer demosaic
  routines from libdc1394 (Damien Douxchamps, Frederic Devernay; VNG and AHD
  from the DCRAW of Dave Coffin). They are LGPL-2.1-or-later
  (`LICENSE.LGPL-2.1`). The build compiles them into the `gfhardware._cam`
  extension module together with the MIT sources. The repository has the
  full source of both parts and the standard build (`setup.py`). Thus anyone
  can change the LGPL component and build or link `_cam` again. This
  satisfies the relink condition of the LGPL. Binary packages from this
  repository, the ForgeFIRM image recipes included, declare
  `MIT & LGPL-2.1-or-later`.
- **The image** installs NXP firmware blobs (VPU, EPDC) from the i.MX6 BSP.
  NXP distributes them under its firmware EULA. The build configuration
  accepts it (`ACCEPT_FSL_EULA = "1"`). The image ships the license text
  next to the blobs, at `/usr/share/licenses/firmware-imx/EULA`. Keep it
  there in each image that you redistribute. The SDMA firmware comes from
  `linux-firmware`, which has its own license package.
