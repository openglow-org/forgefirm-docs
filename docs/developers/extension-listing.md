---
title: List a package in the catalog
---

# List a package in the catalog

The catalog is OpenGlow's signed list of extension packages. A machine
fetches it only when its operator asks, and shows each listed package on
the Extension packages card with a **Get** button. How the machine
verifies it is in
[Extension packages](../technical/forgefirm/extensions.md#the-signed-index);
this page is what it takes to be listed, and what a listing is.

## What a listing is

A listing says that OpenGlow read the package at the listed version before
it listed it: its manifest, its source, and what it asks for against what
it says it does. It is not a test on a machine, a warranty, or a promise of
support. The package's author keeps it working and answers for it.

A listed package that OpenGlow did not write reads as **Community** on
every machine that has the catalog: the catalog names its author's public
key for its id, and the operator installs it with the typed phrase, as for
a key they added themselves. The catalog makes no package official. Only
OpenGlow's own packages, signed with the OpenGlow extension key, are.

## What a package needs

- **Its source, published**, under a license that lets anyone read,
  build, and change it, at the address its `homepage` names. The listed
  archive is built from that source at a tag.
- **Its author's own key.** Every version is signed with the same key
  ([Sign it](extensions.md#sign-it)). The catalog binds the package's id
  to the key it was first listed with, and the key does not change for
  that id: an author who loses a key, or wants a new one, lists the
  package under a new id.
- **An id of its author's own**: reverse DNS under a domain or a code-host
  account the author controls, such as `io.github.<account>.<name>`. The
  ids under `org.openglow.` and `org.forgefirm.` are OpenGlow's.
- **Capabilities that fit what it does.** A package asks for what its
  description needs and nothing more. A package that sends what it learns
  off the machine names where, in its manifest or as a place the operator
  names, and its description says so.
- **A description that says what it does** in plain words, and what it
  sends off the machine.
- **`ffx lint` passes** on it, the machine's own judgment of a package
  ([Check it, and pack it](extensions.md#check-it-and-pack-it)).

## What is not listed

- A package that hides what it does, or does something its description
  does not say.
- A package that sends anything off the machine that its description does
  not say.
- A package that asks for a hold, a program run, or to keep running while
  a job is armed, for no reason its description gives.
- A package whose source does not build into the listed archive.

OpenGlow can decline a package for another reason, and says which.

## Asking for a listing

Ask in the `forgeext` repository's issues, with the package's id, the tag
of its source, the address of the signed archive (`https://`, a release
asset of the package's own repository, for one), and its public key. Each
version is listed on its own: the catalog names every archive by its
address, its size, and its SHA-256, so a new version is a new request, and
an archive changed after it was listed no longer matches and the machine
refuses it.

## Withdrawal

OpenGlow withdraws a listing when a package breaks this policy, when a
flaw in it is found and not fixed, or when its author asks. A machine that
fetches the catalog after that no longer lists it. A copy that is
installed stays installed, and the machine removes nothing on its own; an
update of it is then judged as signed by nobody, and pinning to the key
that signed the installed version refuses it. The operator removes it.

## How the catalog is built

`ffx index build` builds the index from a listing:

```json
{"packages": [
  {"file": "mypackage-0.1.0.ffx",
   "url": "https://github.com/me/mypackage/releases/download/v0.1.0/mypackage-0.1.0.ffx",
   "key": "me.pub"}
]}
```

```sh
tools/ffx index build listing.json --version 2026.9.23 --key forgefirm-ext.priv --out index.ffi
```

Each entry's id, name, version, author, description, license, homepage,
and capabilities are read from the archive's own manifest; its SHA-256 and
its size from its bytes; the key from the named file. An entry in
OpenGlow's namespace names no key, and every other entry must. The same
listing builds the same index, byte for byte. Without `--key` it builds
an unsigned index, which no machine keeps. The signed index is published
as the `index.ffi` asset of the latest release of
`openglow-org/forgefirm-extensions`.
