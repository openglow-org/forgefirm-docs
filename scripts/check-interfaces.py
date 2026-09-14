#!/usr/bin/env python3
"""Interface coverage lint.

Moving the contracts onto this site created one risk: a page can drift from
the code it describes. This lint is the answer to it.

It reads the source revisions the site declares in ``mkdocs.yml`` under
``extra.sources``, extracts every interface those sources expose, and fails
if the site does not document one:

- **sysfs attributes** of ``glowforge.ko``, from the UAPI header;
- **HTTP routes** of ``forgectrl``, from its route table;
- **machine settings keys**, from the validated-key table.

Prints one line per finding as ``KIND: name (source)`` and exits 1 if there
were any.

Where the sources come from
---------------------------
A sibling checkout is used when one exists (the layout the build scripts
expect), reading each file at the declared revision with ``git show``. That
keeps the lint offline for a developer. When the revision is not in the local
object store, or there is no sibling checkout, the repository is cloned into
a temporary directory. ``--worktree`` reads the sibling checkout as it stands
instead, which is what to use while an interface change and its documentation
are still uncommitted.

Bump the declared revisions alongside the recipe pins.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

GITHUB_ORG = "https://github.com/openglow-org"

# Where each interface is declared. One entry per extractor.
SOURCES = {
    "kernel-module-glowforge": ["src/uapi/glowforge.h"],
    "forgectrl": ["src/main.c"],
}

# Attributes that exist in the header but are not a sysfs interface.
ATTR_SKIP = {
    # Group directory names, not attributes.
    "CNC_GROUP_NAME",
    "PIC_GROUP_NAME",
    "THERMAL_GROUP_NAME",
    "HEAD_GROUP_NAME",
    "LED_GROUP_NAME",
}


def fail(msg: str) -> None:
    print(f"check-interfaces: {msg}", file=sys.stderr)
    sys.exit(2)


# --------------------------------------------------------------------------
# Getting the sources


def declared_revisions() -> dict[str, str]:
    """Read ``extra.sources`` out of mkdocs.yml without a YAML dependency."""
    text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    block = re.search(r"^[ \t]*sources:[ \t]*\n((?:[ \t]+\S.*\n|[ \t]*\n)+)", text, re.M)
    if not block:
        fail(
            "mkdocs.yml declares no 'sources:' block under 'extra:'. "
            "Add one naming each source repository and its revision."
        )
    revs = dict(
        re.findall(r"^\s+([A-Za-z0-9._-]+):\s*([0-9a-f]{7,40})\s*$", block.group(1), re.M)
    )
    missing = set(SOURCES) - set(revs)
    if missing:
        fail("mkdocs.yml extra.sources is missing: " + ", ".join(sorted(missing)))
    return revs


def read_source(repo: str, rev: str, paths: list[str], worktree: bool) -> dict[str, str]:
    """Return {path: contents} for one repository at the declared revision."""
    sibling = ROOT.parent / repo

    def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )

    if sibling.is_dir():
        if worktree:
            out = {}
            for p in paths:
                f = sibling / p
                if not f.is_file():
                    fail(f"{repo}: {p} not found in the sibling checkout")
                out[p] = f.read_text(encoding="utf-8", errors="replace")
            head = git(["rev-parse", "HEAD"], sibling).stdout.strip()
            if head and not head.startswith(rev):
                print(
                    f"note: reading {repo} working tree at {head[:12]}, "
                    f"not the declared {rev[:12]}"
                )
            return out
        # Try the declared revision from the local object store first.
        got, out = True, {}
        for p in paths:
            r = git(["show", f"{rev}:{p}"], sibling)
            if r.returncode != 0:
                got = False
                break
            out[p] = r.stdout
        if got:
            return out
        print(f"note: {repo} revision {rev[:12]} is not in the local checkout; cloning")

    if shutil.which("git") is None:
        fail("git is not on PATH")
    tmp = Path(tempfile.mkdtemp(prefix=f"ifacelint-{repo}-"))
    try:
        url = f"{GITHUB_ORG}/{repo}.git"
        r = subprocess.run(
            ["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", url, str(tmp)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            fail(f"cannot clone {url}: {r.stderr.strip()}")
        r = subprocess.run(
            ["git", "fetch", "--quiet", "--depth", "1", "origin", rev],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            fail(f"{repo}: cannot fetch {rev}: {r.stderr.strip()}")
        out = {}
        for p in paths:
            r = subprocess.run(
                ["git", "show", f"{rev}:{p}"], cwd=tmp, capture_output=True, text=True
            )
            if r.returncode != 0:
                fail(f"{repo}: {p} not found at {rev}")
            out[p] = r.stdout
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# Extractors


def sysfs_attributes(header: str) -> set[str]:
    """Every ``#define ATTR_x name`` in the module's UAPI header."""
    found = set()
    for macro, name in re.findall(
        r"^#define\s+(ATTR_[A-Z0-9_]+)\s+([A-Za-z0-9_]+)\s*$", header, re.M
    ):
        if macro in ATTR_SKIP:
            continue
        found.add(name)
    return found


