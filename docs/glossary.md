---
title: Glossary
---

# Glossary

The words this site uses in a particular way, and the acronyms it does not
spell out every time. Acronyms expand on hover wherever they appear.

## The machine

**Bench reference**
: The one machine every measurement on this site was taken on, unless the
  page says otherwise: a Glowforge Basic built in late 2017. A measurement is
  never a specification
  ([The bench reference](technical/machine/index.md#the-bench-reference)).

**Head**
: The print head: the lens and its carriage, the air assist, the beam
  detector, the accelerometer, and a small microcontroller that answers over
  I²C. Its presence is that microcontroller answering, never the
  head-attention line.

**Lid switches, interlock, button**
: The three physical inputs the hardware safing chain reads. Both lid
  switches in series are the lid term; the interlock is the remote lockout
  loop, brought out on a Pro; the button is the operator's consent
  ([The safing chain](technical/machine/safing-chain.md)).

**OK_2_FIRE**
: The hardware chain's verdict that the machine may emit. `FIRE ∧ OK_2_FIRE`
  is `LASER_ON`, and `LASER_ON` is never a bare processor pin.

**The 40 V rail**
: The motor rail that feeds the stepper drivers. It stays up while the
  machine is on, because the drivers can latch into an unserviceable state on
  a glitch ([Motion hardware](technical/machine/motion-hardware.md#the-40-v-motor-rail)).

## Motion and the step stream

**Pulse file**
: A precomputed byte stream, one byte per machine tick, that the factory
  service sends and the machine plays. It opens with a header of
  4-character tags ([Factory firmware](technical/machine/factory-firmware.md)).

**Machine tick**
: The fixed rate at which the hardware timer consumes pulse bytes. Speed is
  the density of step bits across bytes, never a change of tick.

**Ring**
: The pulse buffer in reserved memory that the playback engine reads from.
  GRBL mode streams into a small window of it; cloud mode preloads
  ([The step engine](technical/machine/step-engine.md#the-ring-and-two-ways-to-fill-it)).

**Underrun**
: The ring ran dry while a program was playing. Motion stops instantly and
  the position is no longer trusted.

**Backtrack**
: Replaying the ring backward from a controlled stop, with the beam off, so a
  resume can lead back in over ground already cut. Bounded by the retained
  history the writer leaves behind the play head.

**Anchor**
: The reference that turns the kernel's step counters into machine
  coordinates, written at a completed homing. Anything that invalidates
  position drops it.

**Envelope**
: The operating limits a job carries in its pulse header: fan duties,
  temperature ceilings, tach floors, accelerometer thresholds. A header can
  tighten a local limit for its job and never loosen one.

## The laser

**Armed window**
: The per-job period in which the beam may fire. It opens only on the
  operator's physical button press and closes at program end, on a sender
  change, after the disarm grace, or on any fault
  ([The armed window](technical/forgefirm/grblhal-driver.md#the-armed-window)).

**The latch**
: The kernel's laser lockout. Locked by default, and every close of the pulse
  device locks it again. It puts the fire line beyond the reach of the
  playback engine.

**Fire gate**
: A condition that blocks emission without stopping the machine: a coolant
  fault, an over-temperature, a fan below its floor, a flame or crash
  reading.

**Density**
: The dose model. Every pulse fires at full power and the commanded level
  sets how many ticks of each period fire, so no level lands in the tube's
  dead band ([The laser](technical/machine/laser.md#what-the-tube-does)).

**Verdict**
: The cooling engine's published answer to "may the laser fire right now",
  which the running controller reads and enforces. A missing or stale verdict
  is a bad verdict ([The verdict file](technical/forgefirm/cooling-engine.md#the-verdict-file)).

**Hunt**
: The lens focus sequence the Glowforge service drives. It references Z
  against the hall sensor in the head.

## Software and the build

**Broker**
: The daemon's single, exclusive hold on the pulse device. Controllers
  inherit the file descriptor, so a handover never closes the device or
  cycles the motor rail
  ([Pulse-device ownership](technical/forgefirm/forgectrl.md#pulse-device-ownership)).

**Dead man**
: A hold that safes the machine when its holder disappears. The kernel's
  fires on the final close of the pulse device; the supervisor covers a
  controller's death; the cooling engine covers a controller's hang.

**Slot**
: One of the two 200 MiB root filesystem partitions on the internal storage.
  ForgeFIRM installs into the one that is not running, and a boot selection
  chooses between them
  ([Boot and storage](technical/machine/boot-and-storage.md)).

**Pin**
: The exact source revision at which a recipe fetches a component. A commit
  changes nothing on a machine until its pin moves
  ([Release flow](developers/release-flow.md)).

**Campaign**
: One run of the release acceptance catalog against one image. A release is
  signed only when a campaign authorizes the rootfs it was built from
  ([Acceptance](developers/acceptance.md)).

**Fingerprint**
: The hash that decides whether a recorded test result still applies to a new
  build: the files the test covers, the platform identity, and the test's own
  implementation.

**Drill**
: A bench procedure run against a real machine, usually with the operator
  present.

**Null sink**
: The driver built without a pulse device, so the real core, planner and
  stream code run on a workstation and the laser path can be tested without
  hardware ([Test](developers/testing.md#the-null-sink-controller)).
