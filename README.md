# Green Hour

An agent that gets you **off the screen and outside** — then writes your field notes for you.

Green Hour is a single [Cloudflare Worker](https://developers.cloudflare.com/workers/) with a D1 database and an hourly cron trigger. It runs entirely on **open-weight models** (Whisper for speech, Qwen for extraction), costs nothing, needs no credit card, and holds no API keys beyond a Telegram bot token. The one model it can't run itself — the extractor we fine-tune — is trained with [Tinker](https://thinkingmachines.ai/tinker/).

You talk to it on Telegram. It nudges you out the door, you send a five-second voice note from the trail, and it writes the entry.

The screen is the shortest part of the experience. That's the point.

> Built for the DEV Challenge — *Hacktoberfest Open-Source AI, Week 1: Touch Grass*.

**Live:** https://green-hour.raviarnankeren.workers.dev — the streak page, server-rendered from the journal.

> Status: deployed and serving. The Telegram webhook and location are not yet
> configured, so `/health` reports `telegram: false, location: false` and the
> journal is empty. See [docs/SETUP.md](./docs/SETUP.md) for the remaining steps.

## How it works

```
Telegram ──webhook──► Worker (fetch)
                        ├─ POST /telegram/<secret>   voice note → journal
                        ├─ GET  /                    public streak page
                        └─ GET  /health

Worker (cron, hourly) ──► nudge → Telegram

Workers AI:  whisper-large-v3-turbo (speech) · qwen3-30b-a3b (extraction)
Storage:     D1 (the journal)
```

1. **Nudge.** On the hour, the Worker checks the local time and, at your chosen hours, pulls the forecast from Open-Meteo and messages you the best window: *"🌿 15 °C, mostly clear, 0% rain — clearest window is 16:00–17:00. Go find some grass."*
2. **Walk.** You go outside. No app to open, no form to fill.
3. **Log.** You send a five-second voice note. It is transcribed with Whisper, turned into a structured entry by Qwen, and appended to the journal. You get back: *"Logged walk — "…". Streak: 4 days. 🌿"*
4. **Report.** The streak page at `/` is server-rendered from the journal.

## Why it's free

| Piece | What it is | Cost |
|---|---|---|
| Worker + Cron | Always-on serverless runtime | 100k req/day free |
| D1 | SQLite journal, persistent | 500 MB free |
| Workers AI | Whisper + Qwen, open weights | 10,000 neurons/day free |

A five-second voice note plus one extraction is roughly **3–5 neurons**. The daily allowance is 10,000. It is not close.

The tight constraint is the free plan's **10 ms CPU per invocation** — which is why the handlers stay strictly I/O-bound and the payloads stay small.

## Repo layout

```
green-hour/
├── worker/                  # the whole runtime
│   ├── src/
│   │   ├── index.ts         # fetch + scheduled entrypoints
│   │   ├── weather.ts       # Open-Meteo → best window
│   │   ├── schema.ts        # FieldEntry + tolerant model-output parsing
│   │   ├── extract.ts       # Workers AI → FieldEntry
│   │   ├── journal.ts       # D1 + pure streak/weekly logic
│   │   ├── telegram.ts      # Bot API helpers
│   │   └── page.ts          # the streak page
│   ├── test/                # vitest
│   ├── schema.sql           # D1 schema
│   └── wrangler.toml
└── train/                   # Tinker fine-tune + base-vs-tuned eval (Python)
```

The Render/Hermes version this replaced is preserved on the `hermes-on-render` branch.

## Deploy

```bash
cd worker
npm install --include=dev
npx wrangler d1 create green-hour          # paste the id into wrangler.toml
npx wrangler d1 execute green-hour --remote --file=./schema.sql
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
npx wrangler secret put TELEGRAM_ALLOWED_USER_ID
npx wrangler deploy
```

Then set `GREENHOUR_LAT`, `GREENHOUR_LON`, `GREENHOUR_TZ` in `wrangler.toml` and point the Telegram webhook at the Worker:

```bash
curl "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -d "url=https://green-hour.raviarnankeren.workers.dev/telegram/$WEBHOOK_SECRET"
```

`docs/SETUP.md` is the full runbook, including the parts only you can do.

## The model

The extractor turns a messy transcript into one structured object:

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

To make a small model good at exactly this job, `train/` builds a dataset of ASR-flavoured transcripts, fine-tunes `Qwen/Qwen3.5-4B` with a LoRA adapter via Tinker, and reports base-versus-tuned:

```bash
uv run --no-project --python 3.12 --with-requirements train/requirements.txt train/build_dataset.py --n 500
uv run --no-project --python 3.12 --with-requirements train/requirements.txt train/train_tinker.py --steps 300
uv run --no-project --python 3.12 --with-requirements train/requirements.txt train/eval.py
```

## Why open innovation matters

Your outdoor routine is the most location-revealing dataset you produce. Three things follow from building the whole thing on open pieces:

- **Nothing to leak, nowhere to leak it to.** There is no vendor account behind this, no API key for a closed model, no dashboard with your provider credentials. The journal is a D1 database in *your* Cloudflare account, and the voice notes never leave the request that processed them. A closed agent SaaS would hold a log of where you physically were, every day.
- **You own the model.** The extractor is an open-weight Qwen. The fine-tuned adapter in `train/` is yours — you can swap the base model, retrain it on next month's walks, or self-host it. A closed API can't be tuned to your own field notes, and even if it could you couldn't keep the weights.
- **It costs nothing and locks you into nothing.** No card, no per-call markup, no minimum. The entire runtime is one 24 KB Worker and a SQLite file. If Cloudflare disappears tomorrow the code runs anywhere Docker or Node runs; the port is `weather.ts`, `schema.ts`, `journal.ts` and about 200 lines of glue.

The open path wasn't the compromise here. It was the only one that ran for free without a credit card.

## Tests

```bash
cd worker && npm test        # 36 tests: parsing, streaks, weather windows
cd worker && npm run typecheck
```

## License

MIT. See [LICENSE](./LICENSE).
