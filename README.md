# Green Hour

An open-source agent that gets you **off the screen and outside** — then turns the walk into a field journal.

Green Hour is a [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research, MIT) deployed on [Render](https://render.com), with a small open-weight model that we fine-tune ourselves via [Tinker](https://thinkingmachines.ai/tinker/). You talk to it on Telegram. It nudges you out the door, you send a five-second voice note from the trail, and it writes the entry for you.

The screen is the shortest part of the experience. That's the point.

> Built for the DEV Challenge — *Hacktoberfest Open-Source AI, Week 1: Touch Grass*.

## How it works

```
   you ──Telegram──► Hermes gateway (Render, Docker, persistent disk)
                        │
                        ├── cron: green-hour-nudge ──► Open-Meteo (open data)
                        │        "19 °C, clear — best window 16:00–17:00. Go."
                        │
                        ├── skill: log-outside
                        │        voice note ─► Whisper large-v3 (open weights)
                        │                   ─► Qwen3.5-4B + our LoRA (Tinker)
                        │                   ─► journal entry + streak
                        │
                        └── skill: grass-report ──► weekly summary
```

1. **Nudge.** Twice a day the agent pulls the local forecast from Open-Meteo, picks the best outdoor window, and messages you a single line.
2. **Walk.** You go outside. No app to open, no form to fill.
3. **Log.** You send a five-second voice note. The agent transcribes it, decides whether you were actually outdoors, pulls out what you noticed, appends to your journal, and updates your streak.
4. **Report.** Weekly, it summarises the week back to you.

## The models

| Component | What it is | Why |
|---|---|---|
| `Qwen/Qwen3.5-4B` + LoRA | Open-weight LLM, fine-tuned via Tinker on our own field notes | Turns a messy transcript into a structured entry, in a naturalist's voice |
| Whisper `large-v3` | Open-weight ASR (hosted) | Transcription |
| Hermes Agent | Open-source agent harness (MIT) | The always-on brain: memory, cron, Telegram gateway |

We deliberately run **no local inference** — everything is cloud-hosted — while keeping the *pieces* open. See [Why open innovation matters](#why-open-innovation-matters).

## Repo layout

```
green-hour/
├── Dockerfile                  # Hermes image + our skills layer
├── render.yaml                 # Render Blueprint (web service + disk + static site)
├── scripts/                    # boot-time config patch
├── skills/                     # the actual product
│   ├── green-hour-nudge/       # cron nudge from Open-Meteo
│   ├── log-outside/            # voice note → journal
│   └── grass-report/           # weekly summary
├── train/                      # Tinker dataset + fine-tune + eval
└── web/                         # public streak page (static)
```

## Deploy

Two ways, both on Render:

1. **Blueprint** — point Render at this repo (`New → Blueprint`). It builds the `Dockerfile`, mounts a 5 GB disk at `/opt/data`, and provisions the static streak page.
2. **Manual** — build the image, run it as a Docker web service with `HERMES_DASHBOARD=1`.

Then, from the Hermes dashboard: add your LLM provider key, set the model, and paste your `TELEGRAM_BOT_TOKEN`.

> **Lock the dashboard down.** Hermes' dashboard ships without authentication and can read your provider keys. Put an auth gateway or a private network (e.g. Tailscale) in front of it before you paste anything sensitive, and use a least-privileged Render key.

## Fine-tuning

```bash
uv run train/build_dataset.py     # → train/data/{train,eval}.jsonl
uv run train/train_tinker.py      # LoRA SFT, Qwen3.5-4B, rank 16
uv run train/eval.py              # base vs tuned, prints the results table
```

`eval.py` reports schema-valid rate, field-level F1, indoors/outdoors accuracy, latency and cost for the base model versus our adapter. Those numbers are what the DEV post cites.

## Why open innovation matters

Your outdoor routine is one of the most location-revealing datasets you produce. Three things follow from building on open pieces:

- **You own the runtime.** Hermes is MIT-licensed and self-hosted on your Render account. The nudge schedule, your voice notes, and your location trail stay on infrastructure you control, not a closed agent SaaS.
- **You own the model.** The core extractor is an open-weight Qwen that *you* fine-tuned on your own transcripts. A closed API can't be tuned to your backyard's quirks — and even if it could, you couldn't keep the weights. Here you can swap Qwen for Llama, self-host, or rewrite the agent's behaviour by editing one skill file.
- **It's cheap and portable.** A $26/month box, no per-call markup on the reasoning, and no lock-in on the loop that runs your day.

## License

MIT. See [LICENSE](./LICENSE).
