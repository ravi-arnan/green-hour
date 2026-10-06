/**
 * Green Hour — a Cloudflare Worker that gets you outside.
 *
 *   POST /telegram/<secret>   Telegram webhook → log a walk
 *   GET  /                    public streak page (server-rendered from D1)
 *   GET  /health              config check
 *   scheduled (hourly cron)   the nudge
 *
 * Everything is I/O-bound (Telegram, Open-Meteo, Workers AI, D1), which is what
 * keeps the handlers inside the free plan's 10 ms CPU budget.
 */

import { WHISPER_MODEL, nudgeHours, type Env } from "./env";
import { extract } from "./extract";
import { insertEntry, recent, streak, totals, weeklyStats } from "./journal";
import { renderPage } from "./page";
import { attachmentOf, downloadFile, getFilePath, sendMessage, type TgMessage, type TgUpdate } from "./telegram";
import { bestWindow, fetchHourly, localNowISO, noWindowMessage, nudgeMessage } from "./weather";

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

// --------------------------------------------------------------- the nudge

async function runNudge(env: Env): Promise<void> {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_ALLOWED_USER_ID) return;

  const nowLocal = localNowISO(env.GREENHOUR_TZ);
  const localHour = Number.parseInt(nowLocal.slice(11, 13), 10);
  if (!nudgeHours(env).includes(localHour)) return; // not a nudge hour locally

  let text: string;
  try {
    const hourly = await fetchHourly(env.GREENHOUR_LAT, env.GREENHOUR_LON, env.GREENHOUR_TZ);
    const window = bestWindow(hourly, nowLocal);
    text = window ? nudgeMessage(window) : noWindowMessage();
  } catch (err) {
    console.error("nudge: forecast failed", err);
    return;
  }

  await sendMessage(env.TELEGRAM_BOT_TOKEN, env.TELEGRAM_ALLOWED_USER_ID, text);
}

// ------------------------------------------------------------ logging a walk

async function transcribe(env: Env, buffer: ArrayBuffer): Promise<string> {
  const output = (await env.AI.run(WHISPER_MODEL as never, {
    audio: [...new Uint8Array(buffer)],
  } as never)) as { text?: string };
  return (output.text ?? "").trim();
}

async function logWalk(env: Env, message: TgMessage): Promise<void> {
  const chatId = message.chat.id;
  const attachment = attachmentOf(message);

  let transcript = (message.text ?? "").trim();
  if (!transcript && attachment) {
    const path = await getFilePath(env.TELEGRAM_BOT_TOKEN, attachment.file_id);
    transcript = await transcribe(env, await downloadFile(env.TELEGRAM_BOT_TOKEN, path));
  }

  if (!transcript) {
    await sendMessage(env.TELEGRAM_BOT_TOKEN, chatId, "I couldn't hear anything in that one.");
    return;
  }

  const { entry, model } = await extract(env.AI, transcript, env.GREENHOUR_MODEL);
  await insertEntry(env.DB, entry, {
    tz: env.GREENHOUR_TZ,
    transcript,
    source: attachment ? "voice" : "text",
    model,
  });

  const days = await streak(env.DB, env.GREENHOUR_TZ);
  const heard = [entry.summary, entry.species.length ? `· ${entry.species.join(", ")}` : ""]
    .filter(Boolean)
    .join(" ");

  const reply = entry.outdoors
    ? `Logged walk — "${heard}". Streak: ${days} day${days === 1 ? "" : "s"}. 🌿`
    : `That one sounded indoors, so it isn't counting toward your streak. (I heard: "${heard}")`;

  await sendMessage(env.TELEGRAM_BOT_TOKEN, chatId, reply);
}

// ----------------------------------------------------------------- handlers

async function handleWebhook(request: Request, env: Env, ctx: ExecutionContext, secret: string): Promise<Response> {
  if (secret !== env.TELEGRAM_WEBHOOK_SECRET) return new Response("forbidden", { status: 403 });
  if (request.method !== "POST") return new Response("method not allowed", { status: 405 });

  let update: TgUpdate;
  try {
    update = (await request.json()) as TgUpdate;
  } catch {
    return json({ ok: true }); // malformed; swallow rather than make Telegram retry
  }

  const message = update.message ?? update.edited_message;
  if (!message) return json({ ok: true });
  if (String(message.from?.id ?? "") !== env.TELEGRAM_ALLOWED_USER_ID) return json({ ok: true });

  // Answer Telegram immediately; do the slow work (Whisper, model) afterwards.
  ctx.waitUntil(
    logWalk(env, message).catch(async (err) => {
      console.error("logWalk failed", err);
      try {
        await sendMessage(env.TELEGRAM_BOT_TOKEN, message.chat.id, "Something went wrong logging that one.");
      } catch {
        /* nothing more we can do */
      }
    }),
  );
  return json({ ok: true });
}

async function handlePage(env: Env): Promise<Response> {
  const [days, week, total, entries] = await Promise.all([
    streak(env.DB, env.GREENHOUR_TZ),
    weeklyStats(env.DB, env.GREENHOUR_TZ),
    totals(env.DB),
    recent(env.DB, 20),
  ]);
  const html = renderPage({
    streak: days,
    week,
    totals: total,
    entries,
    generatedAt: new Date().toISOString(),
  });
  return new Response(html, {
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=60" },
  });
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return json({
        ok: true,
        config: {
          telegram: Boolean(env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_ALLOWED_USER_ID),
          location: Boolean(env.GREENHOUR_LAT && env.GREENHOUR_LON),
          timezone: env.GREENHOUR_TZ ?? null,
          nudgeHours: nudgeHours(env),
          model: env.GREENHOUR_MODEL ?? null,
        },
      });
    }

    if (url.pathname.startsWith("/telegram/")) {
      return handleWebhook(request, env, ctx, url.pathname.slice("/telegram/".length));
    }

    if (request.method === "GET" && url.pathname === "/") return handlePage(env);

    return new Response("not found", { status: 404 });
  },

  async scheduled(_controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runNudge(env));
  },
} satisfies ExportedHandler<Env>;
