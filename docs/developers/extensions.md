---
title: Write an extension package
---

# Write an extension package

This page is for the author of a package. What a package is, what the
machine takes, and what a package may reach are in
[Extension packages](../technical/forgefirm/extensions.md); this page is
how to make one, test it, sign it, put it on a machine, and keep it in a
repository that publishes it.

## The kit

Everything is in the `forgeext` repository:

| Path | What it is |
|---|---|
| `tools/ffx` | The author's tool: make, check, pack, sign, install, read the log |
| `sdk/python/ffx.py` | A Python service's client of the extension API |
| `sdk/c/ffx.h` | A native service's client, one header, libc only |
| `sdk/sh/ffx.sh` | A shell service's client, through the machine's `curl` |
| `sdk/js/ffx-bridge.js` | A page's client of the panel's bridge |
| `sdk/python/modules.txt` | The Python modules a service may import |
| `template/` | A package for each runtime |

`ffx` needs Python 3.8 or later, and [fwup](https://github.com/fwup-home/fwup)
for `pack` and `keygen` (set `FWUP` to its path if it is not on `PATH`).
It runs on Linux, macOS, and Windows.

## Start from the template

```sh
tools/ffx new mypackage --id org.example.mypackage --runtime python
```

The id is yours for good: it names the package's directories on every
machine it is installed on, and an update must keep it. It is reverse-DNS,
lower case, and `org.openglow.` and `org.forgefirm.` belong to the
official packages. The template puts the right client of the kit into the
package (`lib/ffx.py`, `lib/ffx.sh`, or `src/ffx.h`, and the bridge client
inside a page).

| Runtime | What runs | Where |
|---|---|---|
| `data` | nothing | files for a person or a program to take |
| `ui` | a page | in the operator's browser, in the panel's sandboxed frame |
| `python` | a service | on the machine, Python 3.12, only the modules in `sdk/python/modules.txt`. Vendor anything else, pure Python only |
| `shell` | a service | on the machine, busybox `sh` |
| `native` | a service | on the machine, one ARMv7 hard-float binary: static, or linked against the C library alone (`libc.so.6`, `libm.so.6`) with no symbol newer than the machine's glibc 2.39 |

A native service is built on the author's computer and packed as a
binary. A static one needs nothing of the machine's; one that looks up a
name (`getaddrinfo`) is better linked against the C library, which then
reads the machine's own resolver configuration. The template's source says
how; on Debian and Ubuntu:

```sh
apt install gcc-arm-linux-gnueabihf
arm-linux-gnueabihf-gcc -static -O2 -Wall -o bin/run src/main.c
```

A package may be a service and a page at once: a service runtime that also
asks for `ui` and ships `ui/index.html`.

## Talk to the machine

A service has one way to the machine, the Unix socket that `FFX_API`
names; the kit's clients speak it. A page has one way too, the panel's
bridge, and `ffx-bridge.js` speaks that. Neither reaches anything else:
not the network unless the manifest names the destination, and never the
machine's own listeners. The calls, what each needs, and what comes back
are in [The extension API](../technical/forgefirm/extensions.md#the-extension-api)
and [The bridge](../technical/forgefirm/extensions.md#the-bridge).

```python
import ffx
ffx.hold(True, "the exhaust fan is off")      # needs the hold grant
for ev in ffx.follow():                       # needs events
    if ev["event"] == "job.ended":
        ffx.hold(False)
```

Some rules to write for:

- **The machine has no clock that keeps the date.** Time every wait and
  every schedule with the monotonic clock (`time.monotonic()`,
  `CLOCK_MONOTONIC`), never with the wall clock.
- **A service is frozen while a job is armed**, unless the operator gave it
  `job_time.run`. Everything it holds stays as it was, its hold included,
  and it goes on where it stopped.
- **A refusal is an answer, in words.** A capability the package does not
  hold is 403, a request out of form is 400, and the machine's own refusal
  (the lid is open, somebody is watching the camera, a job is armed) comes
  back as the machine said it. A client raises it with the status and the
  words; show the words to the operator.
- **Where your service connects is fixed before it starts.** Name a public
  service in the manifest (`net.outbound:ntfy.sh:443`). A device on the
  operator's own network, which only they can name, takes
  `net.outbound.operator`: they name it on the package's card, and
  `/v0/self` (`ffx.me()["destinations"]`) says what they have named, so
  your page can tell them what is still missing.
- **A page can send a little data out of the operator's browser** through
  WebRTC, and nothing in a browser prevents it. Say what your page does
  with what it is shown.

### A page and its own service

A package that is a service and a page at once can have the page ask the
service, and the kit carries both ends. The service answers:

```python
import ffx

def handle(method, path, body):          # "GET" or "POST", "/rules", the page's JSON object
    if path == "/rules":
        return load_rules()              # answered as 200, as JSON
    raise ffx.CallError(404, "there is no " + path)

ffx.serve(handle, background=True)       # a thread of its own; then the service's own work
```

and the page asks:

```js
ffx.service.call('GET', '/rules').then(function (r) { show(r.status, r.body); });
```

A native service polls `ffx_call_fd()` beside its own work and answers with
`ffx_serve_one()`. A shell service cannot answer: busybox `sh` has no way to
accept a connection. A call waits at most 10 s for the whole answer, which
is at most 64 KiB, and a service frozen for an armed window is not asked at
all: the page is told so. The form a call takes, and what refuses one, are
in [A page and its own service](../technical/forgefirm/extensions.md#a-page-and-its-own-service).

### An M-code in a job

A package can answer one of M160 to M179 in the operator's own jobs: ask
for `mcode:<n>` and `job_time.run` (the operator grants the second). The
job waits at the M-code, the head still and the laser dark, and your
service is asked on the same socket a page's calls use, page or no page:

```python
import ffx

def handle(method, path, body):
    if path == "/mcode":                 # {"code": 160, "words": {"P": 1}}
        if not exhaust_on():
            raise ffx.CallError(409, "the exhaust did not start")   # the job is held, with these words
        return {"message": "exhaust on"}                             # the job goes on
    raise ffx.CallError(404, "there is no " + path)

ffx.serve(handle)
```

A 2xx lets the job go on, and its `message` goes to the sender's console.
Anything else holds the job with your words, for the operator to resume or
stop, and so does taking longer than 20 s. Each number is one package's:
the machine refuses a second package that asks for one already taken. What
the controller does meanwhile is in
[A package's M-code](../technical/forgefirm/extensions.md#a-packages-m-code).

### A check on the Setup page

A package that asks for `wizard` adds a check of its own to the Setup
page. The machine's own runner drives it, and your service answers each
step on the same socket:

```python
import ffx

done = False

def handle(method, path, body):
    global done
    if path == "/wizard":                # the Setup page's list
        return {"title": "Exhaust check", "done": done}
    if path == "/wizard/start":
        return {"log": ["looking for the exhaust"], "progress": 50,
                "prompt": {"kind": "confirm", "id": "fan", "text": "Is the exhaust fan running?"}}
    if path == "/wizard/answer":         # {"id": "fan", "answer": "yes"}
        done = body.get("answer") == "yes"
        return {"result": {"ok": done, "summary": "the exhaust runs" if done else "no exhaust"}}
    if path == "/wizard/abort":
        return {}
    raise ffx.CallError(404, "there is no " + path)

ffx.serve(handle)
```

The result is yours to keep: the machine records none of it, and nothing
of the machine's setup waits for it. Use it to decide what your package
does. The steps' form is in
[A package's check on the Setup page](../technical/forgefirm/extensions.md#a-packages-check-on-the-setup-page).

## Test it without a machine

The panel's dev server in the `forgectrl` repository installs a package
from its directory in its mock of the machine:

```sh
python3 tools/devserver.py --package ../mypackage
```

Then open <http://127.0.0.1:8081/#system> and press **Open** beside the
package. The page is read fresh from `ui/index.html` at every Open, its
settings follow its manifest, every capability that needs a grant is
granted, and the mock's head camera shows a millimeter grid that moves as
the head jogs. A service does not run in the mock: test one on a machine.

With `--call-port 8765`, the page's calls to its service go to
`127.0.0.1:8765` in the host's form. The service's handler can answer them
there under `ffx.serve()`, given a socket listening on that port as its
`FFX_CALL_FD`; the rest of a service, which asks the machine, runs only on
a machine.

## Check it, and pack it

```sh
tools/ffx lint mypackage
tools/ffx pack mypackage --key me.priv
```

`lint` judges the package the way the machine will, in the machine's
words, and stops where the machine would: the manifest, the capabilities,
the page, the service's entry point, the limits of a payload, and every
import of a Python service against `sdk/python/modules.txt`. It also reads a
native service's binary, which the machine does not: its architecture, its
float ABI, the libraries it is linked against, and the newest C library
symbol it needs, so that a binary the machine's loader would refuse is
refused here first. `pack` lints
first and packs nothing it refuses; the payload is the same bytes every
time for the same files.

## Sign it

```sh
tools/ffx keygen me          # me.priv, which you keep to yourself, and me.pub
```

A package signed with your key installs as **Community** on a machine
whose owner added `me.pub` (the panel's **Keys you trust** card, with the
machine's button held), and as **Unverified** everywhere else: the owner
then holds the button to install it. An update must be signed with the
key that signed the installed version. Keep the private key: a lost key is
a package that cannot be updated, only removed and installed again.

A package in OpenGlow's catalog installs as **Community** on every machine,
with no key added: the catalog names your key for your package's id.
[List a package in the catalog](extension-listing.md) says what that takes.

## Put it on a machine

```sh
tools/ffx install mypackage-0.1.0.ffx --machine 192.0.2.10 --grant hold
tools/ffx logs --machine 192.0.2.10 --id org.example.mypackage --follow
```

`install` logs in as the machine's owner over HTTPS. The machine's
certificate is its own, so the first connection shows its fingerprint to
compare with the one on the panel's System tab, and remembers it. Then it
shows what the machine says the package is, and installs with what its
tier takes: nothing more for Official, the typed phrase for Community, and
the button held for Unverified. A grant is given only when it is named
with `--grant`. `logs` shows the extension host's log, a package's own
lines with `--id`: everything a service prints is there.

## A repository for your package

A package can live in a repository of its own, whose workflow tests and
packs it on every push, and signs and publishes each new version as a
release. OpenGlow's own packages are examples:

| Repository | Shows |
|---|---|
| [`forgefirm-extension-alignment`](https://github.com/openglow-org/forgefirm-extension-alignment) | The smallest: a page, and nothing that runs on the machine |
| [`forgefirm-extension-automation`](https://github.com/openglow-org/forgefirm-extension-automation) | A native service built for the machine, and its page, with unit tests and a test under the real extension host |

A repository like them holds:

| Path | What it is |
|---|---|
| `manifest.json`, and the package's files | The package, as `ffx new` made it |
| `Makefile` | A `stage` target that lays out what the package ships in `build/pkg`, and nothing of the repository's own files, source, or tests |
| `key.pub` | The public half of the key that signs the package ([Sign it](#sign-it)) |
| `.github/workflows/package.yml` | A call to forgeext's shared workflow |

The call, with the inputs a native service needs:

```yaml
name: package

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: write

jobs:
  package:
    uses: openglow-org/forgeext/.github/workflows/package.yml@main
    with:
      apt: gcc-arm-linux-gnueabihf
      test: make test
      host-test: make host && python3 -B tests/automation_test.py
    secrets: inherit
```

| Input | Default | What it is |
|---|---|---|
| `stage` | `make stage` | The command that lays out the package as it ships |
| `dir` | `build/pkg` | Where `stage` lays it out |
| `test` | none | The package's own tests |
| `host-test` | none | A test under the real extension host, run as root with `FORGEEXT`, `FWUP`, `FFX`, `MKFFX`, and `FFX_RULES` set |
| `apt` | none | Ubuntu packages the build needs, such as a cross compiler |
| `public-key` | `key.pub` | The public half of the signing key |
| `environment` | `extension-signing` | The environment whose secret signs a release |
| `forgeext-ref` | `main` | The forgeext revision whose kit judges and packs the package |

On every push and pull request, the workflow runs the package's own tests,
runs `stage`, lints the result as the machine judges it
([Check it, and pack it](#check-it-and-pack-it)), packs it, and runs the test
under the real extension host.

On a push to `main`, when the manifest names a version that has no release
yet, the workflow does these steps:

1. It stages the package again, and lints it.
2. It signs the package with `EXTENSION_SIGNING_KEY`, the secret of the
   repository's `extension-signing` environment: the private half of your
   key, as `ffx keygen` wrote it. `ffx pack` checks the signature against
   `key.pub` before the step ends, so a secret that is not that key
   publishes nothing.
3. It writes the package's catalog record with `ffx index record`, for the
   address the release gives the archive.
4. It publishes `<id>-<version>.ffx` and the record, `<version>.json`, as
   release `v<version>`.

A version that has a release publishes nothing again: a change ships under
a new version in the manifest. Give the environment one deployment branch,
`main`, so that no pull request and no other branch receives the key. To
list the new version in the catalog, add its record as
`packages/<id>/<version>.json` in a pull request to the catalog
([Asking for a listing](extension-listing.md#asking-for-a-listing)).

A workflow of your own can use forgeext's kit alone: check out forgeext at
`.forgeext`, then `uses: ./.forgeext/.github/actions/kit`. The kit installs
fwup 1.16.0 and sets `FFX`, `MKFFX`, `FWUP`, and `FORGEEXT_SRC`. With
`host: true` it also builds the extension host and fetches the image's deny
rules, and sets `FORGEEXT` and `FFX_RULES`.
