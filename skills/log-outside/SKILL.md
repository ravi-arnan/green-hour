---
name: log-outside
description: Use when the user sends a voice note, a photo caption, or a short text describing a walk they are on or just finished — e.g. "log this", "just got back", a bare voice memo, or "I heard an owl on the ridge". Transcribes if needed, extracts a structured field entry, stores it, and reports the streak. Do NOT use for deciding when to go out (use green-hour-nudge) or for weekly summaries (use grass-report).
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [outdoor, journal, voice, touch-grass]
---

# Green Hour — logging a walk

The user is outside (or just back) and wants it counted. They should never have
to fill in a form; they talk, and this handles the rest.

## Procedure

**If they sent a voice note**, Hermes downloads it to a local path. Pass that
path:

```bash
/opt/hermes/.venv/bin/python \
  /opt/render-tools/skills-local/log-outside/scripts/log_walk.py \
  --audio /path/to/voice-note.ogg
```

**If you already have text** (they typed it, or you transcribed some other
way), pass it directly:

```bash
/opt/hermes/.venv/bin/python \
  /opt/render-tools/skills-local/log-outside/scripts/log_walk.py \
  --transcript "misty loop around the park, kookaburras, wet grass"
```

The script prints a short human line and a JSON object. **Relay the human line
to the user.** Do not restate the JSON, do not editorialise, do not ask them to
confirm the fields — the entry is already saved.

## What it does internally

1. Transcribes with hosted open-weight Whisper (`whisper-large-v3-turbo`).
2. Extracts a `FieldEntry` — `outdoors`, `summary`, `location`, `weather`,
   `mood`, `notable[]`, `species[]` — using the Tinker-tuned model, falling
   back to the baseline if the adapter is unavailable.
3. Appends the row to the SQLite journal on the persistent disk and recomputes
   the streak.

## Judgement calls

- **Indoors or ambiguous → it does not count.** The model sets `outdoors=false`
  and the streak is untouched; the entry is still stored for honesty. Relay the
  "sounded indoors" line and move on. Only use `--force` if the user explicitly
  says the model got it wrong.
- **Never invent a walk.** If the transcript is empty or unparseable, say so.
- **Privacy:** the transcript stays in the container's journal. Do not paste it
  into chat or send it anywhere else.

## Acceptance test

1. Log a real outdoor voice note:
   `--audio <path>` → exit `0`, `outdoors: true`, streak increments.
2. Log a transcript of something clearly indoors ("I'm at my desk, the fan is
   humming") → `outdoors: false`, streak unchanged.
3. `--dry-run` → prints the entry, `stored: false`, journal unchanged.
