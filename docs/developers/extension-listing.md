---
title: List a package in the catalog
---

# List a package in the catalog

The catalog is OpenGlow's signed list of extension packages. A machine
fetches it only when its operator asks, and shows each listed package on
the Extension packages card with a **Get** button. How the machine
verifies the catalog and judges each listed version is in
[Extension packages](../technical/forgefirm/extensions.md#the-signed-index);
this page is what it takes to be listed, what a listing is, and how the
catalog is kept.

The catalog has its own repository,
[`openglow-org/forgefirm-extensions-catalog`](https://github.com/openglow-org/forgefirm-extensions-catalog).
Nothing in it is part of the firmware image. Thus a listing never waits for
a firmware release, and machines on every firmware read the same catalog.

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
  package under a new id. One key can sign several packages.
- **An id of its author's own**: reverse DNS under a domain or a code-host
  account the author controls, such as `io.github.<account>.<name>`. The
  ids under `org.openglow.` and `org.forgefirm.` are OpenGlow's.
- **Capabilities that fit what it does.** A package asks for what its
  description needs and nothing more. A package that sends what it learns
  off the machine names where, in its manifest or as a place the operator
  names, and its description says so.
- **A description that says what it does** in plain words, and what it
  sends off the machine.
- **The firmware it needs, when it needs one**, in its manifest's `core`.
  A version that needs a capability, an extension API, or a firmware that
  some machines do not have is still listed: each machine offers the
  newest listed version that it runs.
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

Open a pull request on the catalog repository that adds one version of one
package:

- `packages/<id>/<version>.json`, the version's record. `ffx index record`
  writes it from the signed archive, after it checks the signature against
  your key and judges the package as `ffx lint` does:

    ```sh
    tools/ffx index record mypackage-0.1.0.ffx \
        --url https://github.com/me/mypackage/releases/download/v0.1.0/mypackage-0.1.0.ffx \
        --key me.pub --out packages/io.github.me.mypackage/0.1.0.json
    ```

- `packages/<id>/key.pub`, your public key, with the first version of a
  package.

The pull request names the tag of the source that the archive was built
from. The archive's address is `https://`, a release asset of the
package's own repository for example. Each version is its own pull request:
the catalog names every archive by its address, its size, and its SHA-256,
so an archive changed after it was listed no longer matches, and the
machine refuses it.

The catalog's check runs on every pull request:

- The catalog's form, as every machine keeps it (`ffx index build`).
- The keys. A package's `key.pub` never changes and is never removed, and
  an id in OpenGlow's namespace has none.
- A new record. The archive is fetched once from its address, verified
  against the package's key, and judged as `ffx lint` judges it, and it
  must give the same record. The record's `core` range can be narrower
  than the manifest's, never wider.
- A changed record. Only its `core` range changes, and only to a narrower
  one.
- The index built from the catalog, kept by the extension host of every
  firmware release still supported. The `hosts` file names their
  `forgeext` revisions.

The check runs as the pull request has it. Thus OpenGlow's review covers
every change to the tools, the workflow, `hosts`, and `keys/`, and a pull
request that changes them lists nothing in the same change. OpenGlow reads
the package at the listed version, and merges the pull request or declines
it and says why.

## Withdrawal

OpenGlow withdraws a listing when a package breaks this policy, when a
flaw in it is found and not fixed, or when its author asks. In the
catalog, `packages/<id>/withdrawn.json` withdraws:

- Versions: `{"versions": {"0.1.0": "why"}}`, with their records removed.
- The whole package: `{"reason": "why"}`, with every record removed and
  `key.pub` kept.

Every machine that fetches the catalog after that sees the withdrawal, on
every firmware. A withdrawn version does not install on any machine. A
copy that is installed stays installed and shows the withdrawal with its
reason: the machine removes nothing on its own. When a whole package is
withdrawn, its key endorses nothing, so an update of an installed copy is
judged as signed by nobody, and pinning to the key that signed the
installed version refuses it. The operator removes it.

## How the catalog is built

`ffx index build` builds the index from the catalog directory. It takes
each package's name, author, description, license, and homepage from its
newest record, and each version's address, SHA-256, size, capabilities,
extension API, and firmware range from that version's record. The same
catalog builds the same index, byte for byte, and `ffx index build`
prints the SHA-256 of its `index.json`.

```sh
tools/ffx index build . --version 2026.923.1 --key forgefirm-ext.priv --out index-1.ffi
```

The index's version is `YYYY.MMDD.N`, and it only goes up: a machine
refuses an index older than the one it keeps. Without `--key`, `ffx index
build` makes an unsigned index, which no machine keeps.

The catalog's workflow publishes the index. After the check passes on a
push to `main`, its publish job (`tools/publish.py`) does these steps:

1. It builds the index of the tree. When its `index.json` is the one that
   the latest release carries, it publishes nothing. The release notes
   carry that SHA-256, and the job reads them through the releases API,
   which counts no download.
2. It takes the next version, `YYYY.MMDD.N` of the day in UTC, which must
   be above the latest release's.
3. It signs the index with the OpenGlow extension key. The key is the
   secret `FORGEFIRM_EXT_KEY` of the repository's `extension-signing`
   environment, whose deployment branches are `main` alone, so no pull
   request and no other branch receives it. The job writes the key to a
   file that only it can read, and removes it when it ends.
4. The extension host of every revision in `hosts` keeps the signed index
   under `keys/forgefirm-ext.pub`, the key every machine trusts. This
   proves that the secret is that key.
5. It publishes the index as the `index-1.ffi` asset of a new release,
   tagged `v<version>` and marked latest. Machines fetch it from the latest
   release.

The firmware is signed with a different key, and not in this workflow
([Release flow](release-flow.md)).
