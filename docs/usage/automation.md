---
title: Notifications and automation
---

# Notifications and automation

Notifications and automation is an official extension package
(`org.openglow.automation`). It watches what the machine does and acts on
it by rules you make on its page:

- **It tells you** when a job ends, stops for an alarm, or pauses: on your
  phone through ntfy, Pushover, Telegram, or Discord, or to a webhook of
  your own.
- **It works your devices**: it turns a smart plug on for the exhaust when
  a job is about to start and off a while after the job ends, or asks
  Home Assistant to.
- **It publishes** the machine's events to an MQTT broker.
- **It can hold a job until the exhaust is on**: the job waits until the
  plug answers that it is on.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../safety/index.md)
    before you run a job. A rule that turns the exhaust on is a help, not a
    safety device: look at the exhaust before you start a job.

It is a package like any other ([Extensions](extensions.md)), with a service
that runs on the machine and a page in the panel.

## Installing it

Upload `org.openglow.automation-<version>.ffx` in the **Extension packages**
card. It asks to:

| Capability | For |
|---|---|
| Follow the machine's event stream | what its rules act on |
| Hold a job until it clears the hold | the rule that holds a job until the exhaust is on. Tick it |
| Keep running while a job is armed | so that it can tell you when a job pauses, and clear its hold. Tick it |
| Keep data on the machine | its rules |
| Connect to ntfy, Pushover, Telegram, and Discord | the notification services it knows |
| Connect to the places you name for it | your plug, your Home Assistant, your broker, your own ntfy server |
| Show a page of its own | where you make the rules |

Then press **Open** beside the package in the card.

## Telling it where your devices are

The package cannot reach anything on your own network until you say it
may. For each device - a plug, Home Assistant, a broker - type its address
and port on the package's card under **Places you named for it**, such as
`192.0.2.40:80` for a plug or `ha.lan:8123` for Home Assistant, and press
**Add**. The page lists what its rules still need, in exactly the form to
type. The package starts again each time you change the list.

## Making a rule

Choose one under **Add a rule** and press **Add**:

| Choice | What it makes |
|---|---|
| Tell me when a job ends | a notification when a job ends well |
| Tell me when a job stops for an alarm | a notification when a job ends in an alarm |
| Tell me when a job pauses | a notification with the reason: the lid, the cooling, or a hold |
| Run the exhaust (a smart plug) for each job | two rules: the plug on when a job waits for the button, and off a while after the job ends. A new job inside that while keeps it on |
| Hold each job until the exhaust is on | the plug turned on, and the job held until the plug answers that it is on |
| Send every event to MQTT | one message for each event, under a topic of its name |
| An empty rule | one to fill in yourself |

The two exhaust choices ask which plug you have - a Shelly, a Tasmota, or
a switch in Home Assistant - and where it is, and make the rules for it.

Each rule then opens in its editor: the events it acts on, an optional
condition on what the event says, and its actions. **Save** keeps it. A
rule's **Try it** button runs one action now, so you can see that your
phone gets the message or the plug clicks, and says what happened.

**Tokens and passwords are not shown again** once saved. The field says
*saved*, and leaving it empty keeps what you saved. To change one, type the
new one.

## The notification services

| Service | What it needs |
|---|---|
| ntfy | a topic name of your own, and the ntfy app subscribed to it. Pick a name nobody could guess: anyone who knows the topic can read it on ntfy.sh. Your own ntfy server is its address, added under Places you named for it |
| Pushover | your user key and an application token from the Pushover site |
| Telegram | a bot's token from @BotFather, and the chat's id |
| Discord | a channel's webhook address, from the channel's integrations |
| A webhook | any address that takes a POST: it receives the event as JSON |

## Holding a job for the exhaust

With the hold rule, a job that waits for the button is held until the plug
answers that it is on, with the reason *waiting for the exhaust to
confirm*. When the plug does not answer that it is on in time, the hold
stays, and says *it did not confirm*: the job does not fire. It goes when
the job ends. Every way out of an extension's hold works here too: turning
the package off, turning extensions off, or removing the package ends it
at once ([Holds](extensions.md#holds)).

## What it shows you

Under **What happened** the page lists the last actions, each done or
failed with the reason, and the last events it saw. The line at its top
says whether it is following the machine's events, whether it holds a job,
and which actions are waiting to run.

## What it does not do

It sends no email, and it does not reach an MQTT broker that takes only
encrypted connections. It reaches nothing you did not name, and never the
machine itself. How it works is on its technical page
([Notifications and automation](../technical/forgefirm/automation.md)).
