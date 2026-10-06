/**
 * Worker bindings and configuration.
 *
 * Secrets (set with `wrangler secret put`) are marked; everything else lives
 * in wrangler.toml under [vars] and is not sensitive.
 */
export interface Env {
  // Bindings
  DB: D1Database;
  AI: Ai;

  // Secrets
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_WEBHOOK_SECRET: string;
  TELEGRAM_ALLOWED_USER_ID: string;

  // Vars
  GREENHOUR_LAT: string;
  GREENHOUR_LON: string;
  GREENHOUR_TZ: string;
  /** Comma-separated local hours to nudge at, e.g. "7,16". */
  GREENHOUR_NUDGE_HOURS: string;
  /** Workers AI model used for extraction. */
  GREENHOUR_MODEL?: string;
}

export const DEFAULT_MODEL = "@cf/qwen/qwen3-30b-a3b-fp8";
export const WHISPER_MODEL = "@cf/openai/whisper-large-v3-turbo";

export function nudgeHours(env: Env): number[] {
  return (env.GREENHOUR_NUDGE_HOURS || "")
    .split(",")
    .map((h) => Number.parseInt(h.trim(), 10))
    .filter((h) => Number.isInteger(h) && h >= 0 && h <= 23);
}
