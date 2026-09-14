---
title: This site
---

# This site

This site is the documentation of ForgeFIRM, and it is the source of truth
for the project. Each fact has one home, here. A repository README is an
index card that points here. The source of the site is the
[`forgefirm-docs`](https://github.com/openglow-org/forgefirm-docs) repository.
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

Every fact is here. No document outside this site holds project
documentation: the status document and the dated bench record that once did
are retired, and what they carried is on these pages. The record of how a
result was obtained lives in the commit that carried it
([Contribute](contributing.md)).

## The rules

The house rules for what goes on a page and how it is written are on
[Contribute](contributing.md), under "Documentation". Two more are about the
site's own shape:

1. **Contracts are pages, not files in a repository.** The kernel feeder
   contract, the machine-services contract, the cloud-mode document and the
   acceptance contract are site pages. The interface lint catches drift
   between a page and the code it describes.
2. **A moved document is deleted.** No stub and no redirect stays at the old
   path. The only forward reference is the link from each repository README
   to the site.
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
- `scripts/check-interfaces.py`: every interface the firmware exposes is
  named on this site. It reads the source revisions declared in `mkdocs.yml`
  under `extra.sources`, extracts the interfaces at those revisions, and
  fails on one the site does not name.

Run them with `python scripts/check-style.py` and
`python scripts/check-interfaces.py`.

### The interface lint

Moving the contracts onto this site created exactly one risk: a page can
drift from the code it describes. This lint is the answer to it, and it has
the same shape as the acceptance system's coverage lint: a currency rule
with a check behind it.

It extracts three kinds of interface:

| Interface | Where it is declared |
|---|---|
| sysfs attributes of `glowforge.ko` | `src/uapi/glowforge.h`, the module's UAPI header |
| the HTTP routes of forgectrl | the route table in `src/main.c` |
| the machine settings keys | the validated-key table in `src/main.c` |

A name counts as documented when the site names it. An attribute may be
written bare or with its group (`pic/lid_ir_1`). A route must match whole, so
a mention of `/cool/status` does not document `/status`. A route parameter
written `:id` in the code matches `<id>` in prose.

**The sources.** The lint reads a sibling checkout when one exists, at the
revision `mkdocs.yml` declares, so it runs offline for a developer. Without
one, or when that revision is not in the local object store, it clones the
repository. `--worktree` reads the sibling checkout as it stands, which is
what to use while an interface change and its documentation are both still
uncommitted.

**Bump the declared revisions alongside the recipe pins.** A revision that
lags means the lint is checking an interface set the machine no longer has.

If the lint reports that it extracted no interfaces of some kind, the
declaration it reads has moved. Fix the extractor, never the expectation.

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
