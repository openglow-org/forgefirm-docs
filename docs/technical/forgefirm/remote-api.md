---
title: The remote API
---

# The remote API

A program on the network that is not a browser (a script, such as the
[notifier](#examples) that tells somebody a job has ended) reaches the
machine with a **scoped token**:
a credential the operator makes in the control panel, which reaches the
routes it was granted and nothing else. It needs no login session. This page
is for whoever writes that program. The routes themselves are documented on
[forgectrl](forgectrl.md#http-api); the guard that judges a token is described
there too ([Scoped tokens](forgectrl.md#scoped-tokens)).

## Making a token

On the panel's System tab, under **API tokens**: a name (what will use it),
the capabilities it holds, **Create token**
([The control panel](../../usage/control-panel.md#api-tokens)). The token is
shown once. The machine keeps its SHA-256 and cannot show it again; a lost
token is revoked and a new one made. Give each program its own token, so one
can be revoked without the others. A machine holds sixteen at most.

A token is `fft_` and 32 hexadecimal digits.

## Sending it

Over HTTPS, in a header:

```sh
curl -k -H "Authorization: Bearer fft_0123456789abcdef0123456789abcdef" \
    https://forgefirm-1a2b/status
```

`X-ForgeFIRM-Token: fft_...` is accepted as well. The certificate is
self-signed, made at the machine's first start and kept across updates; pin
its fingerprint (`GET /cert.pem`, or the panel's Setup card) where the client
can, and skip verification (`-k`) only where it cannot.

**HTTPS only.** A token sent over plain HTTP from another host is refused,
and the machine's log names it: it has crossed the network in the clear, and
the thing to do is revoke it.

A camera route also takes a token as the `key` query parameter, because an
`<img>` tag and most camera integrations cannot send a header:

```text
https://forgefirm-1a2b/cam/stream?cam=lid&key=fft_0123456789abcdef0123456789abcdef
```

A URL ends up in a browser's history, a proxy's log, a referrer. So the token
in it must hold camera capabilities and nothing else: make one token for the
camera consumer and another for anything more. A token that holds more is
refused in a URL, and the machine's log names it. No other route reads a
token from the URL.

## Capabilities

| Capability | Routes |
|---|---|
| `machine.read` | `GET /status`, `GET /cool/status`, `GET /mode`, `GET /grbl/settings`, `GET /motion/state`, `GET /job` |
| `events` | `GET /events` ([the event stream](forgectrl.md#the-event-stream)): three streams in all, one per address |
| `camera.lid`, `camera.head` | `GET /cam/snapshot`, `GET /cam/stream`, `GET /cam/h264` for the camera named by `cam` (the lid camera when absent); `GET /cam/status` with either |
| `motion.jog` | `POST /motion/jog`, `POST /motion/cancel`: a bounded jog with the laser off, beside a connected Grbl client, and its cancel ([the controller port](controller-port.md)) |
| `motion.job` | `POST /job`, `POST /job/abort`: a G-code program run with the machine as its own sender ([the job runner](forgectrl.md#the-job-runner)) |

The list is closed. A token cannot be granted anything outside it, so no
token reaches the settings, the controller mode, the controller's start and
stop, the thermal hardware, a diagnostic, a setup check, an update, the
firmware slots, SSH, the camera key, the fuse identity, or another token.

`motion.job` moves the head and can fire the laser, under the rules every
sender is under: every arm gate stands, and the first laser-on line of every
job waits for a press of the button on the machine. A job is refused while a
Grbl client is connected or anything else holds the machine. `unlock=1`
rides on `motion.job`: the program that may run a job may clear the alarm
its own abort left.

While `panel_open_reads` is 1 (the default) the read routes answer any client
on the LAN without a token, over HTTP as well. `machine.read`, `events`, and
the camera capabilities matter once the operator sets it to 0, and they are
the way to say what a client is for in either case.

## What the machine answers

A request that presents a scoped token is judged by that token alone. It is
never helped by anything else the request carries, and a refusal is a 403
with the reason in words:

| Answer | Meaning |
|---|---|
| `this token does not hold <capability>` | The route is one a token can reach, and this one was not granted it |
| `no scoped token reaches this route` | The route is the panel's |
| `a scoped token is accepted over HTTPS only` | Sent over plain HTTP from another host. Revoke it |
| `a token in a URL may hold camera capabilities only` | Sent as `?key=` while holding more than a camera. Send it in a header, and consider it seen by whatever logged the URL |
| `authentication required` | Not a token of this machine's: mistyped, or revoked |

Past the guard, a route answers a token exactly as it answers the panel:
`409` with the holder's name while something
[holds the machine](forgectrl.md#the-machine-lease), `409` from a jog while
the controller is not idle, `400` with the offending line for a program the
job runner refuses.

The origin checks that protect the panel from a hostile page (an address
literal or the machine's own name as `Host`, no cross-site fetch) do not
apply to a request that presents a scoped token. A page in a browser cannot
put the header on a cross-origin request, and a client that is not a browser
sends whatever `Host` it likes.

## Examples

Following the event stream:

```sh
curl -k -N -H "Authorization: Bearer $TOKEN" https://forgefirm-1a2b/events
```

A 1 mm jog toward +X, and its cancel:

```sh
curl -k -X POST -H "Authorization: Bearer $TOKEN" "https://forgefirm-1a2b/motion/jog?x=1&feed=1200"
curl -k -X POST -H "Authorization: Bearer $TOKEN" https://forgefirm-1a2b/motion/cancel
```

A whole client, in Python's standard library:
[`examples/remote/notify.py`](https://github.com/openglow-org/forgectrl/tree/main/examples/remote)
in the forgectrl repository follows the event stream with an `events` token
and tells somebody when the machine wants them, by a webhook or a command. It
pins the machine's certificate by the fingerprint the panel shows before it
sends the token, which is the way to talk to a self-signed machine.

Running a program, then reading its record:

```sh
curl -k -H "Authorization: Bearer $TOKEN" -F name=myscript -F program=@job.gcode \
    https://forgefirm-1a2b/job
curl -k -H "Authorization: Bearer $TOKEN" https://forgefirm-1a2b/job
```
