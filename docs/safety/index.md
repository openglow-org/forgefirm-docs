---
title: Safety
---

# Safety

Read this page before you install ForgeFIRM and before you run a job. It is
short on purpose.

!!! danger "This is not the manufacturer's firmware"

    ForgeFIRM is community software that replaces the factory software in
    the machine. It is in development. It can have faults the factory
    firmware does not have, and it can fail in ways nobody has seen yet. Use of this software could seriously maim or kill
    you or others, and it may void your warranty. Use it at your own risk.

## What protects you, and what does not

The machine's own hardware still does the last-line work. The lid switches,
the interlock plug on a Pro, and the big button are wired so that the laser
cannot fire with the lid open, and cannot fire at all until a person presses
the button. ForgeFIRM keeps every one of those. On top of them it adds its
own checks: it waits for your press before the first cut of a job, it holds
the job when the coolant is not proven to be moving or is too warm, it ends
the job when the lid opens, and it watches for a fire and for a head crash.

The software checks are software. Treat them as help, not as a guarantee.
The fire watch catches a developed fire, not a small flame, and it is not a
fire alarm. A hold can fail to happen. After a fault the machine's idea of
where the head is can be wrong. The person in front of the machine is the
safeguard that has to work.

## Stay with the machine

- Stay present for the whole job and watch the material. Small flare-ups
  happen with some materials. A flame that keeps burning is a fire.
- Know how to stop before you start. Open the lid: the job ends at once.
  Press the button: the job pauses. Press Stop in your sender. Turn the
  machine off. If anything looks wrong, stop first and think second.
- Keep a fire extinguisher in reach, and know how you will open the lid and
  smother a flame.
- Vent the exhaust outdoors, always. The fumes are toxic and flammable.
- Know your material. Never cut PVC, vinyl, or any chlorinated plastic.
- Every job with a laser layer fires, however low the power is set. If the
  button lights and you did not expect it, press Stop.
- Read the messages. When the machine holds or refuses, the sender console
  and the control panel say why. Find the cause before you retry
  ([Troubleshooting](../usage/troubleshooting.md)).

## Do not bypass a safeguard

- Never defeat a lid switch or the interlock plug, never run with a cover
  off, and never change the safety wiring on the control board. The
  enclosure and the lid glass are your eye protection.
- Never tape, wedge, or wire the button. The press is your consent, once
  per job.
- Do not turn a cooling gate off unless you understand what you give up.
  The settings that can do it say so loudly: a flagged value, a banner on
  the Status tab, and a line in the log at every job start. Some protections
  no setting can reach ([Cooling and fans](../usage/cooling-and-fans.md)).
- Do not work around an alarm or a hold without knowing its cause.
- Do not run a build that did not come from this project.

## What to expect from the safeguards

- **The button, before the first cut.** The big button lights white and the
  machine waits for you to press it. One press covers one job. A long pause
  or an idle wait relocks the laser, and the next cut asks for the press
  again ([GRBL mode](../usage/grbl-mode.md#arming-the-button-press-is-part-of-every-job),
  [Cloud mode](../usage/cloud-mode.md#pause-cancel-and-park)).
- **The button, during a job.** A press pauses the job. Another press
  resumes it.
- **The lid and the interlock.** Opening the lid, or the interlock loop on a
  Pro, during a job ends the job. The head returns to where the job started,
  and the next job asks for the button again. Opening the lid does not stop
  a jog: a jog runs with the lid open, and the beam is blocked in hardware.
- **Cooling.** The machine holds a job, or refuses to start firing, when the
  coolant is not proven to be moving, is too warm or too cold, when a fan is
  not moving air, or when it sees a flame or a head bump. It tells you which
  ([Cooling and fans](../usage/cooling-and-fans.md#quick-reference-what-the-machine-does-when)).
- **A crash of the software.** If the program that controls the machine
  crashes, the machine stops motion and locks the laser on its own, then
  restarts that program.

How the hardware chain and the software checks work is in the Technical
section: [The safing chain](../technical/machine/safing-chain.md),
[The grblHAL driver](../technical/forgefirm/grblhal-driver.md),
[The cooling engine](../technical/forgefirm/cooling-engine.md), and
[The kernel module](../technical/forgefirm/kernel-module.md).

## Legal

Modifying the machine may have legal and regulatory ramifications. It is up
to you to adhere to the laws and regulations that apply where you are
([Installation](../install/index.md#regulatory-and-legal)).
