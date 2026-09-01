---
title: This site
---

# This site

This site is the documentation of ForgeFIRM, and it is the source of truth
for the project. Each fact has one home, here. A repository README is an
index card that points here. The source of the site is the
[`forgefirm-docs`](https://github.com/ScottW514/forgefirm-docs) repository.
[Zensical](https://zensical.org/) builds it from `mkdocs.yml`, and GitHub
Pages publishes it at `docs.forgefirm.org`.

## Where each subject goes

| Section | Contents |
|---|---|
| Home | What ForgeFIRM is, the two modes, the supported hardware, where to go next. |
| Safety | One page: this is not the manufacturer's firmware and it can have faults; stay with the machine; do not bypass a safeguard; what to expect from the safeguards, in plain words, with links to the Usage pages. The mechanisms live in Technical, the operator's view of each safeguard in Usage, and the regulatory and legal notes in Installation. |
| Installation | What you need, the replacement install with the factory firmware archived first, the procedure, the way back to the factory firmware, updates, recovery. |
| Usage | First boot, the control panel, the modes, GRBL mode and senders, cloud mode, homing, cameras, cooling and fans, settings, logs, diagnostics, troubleshooting. |
| Technical: the machine | The Glowforge machine as built: the control board, the connectors, the safing chain, the motion hardware, the step engine, the laser, the sensors, coolant and airflow, the cameras, the buses, boot and storage, the factory firmware, the cloud protocol, the identity. |
| Technical: ForgeFIRM | How ForgeFIRM works with that machine: the kernel module, the pulse-feeder contract, the grblHAL driver, forgectrl, the cooling engine, the video pipeline, cloud mode, homing, install and update, logging, the image and BSP, release acceptance. |
| Developers | This section. |

The site is assembled section by section. Until a section lands, its
documentation stays with the code, and the pages here link to it on GitHub.
Those links are rewritten to site links when the pages land. One document
stays in the code on purpose: the campaign log, `forgefirm/docs/CAMPAIGN-LOG.md`.
It is dated and append-only, and the site describes the present. The
Developers section links to it.

## The rules

1. **One home.** A fact lives on the site, or it does not exist.
2. **Contracts move too.** The kernel feeder contract, the machine-services
   contract, the cloud-mode document, and the acceptance contract are site
   pages. The interface lint catches drift.
3. **The currency rule.** A change carries a documentation commit when it adds,
   removes, or renames an interface, or when it corrects a measured fact.
   The interfaces: a sysfs attribute, an HTTP route, a settings key, a
   G-code or `$` setting.
4. **A moved document is deleted.** No stub and no redirect stays at the old
   path. The only forward reference is the link from each repository README
   to the site.
5. **Present tense only.** The site describes the machine and the firmware
   as they are. Dated records go to the campaign log.
6. **Public hygiene and Simplified Technical English.** No identity of the
   bench machine, no workstation paths, no history narrative, American
   English, no em dashes, ASD-STE100 ([Contribute](contributing.md)).
## Preview the site

```sh
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
zensical serve                # http://127.0.0.1:8000/
```

Or open the repository in VS Code and select **Reopen in Container**. The
dev container in `.devcontainer/` has the generator. The task "docs: serve"
starts the preview server on port 8000 when the folder opens. The port is
forwarded, the browser opens on it, and each save rebuilds the site and
reloads the page. Docker or Podman, either one runs it.

`zensical build` writes the site to `site/`. The build is strict: a broken
link fails it. The version of Zensical is pinned in `requirements.txt`, in
the same way as a recipe pin. Bump it on purpose.

## Checks

Each pull request runs `zensical build` and two scripts. A red check blocks
the merge.

- `scripts/check-style.py`: the house rules that a machine can enforce.
  It checks for American English (a fixed list of British spellings) and
  for em dashes. It also checks for paths from anyone's workstation: drive
  letters, WSL mounts, home directories. It checks for bench-machine
  identity too: private IP addresses, root logins that name a host. A line can carry the marker
  `<!-- style: ignore -->` to be skipped, for the rare quotation that must
  stay as written.
- `scripts/check-interfaces.py`: each sysfs attribute, HTTP route, and
  settings key in the firmware has a page anchor here. It is a placeholder
  until the Technical section lands. Then it checks out the kernel module
  and forgectrl at the revisions that `mkdocs.yml` declares. It extracts the
  names, and it fails on a name without an anchor.

Run them with `python scripts/check-style.py` and
`python scripts/check-interfaces.py`.

## Conventions

- Safety text goes in a `danger` admonition. Additional information goes in
  a `note`.
- A page that differs by controller mode uses content tabs, one for GRBL
  mode and one for cloud mode.
- Each Usage page opens with an admonition that links to the Safety section.
- Every diagram is Mermaid in a fenced block; the theme renders it. No
  ASCII art and no image of a diagram. Wrap the block in
  `<div class="diagram" markdown>`: on a phone the wrapper keeps the diagram
  at a legible width and scrolls sideways, instead of the theme shrinking it
  to fit. Set the width floor per diagram with
  `style="--diagram-min: 68rem"` (the default is 46rem; use 0 for a diagram
  that is narrow anyway). Keep labels to two or three short lines, keep a
  subgraph title short so that no arrow crosses it, and prefer a top-down
  layout with two columns for a diagram that must read on a phone without
  scrolling. Check a new diagram at 1400 px, 768 px, and 390 px, in both
  color schemes.
- Each measured number cites how it was obtained: a link to the campaign
  log.

## Publish

`deploy.yml` publishes `main` to GitHub Pages, but only while the repository
variable `DEPLOY_PAGES` is `true`. A Pages site is public, also from a
private repository. Clear the variable to stop the publication.

## Versions

The site has no versions until the first production release. The URL layout
is fixed now, so that the links you write today stay valid. `/latest/` is an
alias of the newest release, `/dev/` is `main`, and `/vX.Y/` is a release.
From the first release on, `main` publishes as `dev`, and a release tag
publishes `vX.Y` and moves the `latest` alias. Firmware on a machine needs
the documentation that agrees with it.

## The look

The site has the colors of the ForgeFIRM control panel. It has a navy
header with the OpenGlow wordmark, blue links, and laser red for the active
tab and the danger notices. It uses system fonts, in a light and a dark
theme. The tokens are in
`docs/assets/stylesheets/forgefirm.css`, and they mirror `src/ui/theme.css`
in forgectrl. Thus a color changes in both places or in neither. The wordmark
and the touch icon come from `overrides/`. The favicon is the own icon of the
community forum.
