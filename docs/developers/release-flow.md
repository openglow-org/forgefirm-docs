---
title: Release flow
---

# Release flow

The build is reproducible only when the recipe pins, the layer branches, and
the kas configuration move in the correct order. This page gives that order,
and then the release pipeline.

## Each source repository is pinned

Each recipe gets its component from GitHub at an exact `SRCREV`. There is no
`AUTOREV` anywhere. The `SRCREV` of a component, and the `PV` that moves with
it, are in `<recipe>-pin.inc` next to the recipe. Nothing else goes in that
file.

| Pin file | Layer |
|---|---|
| `recipes-forgefirm/forgectrl/forgectrl-pin.inc` | `meta-forgefirm` |
| `recipes-forgefirm/grblhal-glowforge/grblhal-glowforge-pin.inc` | `meta-forgefirm` |
| `recipes-forgefirm/forgefirm-app/forgefirm-app-pin.inc` | `meta-forgefirm` |
| `recipes-kernel/kernel-modules/kernel-module-glowforge-pin.inc` | `meta-glowforge-bsp` |
| `recipes-devtools/python/python3-gfhardware-pin.inc` | `meta-glowforge-bsp` |
| `recipes-devtools/python/python3-gfutilities-pin.inc` | `meta-openglow-core` |

The image manifest keeps `*-pin.inc` out of the layer content hash. Thus a
pin bump changes the acceptance fingerprint of that component only. It makes
the acceptance tests that cover the component necessary again, not the full
bench. A pin in a recipe body also builds, but it counts as a platform
change and makes a full acceptance campaign necessary
([Acceptance](acceptance.md)).

## The push order

When a source repository changes:

1. Push the source repository.
2. Bump its pin. BSP components are pinned in `meta-openglow`. ForgeFIRM
   components are pinned in `meta-forgefirm`.
3. Run `bitbake -c fetch <recipe>` to make sure that the pin resolves.

Two couplings cross the repositories:

- The CI of `grblHAL-glowforge` gets the laser harnesses from `forgefirm` at
  the head of `master`, unpinned. Push a harness change to `forgefirm` before
  the driver change that needs it.
- The page of the acceptance tool shares its theme and its vendored
  Bootstrap with the panel of forgectrl, byte for byte. Land a UI change in
  forgectrl first. Push it and pin it. Only then does the `forgefirm` CI
  check pass.

**This site joins the push order.** A change that adds, removes or renames an
interface, or corrects a measured fact, carries a documentation commit (the
currency rule, on [Contribute](contributing.md)). Push `forgefirm-docs` with
the change it documents, not later: the interface lint checks the site against
the revisions it declares, and the release pipeline tags the site with the
release.

`meta-openglow` is on its `scarthgap` branch (the Yocto layer convention).
Development occurs on the local sibling checkout, and `scarthgap` is pushed
as work lands. `kas lock` locks the upstream layers (poky, meta-openembedded,
meta-freescale, meta-freescale-distro). The lockfile is committed. Refresh
it only when you decide to.

## At release time

