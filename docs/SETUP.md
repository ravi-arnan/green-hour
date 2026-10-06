# Setup runbook

The Worker is already deployed and the database exists. What remains needs your
Telegram account and your location. Written in the order that avoids rework.

## Already done

| Thing | Value |
|---|---|
| Worker | `green-hour` → https://green-hour.raviarnankeren.workers.dev |
| Cron | `0 * * * *` (hourly; the handler decides which local hours to nudge) |
| D1 database | `green-hour` (`5356f4aa-8d25-476b-a061-4215541e85e2`), schema applied |
| Bindings | `DB` (D1), `AI` (Workers AI) |

`GET /health` currently reports `telegram: false, location: false` — that is
correct until you do the steps below.

## 1. Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Message [@userinfobot](https://t.me/userinfobot) → copy your numeric id.
   This is what stops the bot answering anyone else.

## 2. Your location

Set these in `worker/wrangler.toml` under `[vars]`, then redeploy:

```toml
GREENHOUR_LAT = "-33.8688"
GREENHOUR_LON = "151.2093"
GREENHOUR_TZ  = "Australia/Sydney"
```

`GREENHOUR_NUDGE_HOURS` defaults to `7,16` — the local hours you want nudging at.
Cron fires hourly in UTC; the handler converts to your timezone and returns
without doing anything outside those hours.

## 3. Secrets

```bash
cd worker
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_ALLOWED_USER_ID
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET   # any long random string
npx wrangler deploy
```

## 4. Point Telegram at the Worker

The webhook path carries the secret, so a stranger POSTing to it is rejected
with 403.

```bash
TOKEN=...                 # from BotFather
SECRET=...                # the same value as TELEGRAM_WEBHOOK_SECRET
curl "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -d "url=https://green-hour.raviarnankeren.workers.dev/telegram/$SECRET"
```

Check it took:

```bash
curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

## 5. Verify end to end

1. `curl https://green-hour.raviarnankeren.workers.dev/health` → `telegram: true, location: true`.
2. Trigger the nudge without waiting for the hour — set `GREENHOUR_NUDGE_HOURS`
   to the current local hour, redeploy, and wait for the next hour boundary
   (cron propagation can take up to 15 minutes after a change).
   `npx wrangler tail` shows the invocation.
3. Go outside and send the bot a voice note. Expect
   `Logged walk — "…". Streak: 1 day. 🌿`
4. Send something plainly indoors ("I'm at my desk, the fan is humming") →
   it should reply that it isn't counting, and the streak should not move.
5. Open https://green-hour.raviarnankeren.workers.dev/ — the entry should appear.

While testing, watch the **CPU time** in `wrangler tail`. The free plan allows
10 ms per invocation and this design is meant to sit well inside it. If a
handler starts reporting `exceededCpu`, the first thing to trim is the
Open-Meteo payload in `fetchHourly`.

## 6. Fine-tune (optional, but it's the Tinker prize category)

```bash
uv run --no-project --python 3.12 --with-requirements train/requirements.txt train/build_dataset.py --n 500
uv run --no-project --python 3.12 --with-requirements train/requirements.txt train/train_tinker.py --steps 300
uv run --no-project --python 3.12 --with-requirements train/requirements.txt train/eval.py
```

Paste `eval.py`'s table into the post.

## 7. Publish the DEV post

`docs/DEV_POST.md` is the draft. The repo and demo URLs are already filled in;
what remains is the `{{EVAL_TABLE}}` from step 6 and the `{{DEVRELAY_SESSION}}`
embed. Publish with the tags `devchallenge, hf26challenge`.
**Deadline: 11 October.**
