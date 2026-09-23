---
title: The controller port
---

# The controller port

The Grbl socket is one session: a new connection displaces the sender. The
controller port is the second channel beside it, the way the machine daemon
jogs the head and reads the controller's state while LightBurn stays
connected. It carries no program and no laser command, and it never becomes
the sender.

- The routes that reach it, and who may call them, are on
  [forgectrl](forgectrl.md#http-api).
- The motor release and the manual home it carries are on
  [Homing](homing.md#the-motor-release).

## The socket

`/run/forgefirm/grbl.ctl` is a Unix stream socket the GRBL controller creates
at start, mode 0600, so root alone can open it. It is served from the
protocol thread's own poll set: the port adds no thread and no lock to the
controller.

It takes **one client**, and forgectrl is that client. A second connection
is refused and never displaces the first. A client that closes and connects
again at once is served: the controller looks for the old connection's
hang-up before it judges the new one.

**The client is the jog's dead-man.** When the client's connection closes,
a port jog in progress is canceled. forgectrl therefore holds one connection
for as long as the controller lives, and connects again after a controller
restart.

## Requests and replies

A request is one line, and so is its reply. The port reads nothing more
while a line it injected waits for its status, so replies keep the order of
the requests.

| Request | Reply | What it does |
|---|---|---|
| `state` | One JSON object | `state` (the Grbl state name), `sender` (a Grbl client is connected), `port_jog` (the jog in progress is the port's), `released` (the X and Y motors are released), `mpos` (machine position, mm), `homed` (the homed-axes mask), `envelope_open` (the bed check's envelope is open), `mcode` (the M-code a job waits at, `{"seq", "code", "words"}`, or `null`) |
| `jog <words>` | `ok`, `error:<n>`, or `busy:<why>` | Runs `$J=<words>`. `<words>` is held to the characters a jog needs (capital letters, digits, `.`, `-`, `+`, and spaces); anything else answers `error:invalid` |
| `cancel` | `ok` | Cancels a port jog in progress. It does nothing to a sender's own jog |
| `release` | `ok`, `error:<n>`, or `busy:<why>` | `$MD`: releases the X and Y motors |
| `energize` | `ok`, `error:<n>`, or `busy:<why>` | `$ME`: energizes them |
| `home` | `ok`, `error:<n>`, `error:mode`, or `busy:<why>` | `$H`, only while `homing_mode = manual`, where it moves nothing. Under every other method it answers `error:mode`: a homing session is a Grbl client's to start |
| `envelope open\|apply` | `ok`, `error:homed`, or `busy:state` | The Setup page's bed check: `open` sets X's and Y's far edges to the axis travel plus 30 mm, and `apply` sets them from `envelope_x_mm` and `envelope_y_mm` again, without a home ([Homing](homing.md#the-far-edges)). Both need X and Y homed (`error:homed`), and the machine Idle with no armed window (`busy:state`) |
| `mcodes <list>` | `ok` or `error:invalid` | The M-codes packages answer now: `-` for none, or numbers from 160 to 179, each once, comma separated. A list with any other form leaves the table as it was ([A package's M-code](extensions.md#a-packages-m-code)) |
| `mcode_result <seq> ok\|fail [<words>]` | `ok`, `error:stale`, or `error:invalid` | The answer to the M-code `state` names under `seq`. The words are printable, with no brackets, at most 96 bytes; they go to the Grbl client in a `[MSG:]`. An answer under another `seq`, or a second one, is stale |

`error:<n>` is the core's own status for the injected line (`error:15` for a
jog past the soft limits, `error:9` in an alarm). `error:aborted` means the
controller was reset before the line's status came back. The `busy` reasons:

| Reply | Meaning |
|---|---|
| `busy:released` | The X and Y motors are released. The core would refuse the jog as well (the release holds the alarm state); this reply says why |
| `busy:state` | A jog needs Idle, or a port jog already in progress. `release`, `energize`, and `home` need Idle or Alarm |
| `busy:sender` | The Grbl client sent a line with something in it within the last 0.3 s, has such a line waiting, or is in the middle of one |
| `busy:mcode` | A job waits at an M-code a package answers: it is Idle there, and it is still the job |

Every port jog puts `[MSG:Panel jog]` on the Grbl client's console, and
`$MD`, `$ME`, and `$H` report there as they do when the client sends them.

## Three operation sets

`state`, `jog`, and `cancel` are the **package set**: what the panel's Jog
card, a scoped token, or any other client of forgectrl's motion routes can
reach.
`release`, `energize`, `home`, and `envelope` are the **panel set**: they
belong to the operator's own control panel and to nothing else.
`mcodes` and `mcode_result` are the **daemon set**: forgectrl's own M-code
relay says them, and no route reaches them.

The port itself does not tell the sets apart, since it has one client.
forgectrl does, in one place (`grblport.c`): each route names the set it
speaks for, and an operation outside that set is refused before anything is
written to the socket. An argument that carries a line break is refused the
same way, because it would be a second request that had passed no check.

## Why the only motion is a jog

Under an open armed window, with `M3` modal and `S` above zero, an injected
`G1` would fire. A jog cannot, and the reason is one site: the stream engine
masks FIRE for as long as the core is jogging
([The grblHAL driver](grblhal-driver.md)). No other motion has that
property. So the port never forms a line that does not begin with `$J=`,
and `G0`, `G1`, `G2`, `G3`, `S`, `M3`, and `M4` are not in either set.

## The sender goes first

A port operation is never a sender change, and it never takes the machine
from the Grbl client:

- A port jog is refused while the client is active (`busy:sender`).
- The first byte of a line from the client that arrives while a port jog
  runs cancels the jog. A status poll (`?`) and the other realtime characters
  are not a line: they are served as always and cancel nothing.
- **An empty line is not the client speaking either.** LightBurn polls `?`
  with an end of line behind it, about twice a second. The `?` never reaches
  the input ring; the end of line does, as an empty line, which the core
  answers `ok` in every state. It does not refuse a port jog, it does not
  cancel one, and it passes the hold: it is answered during a port jog as at
  any other time, so the client's `ok` count never lags. A port line that
  finds only such empty lines in the ring waits (at most 0.1 s) for the core
  to read them instead of answering `busy:sender`.
- A client's line with something in it waits, unread, until the core is idle
  again, and then runs: the client sees a short delay and its own `ok`, never
  the `error:9` a line draws during a jog.
- The cancel is the core's motion-cancel flag, not the jog-cancel command.
  The core answers that command by flushing its input ring, which would
  discard the client's waiting line without a status.
- A sender's own jog is untouched: the port neither cancels it nor chains
  onto it.
- **An open envelope is the port's jogs' alone.** While the bed check's
  envelope is open, the client's lines wait as they do during a port jog,
  and the first one closes it (the far edges it had before it was opened)
  before the core reads the line, with `[MSG:Bed check envelope closed: a
  sender line]` on the client's console; a port jog it meets is canceled
  first. A status poll and an empty line leave it open. A soft reset, a
  home, and the port's client going away close it as well. No program ever
  runs in the widened envelope.

## Verification

Host tests on the null-sink controller build, in the driver's CI:

- `ctlport_test.py`: every reply routed to its source with the Grbl client's
  response count exact (CR LF clients and empty lines included); the
  sender-goes-first hold; **a client polling `?` with an end of line behind
  it (LF and CR LF): every port jog accepted, a 60 mm port jog run whole,
  one `ok` per poll, and a real line still canceling a port jog**; the
  refusals; one client, and a reconnect right after a close; the dead-man;
  the port across a soft reset; and **every operation of both sets under an
  open armed window with `M3` modal and `S500` ships no FIRE tick**.
- `manual_home_test.py`: the panel set's `release`, `energize`, and `home`,
  with each energize written exactly once.
- `mcode_test.py`: the daemon set's `mcodes` and `mcode_result`, and the
  wait at an M-code a package answers
  ([A package's M-code](extensions.md#a-packages-m-code)).
- `envelope_test.py`: the far edges from `envelope_x_mm` and
  `envelope_y_mm` and their bounds, the panel set's `envelope open` and
  `apply` and their refusals, and **the client's first line (never a status
  poll or an empty line) closing an open envelope before the core reads
  it**, as a soft reset and the port client going away do.

forgectrl's side is `grblport_test` in forgectrl's CI: the sets, a
refused operation leaving the socket untouched, one kept connection, a
controller restart, and a port that never answers; `mcode_test` holds the
daemon set to its one caller.

On the bench, three release acceptance tests
([Release acceptance](../../developers/acceptance.md)): `motion.port-jog`
(the jog beside a connected client, the cancel, the client going first, the
bound, the release and the energize by their routes), `laser.port-dark` (a
lit cut opens the armed window and leaves `M3` modal, and the port's jogs
under it ship dark by the LASER_ON sample count, the HV current, and the
head's beam detector), and `motion.release`.
