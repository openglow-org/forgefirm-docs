---
title: Extensions
---

# Extensions

An extension package is software that is not part of ForgeFIRM. Somebody
else writes it; you install it on the machine, and it runs there in a
sandbox with only what you grant it. Extensions are off until you turn them
on, and everything about them is on the panel's System tab, in the
**Extension packages** card.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../../safety/index.md)
    before you run a job.

What a package runs inside, the API it reaches the machine through, and how
a hold reaches the cooling engine are in
[Extension packages](../../technical/forgefirm/extensions.md).

## Turning extensions on

The card's button shows you the Extensions advisory and asks you to type
`I UNDERSTAND`. Turning extensions on agrees to that text, and the machine
records which version of it you read. Until then no package runs, and a
package you have installed sits idle.

Turning extensions off again stops every package within seconds. So does
**safe mode**: make the file `/run/forgefirm/ext-safe` at the console (as
root, `touch /run/forgefirm/ext-safe`), and no package runs until you
remove it or the machine reboots. Neither exit depends on the extension
host being healthy.

## Installing a package

A package is one file, `<name>.ffx`. Choose it in the card and press
**Upload a package**. The machine reads it and shows you what it is before
anything is installed: who wrote it, what it says it does, what it asks to
be allowed, and who signed it.

| Who signed it | The machine says | Installing it takes |
|---|---|---|
| The OpenGlow extension key | **Official** | Your login |
| A key you added to this machine, or its author's key that the [catalog](#the-catalog) names for it | **Community** | Your login, and you type `I UNDERSTAND` |
| Nobody the machine trusts | **Unverified** | Your login, and the machine's button **held** while you press Install, as for unsigned firmware |

A signature says who made a package. It does not say the package is safe,
correct, or useful. The project does not test or vouch for a package
unless it is signed with the OpenGlow extension key.

Some of what a package asks for needs a grant from you for that one
package, and the card shows those as tick boxes: holding a job, running a
program as the sender, and keeping running while a job is armed. A package
gets nothing you do not tick. An update that asks for more shows you what
is new.

**Discard** removes an uploaded package without installing it. The upload
and the install are refused while a job runs.

## The catalog

The catalog is OpenGlow's list of packages, signed with the OpenGlow
extension key. **Fetch the catalog** on the Extension packages card asks
GitHub for it, that once: the machine never fetches it on its own. It
lists each package with who wrote it, what it says it does, and what it
asks to be allowed, and marks the ones this machine has installed.

The catalog can list more than one version of a package. The card shows
the newest version that runs on this machine's firmware, and **Get**
fetches that version. If a newer version needs a newer firmware, the card
says so. If no version runs on this firmware, the card says why and has no
Get button. After a firmware update, the card shows what the new firmware
runs, with no new fetch.

**Get** fetches the package, checks that it is the very archive the
catalog lists, and shows it to you as an upload is shown. Then you install
it or discard it, as above. A package OpenGlow makes reads as
**Official**. Every other listed package is signed with its author's key,
which the catalog names for that package alone, so it reads as
**Community** and you type `I UNDERSTAND` to install it. OpenGlow read it
before it listed it; that is not a test, and nobody vouches for it. What
it takes to be listed is the
[listing policy](../../developers/extension-listing.md).

The machine never goes back to a catalog older than the one it has.

OpenGlow can withdraw a package, or one version of it:

- A copy you installed stays installed. The machine removes nothing on its
  own. The package's card says that OpenGlow withdrew it, and why.
- A withdrawn version does not install again, from the catalog or from a
  file.
- When a whole package is withdrawn, an update of it reads as unverified,
  and the machine refuses it, because an update must be signed with the
  key that signed the installed version.

Remove a withdrawn package if you no longer want it.

## Keys you trust

The machine trusts the OpenGlow extension key, and whatever key you add
yourself. A package signed with a key you added reads as **Community**
instead of Unverified, so it installs with the typed phrase instead of the
button.

The **Keys you trust** card takes a name and the public key as its author
published it (what `fwup -g` writes). **Hold the button on the machine**
while you add one: a key you add is what this machine will trust from then
on, so it is the same act as installing unsigned firmware. A key that
cannot be read as one is refused and nothing is kept.

Removing a key does not touch a package that was installed with it. The
key decides how an archive reads when you upload it, not what an installed
package is.

