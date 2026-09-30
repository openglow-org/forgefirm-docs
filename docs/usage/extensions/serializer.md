---
title: Serializer
---

# Serializer

Serializer is an official extension package (`org.openglow.serializer`).
It marks serial numbers, dates, and your own text on one item or on a grid
of items, cycle after cycle. You load the items, close the lid, and press
the button on the machine. When the cycle is done, you open the lid, change
the items, and close it: the next cycle goes out with the next numbers, and
you press the button again.

!!! danger "Read the Safety page first"

    ForgeFIRM is not the manufacturer's firmware. Read [Safety](../../safety/index.md)
    before you run a job.

It is a package like any other ([Extensions](index.md)): a page on the
panel's **Extensions** tab, and a service on the machine that keeps your
profiles and numbers and runs the cycles. The cycles go on with the page
closed.

## Installing it

Get it from the [catalog](index.md#the-catalog) on the **Extension
packages** card. You can also upload `org.openglow.serializer-<version>.ffx`
from the releases of its repository,
[openglow-org/forgefirm-extension-serializer](https://github.com/openglow-org/forgefirm-extension-serializer/releases).
Either way it reads as **Official**. It asks to:

| Capability | For |
|---|---|
| Show a card of its own on the Extensions tab | its page |
| Read the machine's status | the lid, the head's position, and the state of each cycle |
| Follow the machine's event stream | the lid opening and closing |
| Keep data on the machine | your profiles, counters, and history |
| Run a program as the machine's one sender | each cycle's program |
| Disconnect the Grbl sender while it uses the machine | the time a run goes on |
| Keep running while a job is armed | following each cycle, and stopping it when you ask |

The last three are yours to grant: tick them when you install it, or the
install is refused.

## A profile

Everything one job needs is a **profile**: the text, its numbers and dates,
the layout, the laser settings, and your notes. Pick one at the top of the
page, or make one with **New** or **Copy**. Every change is saved as you
make it. A new machine starts with an example profile.

The preview beside the settings shows what the next cycle marks: the first
item's text, drawn in its font, with its size, and every item on the bed.
The next cycle's numbers and today's date are in it, and it names anything
that would stop the cycle, such as text that runs past the work area.

### Text

Type the text in the box. It can have several lines. Fields in braces are
filled in for each item: `{Serial}` is a counter, `{Year}` is part of the
date, `{Luhn}` is a check digit. Pick a field from the lists under the box
to put it where the cursor is. Write `{{` or `}}` for a brace as text.

**Font.** Single-line fonts are lines the laser follows: fast and clean,
for small text and for burning. Outline fonts are shapes, **filled** line
by line, traced as an **outline**, or both. The font picker shows each font
drawn in itself. All the fonts are on the machine, so it needs no internet
connection.

**Text height** is the height of the capital letters. **Line spacing** is
the distance from one line to the next, in text heights. **Letter spacing**
adds space between letters.

### Numbers and dates

A **counter** holds the next number to mark. Its settings:

| Setting | What it does |
|---|---|
| Next | The number the next item gets. Change it to start somewhere else |
| Counts in | Digits, letters, digits and letters, hexadecimal, or your own characters, lowest first. Letters can leave out I, O, and Q |
| Width | How many characters, padded with leading zeros (or A for letters). 0 is no padding |
| Step | How much it moves on each time |
| First, Last | Where it starts over, and the highest it goes. A blank Last is as high as the width allows |
| Moves on | For each item, once each cycle (a lot number), or when another counter starts over |
| At its last value | The run stops, or the counter starts over at First |

Two counters make an odometer: `1{Letter}-{Digits}` with `Digits` of width
2 starting over, and `Letter` moving on when `Digits` starts over, goes
1A-98, 1A-99, 1B-00.

The **date fields** are `{Year}` (2026), `{Year2}` (26), `{Year1}` (6),
`{Month}` (09), `{MonthName}` (Sep), `{Day}` (30), `{DayOfYear}` (273),
`{Week}` (the ISO week), `{WeekYear}` and `{WeekYear2}` (the ISO week's
year), `{Weekday}` (Monday is 1), `{WeekdayName}` (Wed), `{Hour}`, and
`{Minute}`. The date and time are your computer's, read when you press
**Start**; the machine keeps no date of its own. Each cycle takes the time
it goes out. Use `{WeekYear2}{Week}` rather than `{Year2}{Week}` for a
year-and-week code, since a week can start in the year before.

A **date code** is your own letters or numbers for a part of the date:
A to L for the months, say, or a letter for each year from a first year
you set.

A **check digit** is worked out from the letters and digits before it on
its line:

| Field | Scheme |
|---|---|
| `{Luhn}` | Luhn, from the digits |
| `{GS1}` | GS1 mod 10 (weights 3 and 1), from the digits |
| `{Mod11}` | Mod 11 (weights 2 to 7), from the digits; 10 is written X |
| `{Mod36}` | ISO 7064 mod 37,36, from the letters and digits |

### Layout

**Start point.** The grid starts where the head is when you press
**Start**, or at a position you set. With the head, align it first: jog it,
or use [Visual alignment](alignment.md) on your jig's corner. The head goes
back to the start point at the end of each cycle.

**First text box.** Its top-left corner is this far to the right of the
start point and toward the front of the machine. The box is the area you
mark on each item. The text sits in it left, centered, or right, and at its
top, middle, or bottom. **Fit to the text** makes the box just hold the
text. **Turned** turns the box and its text by 90, 180, or 270 degrees.

**Grid.** Set how many items across and down, and the spacing from one box
to the next, corner to corner. Items are numbered row by row from the
back-left, and each takes the next numbers in that order. On the bed
preview, click an item to leave it out (an empty place in a jig), or to put
it back.

### Laser

**Material height** is the top of your material, where the laser focuses.
With the **crumb tray** out, it is measured from the floor of the machine.

**Lines** are for single-line fonts and outlines; **Fill** is for filled
outline fonts. Each has a power, a speed, and a number of passes. The fill
also has a **line interval**, the distance between its lines.

**Between cycles:** how long a cycle waits for the button (4 minutes by
default) before it is canceled, and how long the lid must stay open for a
closing to count as a reload (2 seconds by default).

### Notes

Notes are for whoever runs the job: how to set up the jig, where to align
the laser. They show above the **Start** button.

## Running it

1. Home the machine ([Homing](../homing.md)). Place the items, and put the
   head on your start spot if the profile starts where the head is.
2. Press **Start**. The Grbl sender is disconnected for the whole run, as
   with the alignment tool.
3. With the lid closed, the first cycle goes out and the machine's button
   lights. Nothing moves until you press it. If the lid is open, close it
   first.
4. Press the button. The cycle is marked, and the head goes back to the
   start point.
5. Open the lid, change the items, and close it. The next cycle goes out
   with the next numbers. Press the button again.

The page shows each step and the numbers of the cycle in hand. Stop the run
with **Stop** while a cycle waits for the button, or with **Stop after this
cycle** while one is marked.

### Numbers are never marked twice

A cycle's numbers count as used once the machine starts it after your
press. A cycle that is canceled before then gives its numbers back, and
the next cycle marks them:

- you press **Stop** while it waits for the button;
- nobody presses the button in time (the page then offers **Send again**);
- you open the lid while it waits for the button.

When the service cannot tell whether a cycle was marked, its numbers count
as used, so a number is left out rather than marked twice. The **History**
at the bottom of the page lists each cycle with its first and last text.

### Stopping a cycle that is being marked

- **Stop after this cycle** lets it finish, then ends the run.
- **Opening the lid** stops it at once: the head goes back to where the
  cycle started, and its numbers count as used. Close the lid for the next
  cycle.
- **Stop now** stops it at once too, but leaves the machine in an alarm.
  Clear the alarm from your Grbl sender (`$X`) or home the machine before
  the next run.

## Limits

- One cycle is one program, and the machine takes a program of 2 MB at
  most. The preview shows each cycle's size. A big grid of filled text can
  pass it: mark fewer items at a time, widen the fill's line interval, or
  use a single-line font.
- Filled text takes the machine a few seconds to lay out. The next cycle is
  made while you change the items, so it is ready when the lid closes.
- The work area is checked against the machine's default, 495 by 279 mm.