1. Set `FORGEFIRM_RELEASE` in
   `meta-forgefirm/recipes-forgefirm/images/forgefirm-release.inc` to the
   version being cut. That file holds the number and nothing else, and the
   manifest leaves it out of the layer content hash, so the bump is not a
   platform change and does not invalidate the campaign
   ([Acceptance](acceptance.md#domain-fingerprints-and-inheritance)). Set it whenever
   you like, before or after the campaign.
2. In `kas/forgefirm-glowforge.yml`, change `meta-openglow` from the
   local-sibling block to the pinned-remote block (the commented block in
   the file).
3. Refresh `kas lock`.
4. Tag `forgefirm` with `v<version>`. The release version belongs to ForgeFIRM
   alone: the components (`forgectrl`, `grblHAL-glowforge`,
   `kernel-module-glowforge`, `python3-gfhardware`, `Glowforge-Utilities`) and
   the BSP layers keep their own version lines, and the pins record the
   revision of each that the release uses. The pipeline tags `forgefirm-docs`
   itself (below).
5. Commit the acceptance artifact that the bench exported for this image, as
   `releases/v<version>/acceptance.json` and `acceptance.md`. There is one
   directory for each release.
6. Make sure this site is current for the release and pushed (the currency
   rule, on [Contribute](contributing.md)). The pipeline tags it, and it
   refuses a documentation checkout with uncommitted changes.
7. Run the pipeline. Every Yocto build, the release included, runs on the
   build host ([Build](building.md)); nothing builds the images on a hosted
   runner.

### The documentation tag

Firmware on a machine needs the documentation that agrees with it, so
`forgefirm-docs` carries **the same tag as the release**. The pipeline makes
that tag itself, from the checkout `FORGEFIRM_DOCS_DIR` names (by default the
sibling one), and prints the command that pushes it.

The tag is made during the staging step and pushed **with** the release, never
before it: a documentation tag for a release that never shipped is worse than
no tag. `FORGEFIRM_DOCS_SKIP=1` releases without one, loudly, and is never the
default.

## The pipeline: `scripts/release.sh`

`release.sh` runs on the Yocto build host.

```
release.sh <version> [--publish]   the full release: gates, build, pack, sign,
                                   checksums, stage, and the publish command
release.sh --dev                   build and pack a dev-signed .fw for the
                                   upload path of the panel; no staging
```

| Variable | Meaning |
|---|---|
| `FWUP` | The host `fwup` for the pack step. Default: `fwup` on `PATH`. |
| `FWUP_COMPAT` | A factory-era fwup 0.14.2 binary. When set, the script verifies the packed archive with it (raw-format key). This replicates the factory-compatibility guarantee. |
| `FORGEFIRM_SIGNING_KEY` | The private key for release mode. Required, with no default, so that the key choice is always deliberate. |
| `FORGEFIRM_DEV_KEY` | The private key for `--dev` mode. Required for `--dev`. |
| `RELEASE_STAGING_DIR` | The directory for the staged release assets. Default: `<repo>/release-staging`. |
| `FORGEFIRM_ACCEPTANCE_SKIP` | `1` bypasses the acceptance gate. The script prints a loud warning, attaches `NO-ACCEPTANCE.txt` in place of the acceptance artifact, and publishes the release as a prerelease. This is never the default. |
| `FORGEFIRM_SOURCE_SKIP` | `1` builds the release without the source bundle. The licenses of the software in the image make source necessary, so this is never the default. |
| `FORGEFIRM_DOCS_DIR` | The `forgefirm-docs` checkout to tag with this release. Default: the sibling checkout. |
| `FORGEFIRM_DOCS_SKIP` | `1` releases without tagging the documentation. Never the default. |

The script runs its gates, builds both images, packs and signs
`forgefirm.fw`, stages the assets with `sha256sums.txt`, and prints the
`gh release create` command. The gates:

- **The version contract.** `<version>` must equal `FORGEFIRM_RELEASE` in
  `forgefirm-image.bb`, `/etc/forgefirm-version` in the built rootfs
  (`v<version>`), the `.fw` meta-version, and the release tag `v<version>`.
- **The rootfs size**, against the 200 MiB slot: a warning at 170 MiB, a
  failure at 195 MiB.
- **The installer key.** The public key in the installer must agree with the
  signing key.
- **The factory-era verification.** The packed archive must verify with
  fwup 0.14.2.
- **The acceptance gate.** `scripts/acceptance-gate.py` computes the
  fingerprint of each catalog test again, from the manifest in the release
  rootfs. The recorded PASS in the committed artifact must agree.
- **The source bundle.** Each recipe of the image whose license makes
  source necessary must have its source in the bundle (see below).
- **The documentation.** A `forgefirm-docs` checkout must exist and be
  clean. The pipeline tags it with the release version.

A problem in a gate stops the script before the signature.

The installer and the update manager of the panel download the assets by
these exact names:

```
forgefirm.fw
sha256sums.txt
forgefirm-image-glowforge.rootfs.wic.gz
acceptance.json
acceptance.md
```

The release carries one asset more, `forgefirm-source-v<version>.tar.gz`.
It is for a person, and no machine downloads it.

`sha256sums.txt` covers every other asset, the source bundle included. With
the acceptance gate skipped, `NO-ACCEPTANCE.txt` takes the place of the two
acceptance files and the release is a prerelease.

## The source bundle

A release publishes the source of the software that it installs. The
release build merges the overlay `kas/source-bundle.yml`, which turns on
the Yocto archiver. The build then writes the source of each recipe beside
the image, at `build/tmp/deploy/sources/`. The overlay adds tasks only. It
adds no file to the root filesystem and changes no component, so the image
manifest and thus the acceptance result are the same with the overlay and
without it ([Acceptance](acceptance.md)).

The overlay archives the upstream source as upstream publishes it
(`ARCHIVER_MODE[src] = "original"`), the patches that the recipe applies
with the `series` file that gives their order, and the recipe with its
includes. A recipe that gets its source from git is archived as a tar of
the checkout at the pinned revision. `COPYLEFT_LICENSE_INCLUDE` in the
overlay holds the license families that make source necessary, and
`COPYLEFT_PN_INCLUDE` names the ForgeFIRM components, which are MIT and
travel with the release too.

`scripts/source-bundle.py` packs the bundle:

```
forgefirm-source-v<version>.tar.gz
  README.md                       what the archive holds, and how to build again
  SOURCES.txt, MANIFEST.json      each recipe of the image with its archive
  sources/                        the source of each recipe
  licenses/                       both license manifests, and the license texts
  metadata/                       the kas configuration, the layer revisions,
                                  the ForgeFIRM layers, the image manifest
  sha256sums.txt                  the checksum of every file above
```

What the bundle must hold comes from the image, not from a list in the
script: the two license manifests that the build writes,
`license.manifest` (each package of the root filesystem) and
`image_license.manifest` (the kernel, the device tree and the boot
loader). Each recipe in them whose license is in the include list must have
an archive. A recipe with no archive stops the release, so a package cannot
reach a machine with its source left behind. The script names the recipe
and its license when it stops.

The bundle stays under the 2 GiB limit of a release asset of GitHub. The
script warns at 1.5 GiB and stops at 2 GiB.

To pack a bundle outside the release pipeline, run the pass and the packer
by hand:

```
cd forgefirm
python3 scripts/source-bundle.py <version> --build
```

The maintainer keeps the production release key offline. The installer
embeds its public key. Thus releases are signed with that key only. The
archive format is compatible in both directions. An archive from a modern
fwup applies with the factory-era 0.14.2. A modern fwup verifies and applies
the `.fw` of the factory. `scripts/mkfw.sh` is the packer that
`release.sh` calls. The format and the invariants of the update system are
in
[Install and update](../technical/forgefirm/install-and-update.md).

## The documentation

This site has no versions until the first production release. After that
release, `main` publishes as `dev`. A release tag publishes `vX.Y` and moves
the `latest` alias. The URL layout (`/latest/`, `/dev/`, `/vX.Y/`) is fixed
now, so that the links you write today stay valid ([This site](docs.md)).
