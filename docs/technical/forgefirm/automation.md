---
title: Notifications and automation
---

# Notifications and automation

`org.openglow.automation` is an official extension package: a native service
that turns the machine's events into actions by rules, and a page that edits
the rules. How to use it is on the operator's page
([Notifications and automation](../../usage/extensions/automation.md)); what a package
is, and what holds one, is [Extension packages](extensions.md).

## The service

One ARMv7 binary linked against the C library alone. Its source is its own
repository,
[openglow-org/forgefirm-extension-automation](https://github.com/openglow-org/forgefirm-extension-automation),
which is also an example of a package's repository
([A repository for your package](../../developers/extensions.md#a-repository-for-your-package)).
It carries its own small JSON, speaks the extension API through the kit's
`ffx.h` (a copy in its source), sends HTTP through the image's `curl`, and
speaks MQTT itself. Three threads:

- **the follower** reads the machine's events with `POST /v0/events`
  (starting at the present, so nothing from before the start is acted on)
  and matches each against the rules;
- **the worker** carries the actions out one at a time, so that a slow
  notification service delays the next action and nothing else;
- **the main thread** answers the page ([its calls](#the-pages-calls)) and
  starts the actions whose wait is over.

A `hold_until` has a thread of its own while it watches. Every wait is on
the monotonic clock: the machine keeps no date.

It asks for `events`, `hold` and `job_time.run` (both granted by the
operator), `storage:1`, `ui`, `net.outbound.operator`, and the four public
notification services by name (`ntfy.sh`, `api.pushover.net`,
`api.telegram.org`, `discord.com`, each on 443). `job_time.run` keeps it
running through the armed window, at the window's limits, so that a pause
is reported while it lasts and a hold it raised can be cleared.

## Rules

The rules are one file, `rules.json` in the package's data directory,
written whole and renamed into place, at most 48 KiB and 32 rules. A rule:

| Field | Is |
|---|---|
| `id` | 1 to 32 lowercase letters, digits, and `-`; unique |
| `name` | at most 64 bytes, for the page |
| `enabled` | `false` turns it off; absent is on |
| `on` | 1 to 8 event names, or `*` for every event. A name is any the machine may publish, so an event added later needs no new service |
| `if` | optional: at most 8 fields of the event's data, each equal to a string, a number, or `true` or `false` |
| `do` | 1 to 8 actions, run in order |

Any action may carry `after_s` (0 to 3600: it waits that long first) and
`cancel_on` (up to 8 event names: an event among them drops it while it
waits). That is how an exhaust runs on after a job and a new job keeps it
running. Text fields may carry `{event}`, `{data.<key>}` (a missing key is
empty), and `{data}`, the event's data whole as JSON. In a JSON body the
first two are escaped for inside a string; `{data}` is a JSON value and is
not.

| Action | Fields | What goes out |
|---|---|---|
| `notify`, service `ntfy` | `topic`, `server` (default `https://ntfy.sh`), `token`, `priority` 1-5, `title`, `message` | `POST <server>/<topic>`, the message as plain text, `Title`, `Priority`, and `Authorization: Bearer <token>` |
| `notify`, service `pushover` | `token`, `user`, `priority` -2-1, `title`, `message` | `POST https://api.pushover.net/1/messages.json`, form-encoded |
| `notify`, service `telegram` | `token`, `chat_id`, `title`, `message` | `POST https://api.telegram.org/bot<token>/sendMessage`, JSON `chat_id` and `text` |
| `notify`, service `discord` | `url` (the webhook), `title`, `message` | `POST <url>`, JSON `content` |
| `notify`, service `webhook` | `url`, `title`, `message` | `POST <url>`, JSON `event`, `data`, `title`, `message` |
| `http` | `method` (GET, POST, PUT), `url`, `body`, `content_type`, `auth` | the request, `Authorization: <auth>` when given |
| `mqtt` | `broker` (`host:port`), `topic`, `payload` (default: `{"event":..., "data":...}`), `retain`, `username`, `password` | one MQTT 3.1.1 publish at QoS 0 over plain TCP: CONNECT with a clean session, PUBLISH, DISCONNECT |
| `hold_until` | `url`, `match`, `timeout_s` 5-300 (30), `every_s` 1-10 (2), `reason`, `auth` | the package's hold raised with the reason (default "waiting for the exhaust to confirm"); a `GET` of the URL every `every_s` seconds until a 2xx answer holds `match` (compared as given, and again with the white space taken out of both), which clears the hold. Past `timeout_s` the hold stands with "it did not confirm within N s" |
| `clear_hold` | | the package's hold cleared |

Every address is `http://` or `https://`, a host, no user or password part,
at most 1024 bytes. A request goes through `curl` run with an argument vector,
no configuration file, the protocols held to http and https (redirects
too, at most 3), and a deadline of 10 s (7 s for a test from the page). A
`job.ended` event ends a `hold_until` that is watching and clears a hold the
package raised: a hold it put up for a job does not outlive the job.

What the service may reach is fixed when it starts: the four services above
by name, and whatever the operator named for it
([The operator's destinations](extensions.md#the-operators-destinations)).
An action to anywhere else is refused inside the sandbox, and the outcome
says so.

## Secrets

A token, a password, an `auth` value, a Pushover user key, and a Discord
webhook's address are secrets: the page is never shown one back. The service
replaces each saved one with the marker `__kept__`, and a rule saved with
the marker in that place keeps the value the saved rule had in the same
action of the same type. A marker with nothing to keep is refused, in words.
The rules file is the package's own, in its data directory, which only its
account can read.

## The page's calls

The page reaches its service only through the bridge
([A page and its own service](extensions.md#a-page-and-its-own-service)):

| Call | Answers |
|---|---|
| `GET /rules` | the rules with their secrets masked, the action types, and the machine's known events |
| `POST /rule` `{"rule": {...}}` | saves one rule (a new id adds it, a known one replaces it); the rules again |
| `POST /rule/delete` `{"id": ...}` | deletes one; the rules again |
| `POST /test` `{"rule": id, "action": n}` | runs that saved action now with the event `test`; `{"ok", "detail"}`. A hold is not tried from here |
| `GET /status` | whether it follows the machine's events, its hold, the waiting actions, and the last 24 outcomes and 16 events |

A rule out of form is refused with its first fault, 400 in words; one call
saves one rule, so that a rule fits the bridge's 4096 bytes. The page tells
the operator which places its rules still need, from `ffx.self()`'s list of
where the service may connect.

## Proof

forgeext's CI runs the package's unit tests (its JSON parser against every
way of not being JSON and past each limit; the rules' form and every
refusal; secrets masked and kept; matching; the text put in; a URL's
destination; MQTT packets byte for byte and a publish against a stand-in
broker) and `automation_test.py`: the service, built for the CI host, under
the real extension host in network namespaces with the image's deny rules,
against a stand-in forgectrl publishing events and a peer namespace with a
notification server, a smart plug, and a broker. It holds the rules as the
page saves them, a secret kept and never shown, a test refused until the
operator names the place and reaching it after, a notification in ntfy's
form, a condition that holds one back, the exhaust on and off and its run-on
canceled by the next job, an MQTT publish, a job held until the plug is on
and held in words when it never is, and the rules across a restart. CI also
builds it for the machine and lints it as it ships.