def http_routes(main_c: str) -> set[str]:
    """Every path in forgectrl's route table."""
    return {
        path
        for _method, path in re.findall(
            r'\{\s*"(GET|POST|PUT|DELETE|PATCH)"\s*,\s*"([^"]+)"', main_c
        )
    }


def settings_keys(main_c: str) -> set[str]:
    """Every key in forgectrl's validated-settings table."""
    return set(
        re.findall(r'^\s*\{\s*"([a-z][a-z0-9_]*)"\s*,\s*valid_[a-z0-9_]+\s*,', main_c, re.M)
    )


# --------------------------------------------------------------------------
# The site side


def site_text() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8") for p in sorted(DOCS.rglob("*.md"))
    )


def documented(name: str, text: str, kind: str) -> bool:
    """A name is documented when the site names it, as code or in a heading.

    An attribute may be written bare or with its group (``pic/lid_ir_1``), so
    a path separator in front of it is allowed. A route must match whole: the
    ``/status`` route is not documented by a mention of ``/cool/status``. A
    route's ``:id`` parameter is written ``<id>`` in prose, so each parameter
    segment matches either form.
    """
    if kind == "HTTP route":
        parts = []
        for seg in name.split("/"):
            if seg.startswith(":"):
                parts.append(r"(?::\w+|<[^>]+>|\{[^}]+\})")
            else:
                parts.append(re.escape(seg))
        body = "/".join(parts)
        pattern = r"(?<![A-Za-z0-9_/-])" + body + r"(?![A-Za-z0-9_/-])"
    else:
        # Bare, or qualified by its sysfs group.
        pattern = r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])"
    return re.search(pattern, text) is not None


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--worktree",
        action="store_true",
        help="read the sibling checkouts as they stand, not the declared revisions",
    )
    args = ap.parse_args()

    revs = declared_revisions()
    src = {
        repo: read_source(repo, revs[repo], paths, args.worktree)
        for repo, paths in SOURCES.items()
    }

    header = src["kernel-module-glowforge"]["src/uapi/glowforge.h"]
    main_c = src["forgectrl"]["src/main.c"]

    interfaces = [
        ("sysfs attribute", sorted(sysfs_attributes(header)), "kernel-module-glowforge"),
        ("HTTP route", sorted(http_routes(main_c)), "forgectrl"),
        ("settings key", sorted(settings_keys(main_c)), "forgectrl"),
    ]

    for kind, names, repo in interfaces:
        if not names:
            fail(
                f"extracted no {kind}s from {repo}. The declaration it reads has "
                "probably moved; fix the extractor rather than the count."
            )

    text = site_text()
    findings = [
        f"{kind}: {name} ({repo})"
        for kind, names, repo in interfaces
        for name in names
        if not documented(name, text, kind)
    ]

    total = sum(len(n) for _, n, _ in interfaces)
    for f in findings:
        print(f)
    if findings:
        print(f"{len(findings)} undocumented interface(s) of {total} checked")
        print(
            "Each one is an interface the firmware exposes and this site does "
            "not name. Document it, or remove it from the code."
        )
        return 1
    print(f"interfaces: clean ({total} checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
