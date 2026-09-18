---
title: Back to the factory firmware
---

# Back to the factory firmware

ForgeFIRM replaced the factory firmware on your machine. Before it wrote
anything, the installer archived every factory firmware version on the
machine to `/data/forgefirm/archive/`
([Installation](index.md#the-factory-firmware-is-archived-first)). This page
tells you how to restore the factory firmware from that archive, and how to
come back to ForgeFIRM afterward.

## Restore from the control panel

Open the System tab of the control panel and use **Factory restore**
([Updating](updating.md#factory-restore)). The source is **the archive on
`/data`**: offline, no Glowforge account needed, the firmware the machine ran
before ForgeFIRM. The factory image is written to the slot that is not
running, verified, and the boot selection is moved to it. Reboot when it
asks.

## Restore from the factory recovery mode

If ForgeFIRM does not boot, the factory recovery mode can install a
Glowforge `.fw` archive: hold the button at power-on and use the recovery
page ([Recovery](recovery.md#the-factory-recovery-mode)).

## What happens next

The machine is a factory machine again. The factory updater will update it
on Glowforge's schedule, and it will overwrite the slot ForgeFIRM occupied.
The `/data` partition is shared: your settings, credentials, and logs are
untouched, and ForgeFIRM's own files under `/data/forgefirm/` stay.

## Back to ForgeFIRM

Run the installer again from the factory console ([Install](install.md)). It
skips the archives it already has and writes ForgeFIRM to the slot that is
not running.
