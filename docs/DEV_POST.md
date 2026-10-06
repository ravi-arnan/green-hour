---
title: "I built an agent that nags me to go outside, then writes my field notes for me"
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)*

<!--
DRAFT. Before publishing, replace:
  - {{DEMO_URL}} (and the /streak link below it)
  - {{DEVRELAY_SESSION}}
  - {{EVAL_TABLE}} with the real output of `train/eval.py`
  - {{STREAK}} with the real number when you post
-->

## What I Built

**Green Hour** is an agent that gets me off the screen and outside — and then gets out of the way.

It lives in Telegram. Twice a day it checks the local forecast, picks the best window, and sends me one line:

> 🌿 15 °C, mostly clear, 0% rain — clearest window is 16:00–17:00. Go find some grass.

I go. While I'm out, I send it a five-second voice note — whatever I'm seeing, hearing, breathing. That's the entire interaction. No app to open, no form, no fields. Then it writes the entry for me:

> Walking the river loop, with magpie, kookaburra about, noticed the first jacaranda blooms. Streak: 4 days.

That's the whole idea: **the screen should be the shortest part of going outside.** Most "get healthy" apps fail because they make you sit down and log the thing you just left the house to avoid. Green Hour is a chat message and a voice memo.

## Demo

{{DEMO_URL}}

<!-- Show: (1) a nudge arriving, (2) a voice note being sent, (3) the reply with the streak.
     Screenshots of the Telegram thread are the most honest demo here — the whole
     point is how little interface there is. -->

The public streak page: {{DEMO_URL}}/streak

## Code

https://github.com/ravi-arnan/green-hour

## How I Built It

Green Hour is [Hermes Agent](https://github.com/NousResearch/hermes-agent) — Nous Research's open-source (MIT) agent framework — running as a Docker web service on [Render](https://render.com), with a small open-weight model I fine-tuned myself.

**The harness.** Hermes gave me persistent memory, cron scheduling, and a Telegram gateway for free. That matters more than it sounds: the "nudge you twice a day and remember your streak" loop is *stateful*, and most weekend agents are stateless. Hermes keeps its memory, skills, and cron jobs on a persistent disk, so the agent actually accumulates a relationship with you over a week rather than starting fresh every message.

**The brain.** The interesting part is the extractor. When a voice note arrives, it becomes one structured object:

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

That's it. `outdoors` drives the streak, `species` and `notable` make the weekly report worth reading.

I could have prompted a big model to do this. Instead I fine-tuned `Qwen/Qwen3.5-4B` with a LoRA adapter using [Tinker](https://thinkingmachines.ai/tinker/), on a dataset built for exactly this job: a few hundred transcripts corrupted to look like what ASR actually produces — lowercase, no punctuation, filler words, restarts, dropped words — each paired with its correct entry. The training script, the dataset generator, and the eval harness are all in the repo.

**The numbers.** Here is the base model versus the tuned adapter on a held-out split, measuring schema validity, the `outdoors` verdict, set-overlap F1 on the interesting fields, latency, and output size:

{{EVAL_TABLE}}

<!-- Paste the markdown table from `uv run train/eval.py` here. -->

Two things worth reading off it. The schema-valid rate is the one that decides whether the caller can trust the output without a retry — a small model that always emits parseable JSON is worth more here than a bigger model that is *usually* right. And the output-token column is a cost proxy: a tuned 4B writes tight JSON instead of padding out an explanation nobody asked for.

**The fallback that makes it shippable.** The extractor has two backends behind one function. If the tuned adapter is configured and reachable it's used; otherwise it falls back to a hosted model. That's not just belt-and-braces — it meant I could ship a working agent *before* the fine-tune existed, then swap the brain in underneath it. Same interface, better model.

**The nudge** is deliberately boring. It calls [Open-Meteo](https://open-meteo.com), which is free, keyless, and open, scores each daylight hour on rain, temperature, and wind, and picks the best one. About forty lines you can audit in ten seconds — which is rather the point.

## Why Does Open Innovation Matter?

Three specific things, not vibes.

**1. The most sensitive log I own stays mine.** Green Hour accumulates a record of *where I physically am, when, and what I said while I was there*. That's a location trail with my voice attached. Hermes is MIT-licensed and self-hosted on my own Render account, so the nudges, the transcripts, and the entries sit on a disk I control. A closed agent SaaS would hold the one dataset I'd least like to hand over.

**2. I can fine-tune the model on my own backyard — and keep it.** This is the part a closed API makes impossible. The whole reason the tuned model beats the baseline is that it's been trained on *these* transcripts: my idiom, my local birds, the way I actually talk when I'm walking. A closed API won't let you fine-tune, and even if it did, you couldn't take the weights with you. Here the adapter is mine. I can swap Qwen for Llama, self-host it entirely, or fine-tune it further on next month's walks.

**3. The behaviour is editable by me, in text.** The agent's actual behaviour — when it nudges, what it says, what counts as a walk — lives in three `SKILL.md` files in my repo. When I want the nudge to be gentler, or to stop counting rainy walks, I edit a Markdown file. No vendor release notes, no waiting.

And the boring one: it costs about $26/month to run, and no per-call markup on the reasoning. The open path wasn't the compromise here. It was the better engineering.

## My Agent Session

{{DEVRELAY_SESSION}}

<!-- Record with DevRelay and embed using the agent_session tag, or link it. -->

## Prize Categories

- **Best Use of Render** — Hermes runs as a Docker web service on Render, with a persistent disk for the journal and skill state.
- **Best Use of Tinker** — `Qwen/Qwen3.5-4B` fine-tuned with a LoRA adapter via Tinker; `train/eval.py` reports base-versus-tuned on a held-out split.
