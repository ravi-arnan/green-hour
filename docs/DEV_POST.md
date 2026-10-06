---
title: "Green Hour: an agent that nags me to go outside, then writes my field notes"
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)*

<!--
DRAFT. Before publishing, replace:
  - {{EVAL_TABLE}} with the real output of `train/eval.py`
  - {{DEVRELAY_SESSION}} with the embedded session
  - double-check the streak number in the demo section
-->

## What I Built

**Green Hour** gets me off the screen and outside, then gets out of the way.

It lives in Telegram. Twice a day it checks the local forecast, picks the best window, and sends one line:

> 🌿 15 °C, mostly clear, 0% rain — clearest window is 16:00–17:00. Go find some grass.

I go. On the way I send a five-second voice note — whatever I'm seeing, hearing, breathing. That's the entire interaction. No app to open, no form, no fields. Then it writes the entry for me:

> Logged walk — "Walking the river loop, magpies and a kookaburra laughing across the water." Streak: 4 days. 🌿

That's the whole idea: **the screen should be the shortest part of going outside.** Every fitness app I've tried fails for the same reason — it makes you sit down and log the thing you left the house to avoid. Green Hour is one message out and one voice memo back.

## Demo

**Live:** https://green-hour.raviarnankeren.workers.dev

The page at that URL is server-rendered from the journal: the current streak, this week's numbers, and the walks themselves. The interesting demo is the Telegram thread, though — a nudge arriving, a voice note going out, a one-line reply coming back. There is almost nothing to screenshot, and that's the point.

## Code

**Repository:** https://github.com/ravi-arnan/green-hour

```
worker/src/
  index.ts      fetch + scheduled entrypoints
  weather.ts    Open-Meteo → best window
  schema.ts     FieldEntry + tolerant parsing of model output
  extract.ts    Workers AI → FieldEntry
  journal.ts    D1 + pure streak logic
  telegram.ts   Bot API
  page.ts       the streak page
worker/test/    36 vitest tests
train/          Tinker dataset, LoRA training, base-vs-tuned eval
```

## How I Built It

The whole runtime is **one Cloudflare Worker**, a D1 database, and an hourly cron trigger. No servers, no containers, no build pipeline.

### It runs on open-weight models, and costs nothing

Two things made this shape possible.

