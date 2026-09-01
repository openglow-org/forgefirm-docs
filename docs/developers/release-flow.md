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

`meta-openglow` is on its `scarthgap` branch (the Yocto layer convention).
Development occurs on the local sibling checkout, and `scarthgap` is pushed
as work lands. `kas lock` locks the upstream layers (poky, meta-openembedded,
meta-freescale, meta-freescale-distro). The lockfile is committed. Refresh
it only when you decide to.

## At release time

1. In `kas/forgefirm-glowforge.yml`, change `meta-openglow` from the
   local-sibling block to the pinned-remote block (the commented block in
   the file).
2. Refresh `kas lock`.
3. Tag each repository.
4. Prove self-containment: build from a fresh clone. The `yocto-cold-build`
   workflow in the `forgefirm` repository does this on a hosted runner. You
   dispatch it by hand. It builds the release image from a fresh checkout
   with `rm_work`. Then it publishes the artifact checksums, for a
   comparison with the release that you built locally. It never makes release
   artifacts.
5. Commit the acceptance artifact that the bench exported for this image, as
   `releases/v<version>/acceptance.json` and `acceptance.md`. There is one
   directory for each release.
6. Run the pipeline.

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
| `FORGEFIRM_ACCEPTANCE_SKIP` | `1` bypasses the acceptance gate. The script prints a loud warning. This is never the default. |

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

The maintainer keeps the production release key offline. The installer
embeds its public key. Thus releases are signed with that key only. The
archive format is compatible in both directions. An archive from a modern
fwup applies with the factory-era 0.14.2. A modern fwup verifies and applies
the `.fw` of the factory. `scripts/mkfw.sh` is the packer that
`release.sh` calls. The format and the invariants of the update system are
in
[UPDATE-SYSTEM.md](https://github.com/openglow-org/forgefirm/blob/master/docs/UPDATE-SYSTEM.md).

## The documentation

This site has no versions until the first production release. After that
release, `main` publishes as `dev`. A release tag publishes `vX.Y` and moves
the `latest` alias. The URL layout (`/latest/`, `/dev/`, `/vX.Y/`) is fixed
now, so that the links you write today stay valid ([This site](docs.md)).
