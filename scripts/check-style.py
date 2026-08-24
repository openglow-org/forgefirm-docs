#!/usr/bin/env python3
"""House-style lint for the documentation.

Checks every Markdown file under docs/ and the repository README for the
rules a machine can enforce:

- no em dashes (U+2014);
- American English (a fixed list of British spellings);
- no paths from anyone's workstation (drive letters, /mnt/<drive>, home
  directories);
- no bench-machine identity (private IP addresses, root@host).

Prints one line per finding as path:line: RULE: detail and exits 1 if there
were any. A line may carry the marker ``<!-- style: ignore -->`` to be
skipped, for the rare quotation that has to stay as written.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE_MARK = "<!-- style: ignore -->"

# British form -> American form. Verb families are matched on their stems so
# that "analyse", "analysed" and "analysing" all trip, while "analyses" (the
# American plural noun) does not.
BRITISH = {
    r"colour(?:s|ed|ing|ful)?\b": "color",
    r"behaviours?\b": "behavior",
    r"programmes?\b": "program",
    r"licences?\b": "license",
    r"towards\b": "toward",
    r"whilst\b": "while",
    r"amongst\b": "among",
    r"learnt\b": "learned",
    r"spelt\b": "spelled",
    r"analys(?:e|ed|ing)\b": "analyze",
    r"organis(?:e|ed|ing|ation|ations)\b": "organize",
    r"recognis(?:e|ed|ing)\b": "recognize",
    r"initialis(?:e|ed|ing|ation)\b": "initialize",
    r"normalis(?:e|ed|ing|ation)\b": "normalize",
    r"characteris(?:e|ed|ing|ation)\b": "characterize",
    r"summaris(?:e|ed|ing)\b": "summarize",
    r"utilis(?:e|ed|ing|ation)\b": "utilize",
    r"optimis(?:e|ed|ing|ation)\b": "optimize",
    r"catalogues?\b": "catalog",
    r"centres?\b": "center",
    r"centred\b": "centered",
    r"grey\b": "gray",
    r"judgement\b": "judgment",
    r"acknowledgement\b": "acknowledgment",
    r"defence\b": "defense",
    r"offence\b": "offense",
    r"travell(?:ed|ing)\b": "traveled",
    r"modell(?:ed|ing)\b": "modeled",
    r"labell(?:ed|ing)\b": "labeled",
    r"cancell(?:ed|ing)\b": "canceled",
    r"signalling\b": "signaling",
    r"fulfil(?:s)?\b": "fulfill",
    r"ageing\b": "aging",
    r"enquir(?:e|y|ies|ed|ing)\b": "inquire",
    r"sceptic(?:s|al|ism)?\b": "skeptic",
    r"aluminium\b": "aluminum",
    r"manoeuvr(?:e|es|ed|ing)\b": "maneuver",
    r"artefacts?\b": "artifact",
    r"per cent\b": "percent",
}
BRITISH_RE = [(re.compile(r"\b" + p, re.IGNORECASE), a) for p, a in BRITISH.items()]

RULES = [
    ("EM-DASH", re.compile("—"), "em dash; use a colon, period, or comma"),
    ("DEV-PATH", re.compile(r"\b[A-Za-z]:\\"), "workstation drive path"),
    ("DEV-PATH", re.compile(r"/mnt/[a-z]/"), "WSL mount path"),
    ("DEV-PATH", re.compile(r"/home/[a-z][a-z0-9_-]*/"), "home directory path"),
    ("BENCH-ID", re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b"), "private IP address"),
    ("BENCH-ID", re.compile(r"\broot@"), "root@host login"),
]


def files() -> list[Path]:
    found = sorted((ROOT / "docs").rglob("*.md"))
    readme = ROOT / "README.md"
    if readme.exists():
        found.append(readme)
    return found


def check(path: Path) -> list[str]:
    out: list[str] = []
    rel = path.relative_to(ROOT).as_posix()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if IGNORE_MARK in line:
            continue
        for rule, rx, detail in RULES:
            if rx.search(line):
                out.append(f"{rel}:{n}: {rule}: {detail}")
        for rx, american in BRITISH_RE:
            m = rx.search(line)
            if m:
                out.append(f"{rel}:{n}: SPELLING: '{m.group(0)}' -> {american}")
    return out


def main() -> int:
    findings = [f for p in files() for f in check(p)]
    for f in findings:
        print(f)
    if findings:
        print(f"{len(findings)} finding(s)")
        return 1
    print("style: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