## What a package may do, and what it may not

A package runs as its own account, with limits on processor time, memory,
and the number of its processes. It sees its own files and the read-only
parts of the system, and nothing else on the machine. It reaches the
machine only through the extension host, which answers from what you
granted: the status, the cooling status, the mode, the machine's events, a
picture from a camera, a bounded jog, settings of its own, and its own
hold. Its settings are kept by the machine and outlive the package being
updated; they are its own keys and never the machine's. A package's picture
never interrupts you: while you are watching a camera, its capture waits.
**A package that can jog can move the head while you have your hands in the
machine** - the jog is bounded and never fires the laser, and it is still
motion you did not ask for. A package you granted `motion.job` can start a
job, which then waits for the button and stands under every gate your own
jobs do. A package that answers an M-code (one of M160 to M179, which you
put in your own job) holds that job at the M-code until it answers, with the
head still and the laser dark; if it does not answer, or says it could not
do its part, the job is held for you to resume or stop
([GRBL mode](../grbl-mode.md#m-codes-an-extension-answers)). It can
send to the network only where its capabilities say, and never to the
machine itself.

No package reaches the laser, the motion hardware, the cooling hardware,
the cameras, the machine's settings, the firmware, or your login directly.
**While a job is armed every package is frozen**, unless you granted one
the right to keep running, and that one runs under tighter limits for the
length of the job. The lid, the interlock, the armed window and its
button, the cooling gates, and the limits on motion work the same with
extensions on: the most a package can do to a job is hold it.

## Places you name for a package

A package that works with things on your own network - a smart plug for
the exhaust fan, a Home Assistant server, an MQTT broker - cannot know
where they are. It asks to be told instead, and its card then shows
**Places you named for it**, with a box for one more. Type the address and
port, such as `192.0.2.40:80` or `broker.lan:1883`, and press **Add**.
The package can reach those places and no others, and nothing the package
does can add one. It is started again each time the list changes. The
machine itself is never a place a package can reach, so its own address is
refused. **Remove** takes a place away again.

## A package's own page

A package may bring a page of its own, and the card opens it when you ask
for it. It is where a package that has something to set or to show puts
it: the settings it declared, a view, a button of its own. Above the page
the panel writes the package's name, its trust tier and its id, and a
Close button - those are the machine's own words about the package, never
the package's.

The page is held at arm's length. It cannot read your session, reach the
rest of the panel, or open anything of its own on the network; when it
wants something from the machine it has to ask the panel, and the panel
answers only what you granted that package. A camera frame is fetched by
the panel and handed over as a picture, so nothing of your login is ever
in the page's hands.

!!! warning "A page can send a little data out of your browser"

    One way out of a browser, WebRTC, is not something a page can be shut
    out of by the means above - it is outside them in both browsers this
    project tests, and it works at low bandwidth even when a page is
    otherwise cut off. So a package with a page of its own can get a small
    amount of data out through the browser you are viewing it in. A package
    without a page cannot do this at all, and nothing about it reaches the
    machine.

## Holds

A package you granted a hold may withhold fire: the machine reads the
verdict `EXT`, the job holds, and the reason names the package and says
why. A hold never permits anything, and it never outranks a verdict of the
machine's own.

You choose what its hold does when the package cannot speak for itself:

- **is dropped (advisory)**: the hold goes when the package is not
  running. A package that watches a filter's life wants this.
- **stands (required)**: the hold stands whenever the package cannot
  speak: it is not running, it has just started, or the extension host is down. A
  badge reader or a room smoke alarm wants this.

Turning that package off, turning extensions off, entering safe mode, and
removing the package each end its hold at once.

## Turning one package off, and removing it

**Turn off** stops a package's service and ends its hold; it keeps its
files, its data, and what you granted it. **Turn on** starts it again, and
also lets a package out of being set aside.

A package that keeps ending is **set aside** and is not tried again until
you turn it off and on: look at its log first.

**Remove** takes the package and its data away. Its data can hold the
credentials of services it talks to, so removing it removes those too.

## Its log

Every package's output is in the `forgeext` logger, under the package's id,
in the panel's Logs tab and in an export ([Logging](../logging.md)). The
machine's own account of what it started, froze, held, and set aside is
there too.

If you report a problem with the machine, turn extensions off first and see
whether it still happens: the project cannot debug a machine that runs
software it did not write.
