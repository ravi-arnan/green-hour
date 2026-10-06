---
name: grass-report
description: Use when the user asks how their week went, asks for their streak or stats, or when the weekly Green Hour summary cron fires — e.g. "how many walks this week?", "what's my streak?", "what have I been seeing?". Reads the journal and reports. Do NOT use to log a new walk (use log-outside) or to recommend a time to go out (use green-hour-nudge).
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [outdoor, journal, report, touch-grass]
---

# Green Hour — the report

Read the journal back to the user: how often they got out, their streak, and —
the interesting part — what they have been noticing.

## Procedure

```bash
/opt/hermes/.venv/bin/python \
  /opt/render-tools/skills-local/grass-report/scripts/report.py
```

Prints a short human summary and a JSON object. Relay the human summary.

```
🌿 Green Hour — 2026-10-06 to 2026-10-12
Out 5 day(s), 7 walk(s). Streak: 5.
Most heard: magpie×4, kookaburra×2.
Noticed: first jacaranda blooms, cold wind from the south.
```

## Refreshing the public page

The public streak page (a Render static site) reads
`web/data/journal.json`. To refresh it:

```bash
/opt/hermes/.venv/bin/python \
  /opt/render-tools/skills-local/grass-report/scripts/report.py --publish
```

This exports the snapshot and pushes it to the repo via the GitHub API, which
triggers the static site's redeploy. Requires `GITHUB_TOKEN` (repo scope) and
`GITHUB_REPO` (e.g. `you/green-hour`). Use `--export` to write the file locally
without pushing.

Run this weekly, or after logging a walk if the user is showing the page to
someone. Never run `--publish` without both env vars set — it will fail loudly
rather than half-update anything.

## Failure handling

- Empty journal → the summary says zero walks. That is correct, not an error.
- `--publish` fails → the local snapshot may already be written; report the
  error and do not claim the page updated.

## Acceptance test

1. With at least one logged walk, run the plain command → the counts match the
   journal and the streak matches `log-outside`'s output.
2. `--export` → `$GREENHOUR_HOME/journal.json` exists and is valid JSON with a
   non-empty `entries` array.
3. `--publish` with credentials → the file appears in the repo and the static
   site redeploys.
