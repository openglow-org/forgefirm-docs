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

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job.

What a package runs inside, the API it reaches the machine through, and how
a hold reaches the cooling engine are in
[Extension packages](../technical/forgefirm/extensions.md).

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
| A key you added to this machine | **Community** | Your login, and you type `I UNDERSTAND` |
| Nobody the machine trusts | **Unverified** | Your login, and the machine's button **held** while you press Install, as for unsigned firmware |

A signature says who made a package. It does not say the package is safe,
correct, or useful. The project does not review a package unless it is
signed with the OpenGlow extension key.

Some of what a package asks for needs a grant from you for that one
package, and the card shows those as tick boxes: holding a job, running a
program as the sender, and keeping running while a job is armed. A package
gets nothing you do not tick. An update that asks for more shows you what
is new.

**Discard** removes an uploaded package without installing it. The upload
and the install are refused while a job runs.

## What a package may do, and what it may not

A package runs as its own account, with limits on processor time, memory,
and the number of its processes. It sees its own files and the read-only
parts of the system, and nothing else on the machine. It reaches the
machine only through the extension host, which answers from what you
granted: the status, the cooling status, the mode, and its own hold. It can
send to the network only where its capabilities say, and never to the
machine itself.

No package reaches the laser, the motion hardware, the cooling hardware,
the cameras, the settings, the firmware, or your login directly. **While a
job is armed every package is frozen**, unless you granted one the right to
keep running, and that one runs under tighter limits for the length of the
job. The lid, the interlock, the armed window and its button, the cooling
gates, and the limits on motion work the same with extensions on: the most
a package can do to a job is hold it.

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
in the panel's Logs tab and in an export ([Logging](logging.md)). The
machine's own account of what it started, froze, held, and set aside is
there too.

If you report a problem with the machine, turn extensions off first and see
whether it still happens: the project cannot debug a machine that runs
software it did not write.
