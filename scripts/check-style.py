#!/usr/bin/env python3
"""House-style lint for the documentation.

Checks every Markdown file under docs/ and the repository README for the
rules a machine can enforce:

- no em dashes (U+2014);
- American English (a fixed list of British spellings);
- no paths from anyone's workstation (drive letters, /mnt/<drive>, home
  directories);
- no bench-machine identity (private IP addresses, root@host);
- no camera metadata in a published image: a photograph carrying GPS tags
  gives away where the bench is, and the make, model, owner or serial of the
  camera identifies who took it.

Prints one line per finding as path:line: RULE: detail and exits 1 if there
were any. A line may carry the marker ``<!-- style: ignore -->`` to be
skipped, for the rare quotation that has to stay as written.
"""

from __future__ import annotations

import re
import struct
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


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

JPEG_SOI = bytes((0xFF, 0xD8))
PNG_SIG = bytes((0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A))
EXIF_ID = b"Exif" + bytes(2)

# EXIF tags that identify a place, a camera or a person. GPSInfo is the
# pointer to the GPS sub-IFD; its mere presence is the finding.
EXIF_FLAGGED = {
    0x8825: "GPS",
    0x010F: "Make",
    0x0110: "Model",
    0x0131: "Software",
    0x013B: "Artist",
    0x8298: "Copyright",
    0xA430: "CameraOwnerName",
    0xA431: "BodySerialNumber",
}


def _ifd_tags(buf: bytes, bo: str, off: int, found: set) -> None:
    if not 0 < off < len(buf) - 2:
        return
    (n,) = struct.unpack(bo + "H", buf[off:off + 2])
    for k in range(n):
        e = off + 2 + k * 12
        if e + 12 > len(buf):
            return
        (tag,) = struct.unpack(bo + "H", buf[e:e + 2])
        if tag in EXIF_FLAGGED:
            found.add(EXIF_FLAGGED[tag])
        if tag == 0x8769:                       # ExifIFD: owner and body serial
            (sub,) = struct.unpack(bo + "I", buf[e + 8:e + 12])
            _ifd_tags(buf, bo, sub, found)


def _tiff_tags(buf: bytes) -> set:
    """Tag names of interest in a TIFF/EXIF stream. Best effort: a stream
    this cannot parse carries nothing it can report."""
    found = set()
    try:
        bo = {b"II": "<", b"MM": ">"}.get(buf[:2])
        if bo is None:
            return found
        magic, off = struct.unpack(bo + "HI", buf[2:8])
        if magic == 42:
            _ifd_tags(buf, bo, off, found)
    except (struct.error, IndexError):
        pass
    return found


def image_tags(data: bytes) -> set:
    """Flagged EXIF tag names carried by a JPEG or PNG."""
    if data[:2] == JPEG_SOI:
        i = 2
        while i < len(data) - 3 and data[i] == 0xFF:
            marker = data[i + 1]
            if marker == 0xDA:                  # start of scan; metadata is behind us
                break
            try:
                (ln,) = struct.unpack(">H", data[i + 2:i + 4])
            except struct.error:
                break
            seg = data[i + 4:i + 2 + ln]
            if marker == 0xE1 and seg[:6] == EXIF_ID:
                return _tiff_tags(seg[6:])
            i += 2 + ln
    elif data[:8] == PNG_SIG:
        i = 8
        while i + 8 <= len(data):
            (ln,) = struct.unpack(">I", data[i:i + 4])
            kind = data[i + 4:i + 8]
            if kind == b"eXIf":
                return _tiff_tags(data[i + 8:i + 8 + ln])
            if kind == b"IDAT":
                break
            i += 12 + ln
    return set()


def images() -> list[Path]:
    return sorted(p for p in (ROOT / "docs").rglob("*")
                  if p.suffix.lower() in IMAGE_SUFFIXES)


def check_image(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    tags = image_tags(path.read_bytes())
    if not tags:
        return []
    what = "GPS tags" if "GPS" in tags else ", ".join(sorted(tags))
    return [f"{rel}: EXIF: {what} - strip the metadata before publishing"]


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
    findings += [f for p in images() for f in check_image(p)]
    for f in findings:
        print(f)
    if findings:
        print(f"{len(findings)} finding(s)")
        return 1
    print("style: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
