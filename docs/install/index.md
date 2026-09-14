---
title: Installation
---

# Installation

This section tells you what you need, how ForgeFIRM replaces the factory
firmware, how the factory firmware is backed up and how you return to it, how
to update, and how to recover. Read [Safety](../safety/index.md) first, and
[Regulatory and legal](#regulatory-and-legal) before you install.

!!! warning "Beta"

    **ForgeFIRM is in beta.** Every release below 0.1.0 is a beta release.
    Expect problems, and expect frequent updates. Upgrade whenever a newer
    release is available ([Updating](updating.md)), and report what you find
    ([Community forum](https://community.openglow.org)). Releases come only
    from the project's GitHub releases page.

!!! danger "Experimental software"

    Use of this software could seriously maim or kill you or others, and
    may void your warranty. Use it at your own risk
    ([Regulatory and legal](#regulatory-and-legal)).

| Page | Contents |
|---|---|
| [Serial access](serial-access/index.md) | The console on the control board: the Micro-USB port of early machines, the OpenGlow serial adapter, or a soldered 1.8 V FTDI cable. |
| [Install](install.md) | The one-stage installer, run at the factory console, and the first boot. |
| [Back to the factory firmware](factory-restore.md) | The factory archive, and how to restore the factory firmware from it. |
| [Updating](updating.md) | Signed `.fw` releases and the update manager in the control panel. |
| [Recovery](recovery.md) | The recovery ladder and the factory recovery mode. |
| [Legacy migration](legacy-migration.md) | Upgrading from a legacy dual-partition install. |

## Regulatory and legal

Modifying the machine, including replacing its firmware, may have legal and
regulatory ramifications. It is up to you, the end user, to make sure that
you adhere to all laws, regulations, certifications, and insurance terms that
apply where you are. The project cannot advise you on them.

ForgeFIRM is free software under MIT and GPL licenses, and the text of this
site is CC BY-SA 4.0 ([Licenses](../developers/index.md#licenses)). There is
nothing to buy, and if someone offers to sell it to you, what you take home is
their build rather than this one: get it from the source
([What this costs](../index.md#what-this-costs)).

## What you need

- A stock Glowforge Basic, Plus, or Pro. The control board is common to all
  three, and nothing on it is modified.
- [Serial console](serial-access/index.md) access. The factory firmware does not
  offer SSH and does not support installing firmware that is not signed by 
  Glowforge, so the install runs at the console (login `root`, no password).
- About 300 MB free on `/data` (a factory machine has far more).
- Internet access on the machine for the standard flow. For an offline
  install, place a `forgefirm.fw` on `/data` beforehand and pass its path to
  the installer.
- A ForgeFIRM release that ships the `forgefirm.fw` asset (0.0.1 or
  later; every 0.0.x release is a beta).

## A replacement, with a way back

ForgeFIRM **replaces** the factory firmware. It is not a second system that
runs next to it. Before the installer writes anything, it archives the
factory firmware to `/data` (below), and you can restore the factory
firmware from that archive whenever you wish
([Back to the factory firmware](factory-restore.md)).

The install and every later update use the factory's own update mechanism:
the onboard storage (4GB eMMC) carries two 200 MiB rootfs slots, a signed `.fw` archive is
applied to the slot that is not running, the result is verified, and the
boot selection moves to it. Nothing is repartitioned, and the factory
`/data` partition (settings, credentials, logs) is untouched and keeps its
full factory size. The invariants that every flash path obeys are in
[Install and update](../technical/forgefirm/install-and-update.md); the
eMMC layout is in [Boot and storage](../technical/machine/boot-and-storage.md).

## The factory firmware is archived first

Before anything is overwritten, the installer archives **every** factory
firmware version on the machine, both rootfs slots and the recovery boot
partitions, to `/data/forgefirm/archive/`. A full offline factory restore
is therefore always possible, with no Glowforge cloud required. The archive
holds `factory-rootfs-<ver>.img.gz` for each factory version, `boot0.img`
and `boot1.img`, and a `manifest` with the slot versions, dates, and
checksums. A restore runs from the control panel
([Back to the factory firmware](factory-restore.md)).

## The first boot

After the install the machine boots into ForgeFIRM, and the serial console
prints the panel's addresses. Open `https://<ip>/`, accept the browser's
certificate warning once, and complete
the setup ([Setup](../usage/setup.md)). Root has no password
and works at the serial console only. SSH is off until you turn it on from
the panel, and it opens with the account the setup creates
([Install](install.md#after-the-first-boot)).
