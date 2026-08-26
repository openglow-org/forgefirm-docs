---
title: Roadmap
---

# Roadmap

ForgeFIRM has no public release yet. The machine works in both controller
modes, the full stack is hardware-validated, and the acceptance campaign has
passed on a pin-file image. Until that release, the open work is tracked in one place:
["Next work" in BRINGUP.md](https://github.com/ScottW514/forgefirm/blob/master/docs/BRINGUP.md#next-work),
the status document of the project. That list is the authority. This page
takes its role over with the first production release.

The headline items on that list:

- **The first signed release.** The acceptance export from the bench,
  `scripts/release.sh`, the kas flip to the pinned-remote BSP, and the first
  GitHub release ([Release flow](release-flow.md)).
- **Laser commissioning.** The hardware button latch across the gaps between
  motion bursts in a job, and the flow-check behavior from a warm baseline
  under real laser heating.
- **Low-temperature gates and warm-up**, and **TEC handling** as a setting,
  because the TEC output has no readback.
- **The fire watch (lid IR).** The gate stays disabled until it is
  lamp-aware.
- **Limit-switch homing.** The second homing method.
- **Cameras.** First light on an 8 MP (OV8856) machine, for which the full capture path is written but untested.
- **A head crash and rail-contact detector**, measured on the bench.
- **Gapless pause and resume in GRBL mode**, on the pattern that cloud mode
  already has.
- **The remaining polish of the shared machine services**, and the recovery
  refresh of the update system.
