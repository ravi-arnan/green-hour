# Setup runbook

Everything in the repo is built. What's left needs *your* accounts. This is
the order that avoids rework.

## 0. Prerequisites

- A Render account (the Hermes image needs the **standard** plan, ~$25/mo — the
  free plan cannot hold it).
- A Telegram account.
- A GitHub account (for the repo and for publishing the streak snapshot).

## 1. Claim the partner credits first

Do this before creating anything paid.

```bash
curl -fsSL https://devrelay.com/install.sh | sh
```

Restart your coding agent so it picks up DevRelay, then sign in with MLH and
link your DEV account. Ask the agent:

> What sponsor offers can I claim for Hacktoberfest?

DevRelay exposes the offers as an MCP tool (`list_event_offers`) and will claim
the Render / Tinker / Backboard / ElevenLabs credits with your OK. Confirm each
one actually landed before you depend on it.

## 2. Telegram bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
   (`TELEGRAM_BOT_TOKEN`).
2. Message [@userinfobot](https://t.me/userinfobot) → copy your numeric id
   (`TELEGRAM_ALLOWED_USER_ID`). This keeps the agent from answering strangers.

## 3. Model access

- **OpenRouter** — create a key at [openrouter.ai/keys](https://openrouter.ai/keys)
  (`OPENROUTER_API_KEY`). Free open-weight models are enough to run the agent
  and to serve as the baseline in `eval.py`.
- **Groq** — create a key at [console.groq.com](https://console.groq.com)
  (`GROQ_API_KEY`). This hosts the open-weight Whisper model used for
  transcription.
- **Tinker** — create a key at
  [tinker.thinkingmachines.ai/keys](https://tinker.thinkingmachines.ai/keys)
  and set up billing (`TINKER_API_KEY`). Training fails without it.

## 4. Fine-tune (before or after deploying — the agent falls back either way)

```bash
uv run --no-project --python 3.12 --with-requirements train/requirements.txt \
    train/build_dataset.py --n 500
uv run --no-project --python 3.12 --with-requirements train/requirements.txt \
    train/train_tinker.py --base-model Qwen/Qwen3.5-4B --rank 16 --steps 300
```

Copy the printed `TINKER_MODEL_PATH` — that goes in the Render env vars below.

Then produce the table for the post:

```bash
uv run --no-project --python 3.12 --with-requirements train/requirements.txt \
    train/eval.py
```

## 5. Deploy on Render

1. Push this repo to GitHub.
2. Render → **New → Blueprint** → select the repo. It reads `render.yaml` and
   creates the `hermes` web service (with a 5 GB disk) and the
   `green-hour-streak` static site.
3. Wait for the first build (~3–5 min; it pulls the Hermes image).
4. Open the service URL. You should see the Hermes dashboard.

## 6. Configure the agent

In Render → your `hermes` service → **Environment**, set the `sync: false`
values from `.env.example`:

| Variable | Value |
|---|---|
| `GREENHOUR_LAT`, `GREENHOUR_LON`, `GREENHOUR_TZ` | your home coordinates |
| `OPENROUTER_API_KEY` | step 3 |
| `GROQ_API_KEY` | step 3 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID` | step 2 |
| `TINKER_API_KEY`, `TINKER_MODEL_PATH` | step 4 (optional but recommended) |
| `GITHUB_TOKEN`, `GITHUB_REPO` | optional; needed for `--publish` |
| `RENDER_MCP_API_KEY` | optional; use a **least-privileged** key |

Then, from the Hermes dashboard chat, ask it to confirm the setup:

> What model are you running on, and are the Render tools available?

### Lock the dashboard before you paste any keys

Hermes' dashboard has **no authentication** — anyone who reaches the URL can
read your provider keys and chat with the agent. Put an auth gateway or a
private network (e.g. Tailscale) in front of it, or accept the risk only for a
throwaway demo with low-privilege keys. Do not skip this.

## 7. Schedule the loop

From the Hermes dashboard's cron surface, create three jobs (the exact schedule
syntax lives in the Cron tab — use a five-field schedule):

| when | prompt |
|---|---|
| 07:30 daily | `Run the green-hour-nudge skill and send me the line it prints, verbatim.` |
| 16:00 daily | `Run the green-hour-nudge skill and send me the line it prints, verbatim.` |
| Mon 09:00 | `Run the grass-report skill and send me the weekly summary.` |

## 8. Verify end to end

1. Trigger the nudge job manually — the line should arrive in Telegram.
2. Go outside and send the bot a voice note.
3. You should get the "Logged walk … Streak: 1 day(s)" reply.
4. Send something plainly indoors — it should *not* count.
5. `grass-report --publish` (or let Monday's job run) and check the streak page.

## 9. Publish the DEV post

`docs/DEV_POST.md` is the draft. Fill the placeholders — repo URL, demo URL, the
`eval.py` table, and the DevRelay session embed — then publish with the tags
`devchallenge, hf26challenge`. **Deadline: 11 October.**
