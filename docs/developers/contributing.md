---
title: Contribute
---

# Contribute

The work occurs in public, and these are the rules that the project holds
itself to. They are short. Each one exists because it protects something:
a person, a machine, or a fact.

## Safety first, and in that order

- The hardware chain is the safety boundary. Software only adds gates on
  top of it. `LASER_ON` is never a bare GPIO. The kernel laser latch is
  locked by default, and each close of the pulse device locks it again.
- Never defeat a switch, in hardware or in software, not even for a test.
- The order of work is absolute: emission and motion first, robustness and
  hygiene after. A change that touches emission or motion is reviewed for
  that before anything else.
- A change that can put energy where it was not commanded gets a regression
  test with the feature or fix, not after it.
- Position counters are not proof of physical motion. The head accelerometer
  is.

The safing chain itself is described in
[Safety](../safety/index.md).

## Proof before done

A feature or fix is not complete until it is proven. The order of preference:

1. A host test that runs in CI ([Test](testing.md)). The null-sink
   controller build lets the laser-stream and armed-window harnesses run
   without hardware.
2. A bench drill on [the bench reference](../technical/machine/index.md#the-bench-reference),
   recorded in the commit message that carries the change.
3. Documented reasoning.

Also:

- Evaluate each change against the acceptance catalog, and keep the coverage
  maps current ([Test](testing.md), "Coverage currency"). A behavior change
  with no catalog consequence gets a sentence of justification in the commit
  message.
- Push a source repository before you bump its pin. Verify the pin with
  `bitbake -c fetch` ([Release flow](release-flow.md)).
- Kernel and BSP changes ride one image flash, in a batch. Validate a `.ko`
  or overlay change on the image that ships it ([The bench](bench.md)).
- Remove what you put on the bench, in the same session ([The bench](bench.md),
  "Bench hygiene").

## Documentation

- **One home.** A fact lives on this site, or it does not exist. A
  repository README says what the repository is, how to build and test it,
  and where the documentation is. Nothing else.
- **Present tense, present state.** The site describes the machine and the
  firmware as they are. There is no history narrative and no status document:
  what was done, how it was proven, and what it replaced belong in the commit
  message that carried it, where the change and its record stay together. Open
  items (bugs, feature requests, enhancements) are tracked as GitHub issues
  once the repositories accept them; this site has no roadmap page.
- **The currency rule.** A change carries a documentation commit when it adds,
  removes, or renames an interface, or when it corrects a measured fact. The
  interfaces are a sysfs attribute, an HTTP route, a settings key, and a
  G-code or `$` setting. The lint that catches drift is on
  [This site](docs.md#checks).
- **Cite the measurement.** A measured fact says how it was obtained, and on
  what: unless the page says otherwise, a measurement on this site was taken
  on [the bench reference](../technical/machine/index.md#the-bench-reference),
  and it is written so a reader can tell a measurement from a specification.
- **Public hygiene.** No paths from anyone's workstation. No identity of the
  bench machine. American English. No em dashes.
- **Simplified Technical English.** All text follows ASD-STE100. That means short
  sentences, one instruction for each sentence, the active voice, and the
  imperative in procedures. It also means the approved words in their
  approved meanings, and consistent technical names. Warm and direct is good. A joke that
  shades a fact is not.

`scripts/check-style.py` in the documentation repository enforces the
mechanical parts ([This site](docs.md)).

## Code

- Comments and log text obey the same rules as the documentation: present
  tense, Simplified Technical English, no history, no workstation paths.
- Each new file carries an `SPDX-License-Identifier` line under the license
  of its repository ([Developers](index.md), "Licenses").
- A fork of a third-party project (e.g. the grblHAL core) carries the minimum
  change and no rationale comments. The reasoning goes in the commit
  message.

## Where to talk

- The [community forum](https://community.openglow.org) for questions and
  bench reports.
- The issue tracker of the repository that holds the code, for defects and
  proposals.
