---
name: green-hour-nudge
description: Use when it is time to send the user their outdoor nudge — i.e. a scheduled Green Hour cron job fired, or the user asks "when should I go outside?", "is it a good time to walk?", or "what's the weather for a walk?". Computes the best daylight window from Open-Meteo and returns a single line to relay. Do NOT use this to log a walk the user has already taken (use log-outside) or to summarise past walks (use grass-report).
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [weather, outdoor, cron, touch-grass]
---

# Green Hour — the nudge

Pick the best window today to be outside, and say so in one line. This is the
part of Green Hour that starts the loop.

## What it does

Calls the free, keyless [Open-Meteo](https://open-meteo.com) forecast, scores
every daylight hour in the next few hours on rain, temperature and wind, and
returns the best one. No API key, no vendor, nothing to bill.

## Prerequisites

- `GREENHOUR_LAT`, `GREENHOUR_LON`, `GREENHOUR_TZ` are set.
- Network access (the container has it).

If the coordinates are missing the script exits `2` with a clear message; tell
the user to set them in the service's Environment tab rather than guessing.

## Procedure

Run exactly this:

```bash
/opt/hermes/.venv/bin/python \
  /opt/render-tools/skills-local/green-hour-nudge/scripts/nudge.py
```

It prints two things: a human line, then a JSON object.

```
🌿 19 °C, partly cloudy, 10% rain — clearest window is 16:00–17:00. Go find some grass.
{"ok": true, "message": "...", "window": {...}}
```

Then **relay the human line to the user verbatim** on the channel they use
(Telegram). Do not add commentary, do not pad it, do not ask a follow-up
question. The whole value is that it is one line they can act on.

If there is no good window the line is:

```
🌧️ No good window today (nothing dry in the next stretch). Read a book instead — the grass will wait.
```

Relay that just the same.

## Failure handling

- Exit `1` → forecast unavailable. Relay nothing; log the error. Do **not**
  invent a weather forecast from memory.
- Exit `2` → missing configuration. Tell the user which env var to set.

## Acceptance test

1. `GREENHOUR_LAT`, `GREENHOUR_LON` set to a real place.
2. Run the command above.
3. Expect exit `0`, a `🌿` or `🌧️` line, and a JSON object whose
   `window.start`/`window.end` fall within the next few hours and are
   daylight hours for that location.
