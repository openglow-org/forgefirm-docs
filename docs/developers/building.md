---
title: Build
---

# Build

ForgeFIRM is built with [kas](https://kas.readthedocs.io/). kas manages the
Yocto layers and pins their versions. The `forgefirm` repository is the base
of the build: it controls the build, and the images land in it. All the
commands on this page run in that repository.

## Baseline

| Item | Value |
|---|---|
| Yocto release | Scarthgap 5.0 LTS |
| Kernel | linux-fslc 6.12 (mainline LTS, from meta-freescale) |
| Machine | `glowforge` (the i.MX6 Solo SOM in the Basic, the Plus, and the Pro) |
| Distro | `forgefirm` |
| Images | `forgefirm-image` (the release image) and `forgefirm-image-dev` (the dev image, which the bench runs) |

## Prepare the host

A Linux host is necessary. WSL2 on Windows is also possible; Yocto supports
it officially.

!!! note "WSL2"

    Keep the full tree on the native ext4 file system of WSL2, not on a
    Windows drive mount. The Windows mount breaks case sensitivity and
    permissions, and it is very slow for Yocto. Give the WSL2 VM sufficient
    RAM and disk in `.wslconfig`.

On Ubuntu or Debian (WSL2 included), install the Yocto host packages and kas:

```console
sudo apt-get install -y gawk wget git diffstat unzip texinfo gcc build-essential \
  chrpath socat cpio python3 python3-pip python3-pexpect xz-utils debianutils \
  iputils-ping python3-git python3-jinja2 python3-subunit zstd liblz4-tool file \
  locales libacl1 lz4 rsync
sudo locale-gen en_US.UTF-8
pipx install kas        # pipx, because Ubuntu 24.04 (PEP 668) blocks "pip install --user"
```

For other distributions, see the
[Yocto Project Quick Build](https://docs.yoctoproject.org/brief-yoctoprojectqs/index.html).
Do not build as root. The Yocto sanity checks refuse it.

## Get the sources

The convention for work on the project is one base working directory,
`openglow-forgefirm`. Every source repository of the project is checked out
into it, as a sibling of the others. The directory itself is not a
repository. The kas configuration and the bench build scripts depend on this
layout: they refer to the siblings by relative path.

Make the directory, then clone the two repositories that a build needs:

```console
mkdir openglow-forgefirm && cd openglow-forgefirm
git clone https://github.com/ScottW514/forgefirm.git
git clone -b scarthgap https://github.com/ScottW514/meta-openglow.git
```

The kas configuration refers to `meta-openglow` (branch `scarthgap`) at
`../meta-openglow`. kas gets the upstream Yocto layers itself. Each recipe
gets its ForgeFIRM source repository from GitHub at a pinned revision. Thus
a build needs no other checkout.

For work on a component, clone its repository into the same directory. The
build scripts in `forgefirm/scripts/bench/` find it there, and a local
`externalsrc` bbappend can point to it ([Build one
component](#build-one-component)).

```
openglow-forgefirm/            the base working directory (not a repository)
├── forgefirm/                 the base repository; the build runs here
│   ├── kas/
│   │   └── forgefirm-glowforge.yml   the build entry point
│   ├── meta-forgefirm/        the ForgeFIRM layer
│   ├── layers/                the upstream layers that kas clones (gitignored)
│   ├── build/                 the bitbake output, images included (gitignored)
│   └── downloads/ sstate-cache/      the caches (gitignored)
├── meta-openglow/             the Glowforge BSP layers (necessary for a build)
├── forgectrl/                 a component checkout, for work on it (optional)
├── grblHAL-glowforge/         the same
├── kernel-module-glowforge/   the same
├── python3-gfhardware/        the same
├── Glowforge-Utilities/       the same
└── forgefirm-docs/            this site (optional)
```

The configuration refers to `meta-openglow` as a local sibling. Thus the
build uses your in-place edits to the BSP. The configuration also has a
pinned-remote block, commented out. With that block, the `forgefirm`
repository is fully self-contained ([Release flow](release-flow.md)).

## Build the images

Run the commands from the root of the `forgefirm` repository, so that the
outputs land in it:

```console
cd forgefirm
kas build  kas/forgefirm-glowforge.yml     # get the layers, then a full build
kas shell  kas/forgefirm-glowforge.yml     # an interactive bitbake environment
kas dump   kas/forgefirm-glowforge.yml     # show the resolved configuration
```

`kas build` builds the kas target, `forgefirm-image`. A build for the bench
makes both images in one bitbake run. The bench runs the dev image, and the
two images from one run have the same manifest identity ([Test](testing.md)):

```console
kas shell kas/forgefirm-glowforge.yml -c 'bitbake forgefirm-image forgefirm-image-dev'
```

kas clones the upstream layers into `forgefirm/layers/`, builds in
`forgefirm/build/`, and writes the images to
`forgefirm/build/tmp/deploy/images/glowforge/`:

```
forgefirm-image-glowforge.rootfs.wic.gz         the release image
forgefirm-image-dev-glowforge.rootfs.wic.gz     the dev image
```

## The debug-kernel variant

One dev image carries a kernel with the lock-correctness options
(`DEBUG_MUTEXES`, lockdep, `DEBUG_ATOMIC_SLEEP`). Build it with the debug
kas config after the normal build:

```console
kas build kas/forgefirm-glowforge-debug.yml
```

The debug kernel has a different config signature. bitbake rebuilds the
kernel and the dev image under it. The other images stay in the deploy
directory. The debug image lands beside them. Its version string is
`(dev-debug)`.

Do not ship the debug image. The options make the kernel slow. Boot the
debug image one time to run the debug-kernel drills
(`scripts/bench/debug_kernel_drills.py`), then flash the real image. The
drills cycle the 40 V rail, so the machine must be idle.

`forgefirm-image-dev` is a strict superset of `forgefirm-image`. It adds a
root login without a password, python3, gdb and strace, the acceptance tool
`forgetest`, and the bench tools. A release image never has them. The debug
features are in `forgefirm-image-dev.bb`, not in the kas configuration. Thus one build gives a hardened release image and a debug dev image.
`release.sh` refuses a release rootfs that has a root entry without a
password.

!!! note "The U-Boot binary"

    The build also writes `u-boot-glowforge.imx` to the deploy directory.
    It is for reference only. Each supported install and boot flow keeps the
    factory bootloader on the eMMC. Its environment configuration agrees with
    the factory layout (0x80000 primary, 0x82000 redundant), but no install
    path uses it. Do not flash it.

### Build in a container

kas can run the build in its own container (Docker or Podman), for a
reproducible host:

```console
cd forgefirm
kas-container build kas/forgefirm-glowforge.yml
```

### Lock the layer versions

The configuration follows the `scarthgap` branch of each upstream layer. To
lock each layer to an exact commit:

```console
kas lock kas/forgefirm-glowforge.yml      # writes kas/forgefirm-glowforge.lock.yml
```

kas loads the lockfile automatically on the next runs. The lockfile is
committed. Refresh it only when you decide to.

### Build-time facts

- The kas configuration sets `ACCEPT_FSL_EULA = "1"`. The i.MX6 BSP installs
  NXP firmware blobs (VPU, EPDC) under the NXP firmware EULA. The package
  `firmware-imx-lic` puts the license text next to the blobs, at
  `/usr/share/licenses/firmware-imx/EULA`. Keep it there in each image that
  you redistribute. The SDMA firmware comes from `linux-firmware`, which has
  its own license package.
- Each `LICENSE` string in the layers (`meta-forgefirm`, `meta-glowforge-bsp`,
  `meta-openglow-core`) is an SPDX identifier. A recipe for a third-party
  component with more than one license (`wlconf`, `python3-gfhardware`)
  declares each license with a checksum of its license text.
- The kernel is `linux-fslc`. The device tree, the configuration fragment,
  and the layer patches are in
  `meta-openglow/meta-glowforge-bsp/recipes-kernel/linux/`. The bbappend
  header lists the patches, and `glowforge.cfg` describes the configuration.
  The bootloader recipe is `u-boot_2020.01.bb` in `recipes-bsp`.
- The parallelism in the kas configuration is for a build VM with 12 cores
  and 16 GB (`BB_NUMBER_THREADS = "8"`, `PARALLEL_MAKE = "-j 8"`). Increase
  it on a larger host. The download cache and the sstate cache are in the
  `forgefirm` checkout.

## Write the image to an SD card

```console
cd build/tmp/deploy/images/glowforge
sudo zcat forgefirm-image-glowforge.rootfs.wic.gz | dd of=/dev/sdX bs=1M
```

The bench boots the dev image from an SD card ([The bench](bench.md)). To
install ForgeFIRM on the factory eMMC, use the
[installation instructions](https://github.com/ScottW514/forgefirm/blob/master/INSTALL.md).
The installer puts ForgeFIRM in the unused A/B slot, and it archives the
factory firmware first.

## Build one component

The recipes build the components. For fast iteration on one component, you
have two options:

- Bump its pin for each iteration ([Release flow](release-flow.md)).
- Add a local, untracked `externalsrc` bbappend that points to a working
  checkout. Never commit it. If you do, released images no longer agree
  with the pins.

The sections below are the builds of the components outside Yocto.

### grblHAL-glowforge

```sh
cmake -B build && cmake --build build      # host build: null-sink mode, for the tests
```

On a host, the driver runs in null-sink mode (no `GFSINK`). The host tests
and the CI harnesses use that build ([Test](testing.md)). The board binary is
a cross-compile with the i.MX6 toolchain. `scripts/bench/build-glowforge.sh`
in the `forgefirm` repository does this in the Yocto build environment, with
the toolchain of the recipe. This is the production controller build. The
controller is a userspace program. To deploy a new binary, replace the binary
on the board. An image flash is not necessary.

Under the ForgeFIRM image, the driver runs as a supervised child of
forgectrl. It receives `/dev/glowforge` as an inherited file descriptor
(`GF_PULSE_FD`). Standalone, it opens the device itself:

```sh
GFSINK=/dev/glowforge grblHAL_glowforge -p 23 -e /data/EEPROM.DAT
```

| Variable | Meaning |
|---|---|
| `GFSINK` | The pulse device. Unset = null-sink test mode. |
| `GFSINK_RATE` | The machine tick. Default 28160 Hz, the travel-move tick of the factory firmware. Accepted range 1000 to 165000. |
| `GFSINK_DEPTH_MS` | The queue depth of the shipper. Default 200 ms, which is the feed-hold latency. Minimum 20. Maximum: half the stream ring at the selected rate. |
| `GFSINK_LEAD_MS` | The lead of the producer over the ship cursor. Default 10 ms. The per-run debug line reports the measured minimum margin against it. |
| `GFSINK_DUMP` | Null-sink mode only. The file that receives the pulse stream. The CI harnesses read it. |
| `GF_PULSE_FD` | The inherited pulse-device descriptor, under the supervision of forgectrl. |

The driver reports a value that is out of range and uses the default. The
`FFLOG_*` variables are the same as for forgectrl (below).

### forgectrl

forgectrl builds with CMake. It links against ulfius, libjpeg, and zlib. The
target needs Linux with imx-media, the coda VPU driver, and v4l-utils
(`media-ctl`, `v4l2-ctl`). The `meta-forgefirm` recipe builds it for the
image and installs the sysvinit script from `init/`.
`scripts/bench/build-forgectrl.sh` in the `forgefirm` repository
cross-compiles it in the same way as the controller, with the toolchain
from the work directory of the recipe. After a clean, run `bitbake forgectrl`
to make that directory again.

```sh
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build
```

`.devcontainer/` packages the host build for VS Code (Dev Containers, with
Docker or Podman). The container is Ubuntu 24.04 with the build
dependencies. The build and the CI unit tests run in it. The task "panel: dev
server" starts the dev server of the panel when the folder opens, and port
8081 is forwarded. Interactive shells in the container export `.env`. Thus
the bench tools see `GF_HOST` and `GF_TOKEN` too.

| Variable | Default | Purpose |
|---|---|---|
| `FORGECTRL_PORT` | 8080 | The HTTP port |
| `FORGECTRL_STREAM_Q` | 75 | The JPEG quality of the stream (1 to 100) |
| `FORGECTRL_STREAM_FPS` | unset | The frame-rate ceiling of the stream (frames/s). Unset or 0 = the sensor maximum |
| `FORGECTRL_LAMP` | 132 | The illumination level during capture (0 to 1023) |
| `FORGECTRL_NO_VPU` | unset | Force the libjpeg software encoder |
| `FORGECTRL_NO_NEON` | unset | Force the scalar demosaic |
| `FORGECTRL_NO_CACHED_BUFS` | unset | Force uncached capture buffers and a bounce copy |
| `FORGECTRL_NEON_CHECK` | unset | A one-shot NEON/scalar equivalence check (logged) |
| `FFLOG_LEVEL` | from the settings | Override the emit level (`off` to `debug`) |
| `FFLOG_STDERR` | unset | Echo the log lines to stderr, also when stderr is not a terminal (for harnesses) |
| `FFLOG_CONF`, `FFLOG_SOCK` | `/data/forgefirm.conf`, `/dev/log` | The settings file and the syslog socket (for host tests) |

#### Work on the control panel

The panel is a plain static page under `src/ui/`:

- `index.html`
- `theme.css`: the OpenGlow theme. Each color is a token, for light and
  dark, mapped onto the component variables of Bootstrap.
- `help.js`: the help text, one entry for each "?" button, each with its
  link to the documentation.
- `forms.js`: the shared dirty set, the save bar, the tab guard, the theme
  toggle, and the toasts.
- `panel.js`: the tabs, the telemetry rendering, and each action.
- `vendor/`: Bootstrap, pinned, with its license. There are no external
  assets and no build tools other than CMake.

The build bundles these files into one self-contained page, gzips it, and
embeds the compressed bytes in the daemon (`src/ui/embed.cmake`, run by
CMake). The bundled page also lands in `build/ui/index.html`. The daemon
decompresses the page once, at the first request, and puts the token in it.
Thus the page that ships is one plain response. The page is compressed in
the binary because the rootfs is raw ext4: bytes in `.rodata` are bytes on
the image.

`tools/devserver.py` (Python 3, standard library only) serves the files as
they are, with live reload. The browser sees the real file names and line
numbers. The open tab reloads when you save a file under `src/ui/`. The
option `--bundle` serves the page inlined, in the same way as the daemon. The
API calls from the page go to one of two backends:

- **A real machine.** Set `GF_HOST` (an IP literal, with `:port` if the port
  is not 8080) and `GF_TOKEN` (the panel token, `/data/forgefirm/panel.token`
  on the machine). Put them in the environment, or in a git-ignored `.env`
  at the root of the repository. `.env.example` is the template, and the
  server reads the file again when it changes. The server embeds the token
  in the page in the same way as the daemon. It proxies the requests with the
  address-literal `Host` of the machine, and the MJPEG stream passes through.
  Thus the panel shows live data, and its actions reach the hardware.
- **The built-in mock** (`--mock`, or automatically without `GF_HOST`):
  in-memory settings, status, diagnostics, slots, logs, and a placeholder
  camera. The mock does the same token check as the daemon on the
  state-changing calls.

```sh
cp .env.example .env            # then fill in GF_HOST / GF_TOKEN
python3 tools/devserver.py      # http://127.0.0.1:8081
python3 tools/devserver.py --mock
python3 tools/devserver.py --dump > panel.html   # the bundled page
```

The page of the acceptance tool shares `theme.css` and the vendored Bootstrap
with the panel, byte for byte. `scripts/check-ui-vendor.py` in the
`forgefirm` repository does that check, and CI runs it ([Test](testing.md)).

### kernel-module-glowforge

The recipe builds the module against the kernel of the image, and the module
ships in the image. Do not build it by hand for the board. The
kernel-independent parts have host tests (`make -C tests check`). CI
cross-builds the module against linux-fslc 6.12 with the BSP overlay and the
patches applied ([Test](testing.md)). A `.ko` change is validated on the
image that ships it ([The bench](bench.md)). After an edit under the overlay
of the kernel recipe, the module loads only from a full image flash.

### The Python components

The recipes install `gfhardware` (with its `_cam` extension), the cloud
applications in `forgefirm-app/`, and `gfutilities` from the pinned
revisions. `gfutilities` is also on PyPI (`pip install gfutilities`). For
work on the emulator, install it from source with `pip install -e .`.
