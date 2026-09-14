# ForgeFIRM documentation

The source of [docs.forgefirm.org](https://docs.forgefirm.org/), the
documentation for [ForgeFIRM](https://github.com/openglow-org/forgefirm), open
firmware for stock Glowforge lasers. Everything the project knows lives here;
the code repositories keep a README that points back.

Built with [Zensical](https://zensical.org/) from `mkdocs.yml`, published by
GitHub Pages.

## Preview locally

```sh
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
zensical serve                # http://127.0.0.1:8000/
```

Or open the repository in VS Code and choose **Reopen in Container**. The
dev container in `.devcontainer/` carries the generator, and the "docs:
serve" task starts the preview server on port 8000 when the folder opens:
the port is forwarded, the browser opens on it, and every save rebuilds the
site and reloads the page. Docker or Podman, either runs it.

`zensical build` writes the site to `site/`. The build is strict: a broken
link fails it.

## Checks

Every pull request runs the strict build and two lints, and a red check blocks
the merge:

```sh
python scripts/check-style.py        # American English, no em dashes, no bench identity
python scripts/check-interfaces.py   # every firmware interface is named on the site
```

[This site](https://docs.forgefirm.org/developers/docs/) describes both, and
where each subject goes.

## Contributing

[AGENTS.md](AGENTS.md) carries the rules for this repository and for the
project: safety ordering, proof before done, the push order, and the writing
rules. They apply to human contributors too.

## Look

The site wears the same colors as the ForgeFIRM control panel: navy header
with the OpenGlow starburst wordmark, blue links, laser red kept for the
active tab and the danger notices, system fonts, light and dark. The tokens
live in `docs/assets/stylesheets/forgefirm.css` and mirror forgectrl's
`src/ui/theme.css`, so a color changes in both places or in neither. The
wordmark and the touch icon come from `overrides/`; the favicon is the
community forum's own.

## Checks

Every pull request runs `zensical build` plus two scripts, and a red check
blocks the merge:

- `scripts/check-style.py`: the house rules that a machine can enforce.
  American English, no em dashes, no paths from anyone's workstation, no
  bench-machine identity.
- `scripts/check-interfaces.py`: every sysfs attribute, HTTP route, and
  settings key in the firmware has a page here. A placeholder until the
  Technical section lands.

Run them with `python scripts/check-style.py` and
`python scripts/check-interfaces.py`.

## Publishing

`deploy.yml` publishes `main` to GitHub Pages, but only while the repository
variable `DEPLOY_PAGES` is `true`. Pages sites are public even from a private
repository, so the variable stays unset until the site is ready to be seen.

## License

The text of this site is licensed
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The
firmware it describes carries its own licenses in its own repositories.
