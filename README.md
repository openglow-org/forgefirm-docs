# ForgeFIRM documentation

The source of [docs.forgefirm.org](https://docs.forgefirm.org/), the
documentation for [ForgeFIRM](https://github.com/ScottW514/forgefirm), open
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

`zensical build` writes the site to `site/`. The build is strict: a broken
link fails it.

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
