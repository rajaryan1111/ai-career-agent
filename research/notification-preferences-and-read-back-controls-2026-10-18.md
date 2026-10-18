# Quiet by default, and controls that are read back rather than believed — 2026-10-18

P8 item 5 is two requirements wearing one sentence: *preferences* for being told things, and *tests*
that pausing, resuming, stopping and withdrawing are true in the records rather than true because a
control was pressed. They are related: a notification is the one feature in this project that acts on
a person without being asked at that moment, so it has to obey every switch the person already has.

## The quiet default, and why it is not laziness

`NotificationPreferences()` is `cadence=OFF`. A missing preference reads as "no permission to
interrupt", never as "nothing configured, so use something sensible". The same rule governs a damaged
row: `preferences_from_payload` raises rather than falling back to a default, because silently
replacing somebody's stored choice with a default is exactly how an application ends up telling
somebody something at three in the morning. Schema 13 adds one small table, `app_preference(name,
value, updated_at)`, and an absent row is the default.

## What a notification may not do

Five independent refusals, all reported together rather than one at a time - a person asking "why did
I not get it?" deserves the whole answer, not the first clause of it:

1. the cadence is off - they never asked;
2. everything is stopped, or the authorisation was withdrawn - a person who stopped the application
   did not exempt the part that talks to them;
3. it is inside their quiet hours, taken from the standing authorisation (midnight-wrapping);
4. it is before the hour they chose;
5. one was already prepared for this period (day for daily, ISO week for weekly);
6. and, when they asked for it, nothing in the records needs them.

## The limit stated rather than hidden

There are two channels: the window they open, and a file on their own machine. No email, no push, no
system notification. `CHANNEL_LIMITS` carries the sentence each one shows - "nothing is sent anywhere
and nothing appears while the window is closed", "nothing is uploaded, and a file in a synced folder
is as private as that folder" - and a preference for a channel this build does not have is refused
rather than quietly downgraded to one it does. `--notifications` prints the same limit every time it
runs. **Delivery itself is still not built**: today the preference decides, and `--report` prints.

## Read back, not assumed

The second half is five tests that distinguish a control from its effect:

- **pause** writes `enabled=False` and is then *re-read from the database*; the assertion is on what
  came back, not on what was passed;
- a paused task **is not claimed by a worker** - the worker reads the schedule, so a pause is obeyed
  without anything telling the worker about it;
- **resume** schedules the next occurrence from now and replays nothing: `list_task_runs` is still
  empty, because resuming is not running;
- **worker status** with no worker running reports no lease and no running work, read from the rows;
- **stop-all** and **withdrawal** are read back from the stored authorisation, refuse a policy
  decision that would otherwise be allowed, appear in the operational report ("Everything is stopped,
  so none of it applies right now"), and silence notifications in the same breath.

A refused run is also pinned as refused rather than done, on the way back out of the store.

## Evidence

- `career_agent/notifications.py`, schema 13 in `career_agent/store.py`, `--notifications` in
  `career_agent/__main__.py`, README section "When it may tell you something".
- `tests/test_notifications.py` — 33 tests (preferences, the due decision, storage, read-back
  controls, four subprocess runs of the command).
- Suite after this increment: **2422 OK (skipped=13)**.
- Not built, and not claimed: delivery of any kind, a window surface for the preference, and
  scheduled preparation of the report.