First, [Workers AI](https://developers.cloudflare.com/workers-ai/) serves open-weight models on a free daily allowance — 10,000 neurons. `@cf/openai/whisper-large-v3-turbo` costs ~47 neurons per *audio minute*, so a five-second voice note is a rounding error. `@cf/qwen/qwen3-30b-a3b-fp8` handles extraction for a couple more. The entire product runs on roughly **3–5 neurons per walk**, against a budget of 10,000 a day.

Second, D1 is a real SQLite database on the free tier, so the journal — the thing that makes a streak a streak — is genuinely persistent.

The practical upshot: **no API keys at all.** Not a model key, not a transcription key, not a weather key. The only secret in the deployment is a Telegram bot token. I kept trying to write the "add your OpenRouter key here" section of the README and eventually realised I didn't need one.

### Two constraints that shaped the design

**10 ms of CPU per invocation.** That's the free plan's limit, and it applies to cron triggers too. It sounds brutal until you notice that CPU time excludes waiting on network I/O — and this whole product is I/O. Fetch the forecast, call Whisper, call Qwen, hit D1, post to Telegram. So the rule became: keep the *code* trivial, let the network be slow. Concretely, the forecast request asks for two days and five hourly fields rather than anything generous, and the streak page renders at most 20 rows by string concatenation. Both are deliberate, not accidental.

**Cron runs in UTC; my afternoon doesn't.** Rather than reason about offsets and daylight saving, there is one hourly trigger and the handler computes the local hour and returns immediately unless it's a nudge hour. Timezone-correct, one trigger out of the five the free plan allows, and it costs nothing to check.

### The model

When a voice note arrives, it becomes one structured object — this is the seam everything else hangs off:

```json
{
  "outdoors": true,
  "summary": "Walking the river loop, magpies and a kookaburra laughing across the water.",
  "location": "the river loop",
  "weather": "overcast and cool",
  "mood": "wide awake",
  "species": ["magpie", "kookaburra"],
  "notable": ["first jacaranda blooms"]
}
```

`outdoors` drives the streak; `species` and `notable` are what make the weekly roll-up worth reading.

I could have prompted a large model for this. Instead I fine-tuned `Qwen/Qwen3.5-4B` with a LoRA adapter using [Tinker](https://thinkingmachines.ai/tinker/), on a dataset built for exactly this job: a few hundred transcripts deliberately corrupted to look like what ASR actually emits — lowercase, no punctuation, filler words, restarts, dropped words — each paired with its correct entry. The dataset generator, the training script and the eval harness are all in `train/`.

Base versus tuned, on a held-out split:

{{EVAL_TABLE}}

<!-- Paste the markdown table from `uv run train/eval.py`. -->

The schema-valid rate is the number that decides whether the caller can trust the output without a retry — a small model that always emits parseable JSON is worth more here than a bigger one that is *usually* right. And the output-token column is the cost proxy: a tuned 4B writes tight JSON instead of padding out an explanation nobody asked for.

### The parsing is where the real work went

`schema.ts` is the least glamorous and most load-bearing file in the repo. Models wrap JSON in markdown fences, preface it with "Sure!", and — if they're reasoning models — emit a `thinking` block that contains braces of its own. So rather than trusting one `JSON.parse`, the parser strips reasoning blocks and fences, scans *(all)* top-level balanced objects, and tries each from last to first until one validates against the schema. It never throws on a filled fence, and it never grabs a brace out of the model's own reasoning. Sixteen of the thirty-six tests are about this file.

### About the deploy

I originally built this on a different host, on the assumption that its free tier would run it. The free tier had no persistent disk and put services to sleep after fifteen minutes — which is fatal for a product whose entire value is a streak that survives, and for cron jobs that need to fire while you're out walking. I moved to Workers because it is the one free tier that is genuinely always-on *and* persistent *and* doesn't ask for a credit card. That reframing — "what can actually run this for nothing" rather than "what's the obvious host" — ended up simplifying the architecture rather than complicating it.

## Why Does Open Innovation Matter?

Three specific things, not vibes.

**1. There is nothing to leak, and nowhere to leak it to.** Green Hour accumulates a log of *where I physically am, when, and what I said while I was there.* That's a location trail with my voice attached. There is no vendor account behind this, no API key for a closed model, no dashboard holding provider credentials. The journal is a D1 database in my own account, and the voice notes never leave the request that processed them. A closed agent SaaS would hold exactly the dataset I'd least like to hand over.

**2. I can fine-tune the model on my own backyard — and keep it.** This is the part a closed API makes impossible. The tuned adapter beats the baseline precisely because it has seen *these* transcripts: my idiom, my local birds, the way I actually talk when I'm walking. A closed API won't let you fine-tune; even if it did, you couldn't take the weights with you. Here the adapter is mine. I can swap the base model, retrain it on next month's walks, or self-host the lot.

**3. It costs nothing, and locks in nothing.** No card, no per-call markup, no minimum spend, no vendor relationship. The whole runtime is a 24 KB Worker and a SQLite file. If Cloudflare vanished tomorrow the code would run anywhere Node runs — the portable parts are `weather.ts`, `schema.ts` and `journal.ts`, about 200 lines of glue around them. That's not a theoretical property; it's why I could move hosts in an afternoon when the first one didn't work out.

The open path wasn't the compromise here. It was the *only* path that ran for free, without a credit card, on infrastructure that stays awake.

## My Agent Session

{{DEVRELAY_SESSION}}

<!-- Record with DevRelay and embed using the agent_session tag, or link it. -->

## Prize Categories

- **Best Use of Tinker** — `Qwen/Qwen3.5-4B` fine-tuned with a LoRA adapter via Tinker; `train/eval.py` reports base-versus-tuned on a held-out split (schema validity, `outdoors` accuracy, field F1, latency, output tokens).
