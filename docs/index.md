---
title: Home
---

# ForgeFIRM

Open firmware for Glowforge brand CNC lasers. ForgeFIRM replaces the
cloud-dependent factory software on the **stock control board**, with no
hardware modification, and gives the machine a local controller, a local web
control panel, and a standard Grbl interface.

!!! danger "In development, not yet released"

    **ForgeFIRM has no public release, yet.**  Nothing here is installable.  
    The documentation describes the firmware as it is being built 
    and validated on the bench. It is here to be read, not followed.  
    The first public release is expected in September 2026. If you are interested 
    in being an early tester, please reach out to the developer.  

## What it does

**Two controller modes, selected in the web panel and switchable while the
machine is idle:**

**GRBL mode**: [grblHAL](https://github.com/grblHAL) runs on the machine and
  speaks Grbl 1.1 over TCP port 23, so LightBurn, UGS, cncjs, etc... drive the
  laser directly. Motion runs on the board's own hardware step engine (SDMA +
  EPIT), fed live by a local planner. M3/M4 dynamic laser power, coolant-flow
  verification, over-temp holds, and an operator button press to arm the laser
  for each job.

**Cloud mode**: The machine presents itself as a stock Glowforge to the
  Glowforge web service, so the phone and web apps work as they always did.
  Optional, and off by default. GRBL mode jogs and cuts without it; the one
  GRBL-mode function that still reaches the Glowforge service is
  camera-referenced homing (below), until limit-switch homing lands.

A **web control panel**: Machine status and position, coolant
  and fan telemetry, safety-switch states, live camera stream, machine settings, hardware diagnostics, firmware updates, and boot-slot management.

**Camera-referenced homing**: `$H` from any sender runs the factory-style
  camera homing cycle through the Glowforge service (a Glowforge account and a
  live service session are required for `$H`; everything else in GRBL mode
  runs without them).

## Hardware

The control board is common to Glowforge Basic, Plus, and Pro. The 5 MP
(OV5648) camera modules are fully supported and hardware-validated. The 8 MP
(OV8856) modules found in "HD" units have a complete capture path, with the
kernel patches, device tree, and sensor-aware capture profile they need all in
the build, but it has never run on an 8 MP machine, so treat it as untested.

## What this costs

ForgeFIRM is free in both senses: free as in beer, free as in speech. All of
it is public and released under MIT and GPL licenses. Read it, build it, 
change it, use it, pass it on.

The work happens in public, including the parts that don't work yet, which
are written up with more candor than flatters anyone.
No paid tier. No license key, no subscription, no activation, no Pro edition,
no feature parked behind a paywall. Nothing is held back for a rainy day,
mostly because there's no plan for a rainy day.

If someone offers to sell you this firmware, the licenses allow it and
nobody's calling it theft. Just note that you'd be paying for something
that's given away. Get it from the source. Same price everywhere, and here 
you get to read what you're running.

## Safety

**These machines contain a CO~2~ laser: it burns, blinds, and starts fires.**
Never defeat the lid switches or interlock. Never leave a running job
unattended, and keep a fire extinguisher within reach.

**This is experimental software. Use of this software could seriously maim or
kill you or others, and voids your warranty. Use it at your own risk.**

## Where the rest lives, for now

This site is being assembled. Until each section lands here, the
documentation stays with the code:

- [Installation](https://github.com/ScottW514/forgefirm/blob/master/INSTALL.md)
- [Build](developers/building.md), for developers
- [Connecting LightBurn](https://github.com/ScottW514/forgefirm/blob/master/docs/LIGHTBURN.md)
- [Motion and the laser](https://github.com/ScottW514/forgefirm/blob/master/docs/MOTION.md)
- [Cooling and airflow](https://github.com/ScottW514/forgefirm/blob/master/docs/COOLING.md)
- [The cameras and the video stream](https://github.com/ScottW514/forgefirm/blob/master/docs/VIDEO.md)
- [How the laser safing works](https://github.com/ScottW514/forgefirm/blob/master/docs/SAFETY.md)
- [Release acceptance](developers/acceptance.md), for developers
- [Community support](https://community.openglow.org)
