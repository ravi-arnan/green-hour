/**
 * The journal, on Cloudflare D1.
 *
 * Port of skills/_lib/greenhour/journal.py. The interesting logic (streaks,
 * weekly roll-ups) is pure and unit-tested; the D1 calls around it are thin.
 */

import type { FieldEntry } from "./schema";
import { localNowISO } from "./weather";

export interface EntryRow {
  id: number;
  created_at: string;
  local_date: string;
  outdoors: number;
  summary: string;
  location: string | null;
  weather: string | null;
  mood: string | null;
  notable: string;
  species: string;
  transcript: string | null;
  source: string;
  model: string | null;
}

export interface Entry {
  id: number;
  createdAt: string;
  localDate: string;
  outdoors: boolean;
  summary: string;
  location: string | null;
  weather: string | null;
  mood: string | null;
  notable: string[];
  species: string[];
  source: string;
}

// ---------------------------------------------------------------- pure logic

/** Add (or subtract) whole days to a `YYYY-MM-DD` string, UTC-safe. */
export function addDaysISO(iso: string, delta: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const ms = Date.UTC(y!, (m ?? 1) - 1, d ?? 1) + delta * 86_400_000;
  const dt = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getUTCFullYear()}-${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())}`;
}

/**
 * Consecutive days ending today (or yesterday, so an evening walker doesn't
 * watch the streak reset at midnight).
 */
export function computeStreak(days: Set<string>, todayISO: string): number {
  if (days.size === 0) return 0;
  let cursor = days.has(todayISO) ? todayISO : addDaysISO(todayISO, -1);
  let count = 0;
  while (days.has(cursor)) {
    count++;
    cursor = addDaysISO(cursor, -1);
  }
  return count;
}

export function topCounts(values: string[], limit = 5): { name: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

export interface WeekStats {
  start: string;
  end: string;
  daysOut: number;
  walks: number;
  species: { name: string; count: number }[];
  notable: { name: string; count: number }[];
}

export function summarizeWeek(entries: Entry[], startISO: string, endISO: string): WeekStats {
  const outdoors = entries.filter((e) => e.outdoors);
  return {
    start: startISO,
    end: endISO,
    daysOut: new Set(outdoors.map((e) => e.localDate)).size,
    walks: outdoors.length,
    species: topCounts(outdoors.flatMap((e) => e.species)),
    notable: topCounts(outdoors.flatMap((e) => e.notable)),
  };
}

export function parseRow(row: EntryRow): Entry {
  return {
    id: row.id,
    createdAt: row.created_at,
    localDate: row.local_date,
    outdoors: Boolean(row.outdoors),
    summary: row.summary,
    location: row.location,
    weather: row.weather,
    mood: row.mood,
    notable: safeParseArray(row.notable),
    species: safeParseArray(row.species),
    source: row.source,
  };
}

function safeParseArray(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

// -------------------------------------------------------------- D1 wrappers

export async function insertEntry(
  db: D1Database,
  entry: FieldEntry,
  opts: { tz: string; transcript?: string | null; source?: string; model?: string | null },
): Promise<number> {
  const now = new Date();
  const localISO = localNowISO(opts.tz, now);
  const result = await db
    .prepare(
      `INSERT INTO entries
         (created_at, local_date, outdoors, summary, location, weather, mood,
          notable, species, transcript, source, model)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      now.toISOString(),
      localISO.slice(0, 10),
      entry.outdoors ? 1 : 0,
      entry.summary,
      entry.location,
      entry.weather,
      entry.mood,
      JSON.stringify(entry.notable),
      JSON.stringify(entry.species),
      opts.transcript ?? null,
      opts.source ?? "voice",
      opts.model ?? null,
    )
    .run();
  return Number(result.meta.last_row_id ?? 0);
}

export async function recent(db: D1Database, limit = 20): Promise<Entry[]> {
  const { results } = await db
    .prepare("SELECT * FROM entries ORDER BY id DESC LIMIT ?")
    .bind(limit)
    .all<EntryRow>();
  return (results ?? []).map(parseRow);
}

export async function outdoorDates(db: D1Database): Promise<Set<string>> {
  const { results } = await db
    .prepare("SELECT DISTINCT local_date FROM entries WHERE outdoors = 1")
    .all<{ local_date: string }>();
  return new Set((results ?? []).map((r) => r.local_date));
}

export async function entriesSince(db: D1Database, startISO: string): Promise<Entry[]> {
  const { results } = await db
    .prepare("SELECT * FROM entries WHERE local_date >= ? ORDER BY id ASC")
    .bind(startISO)
    .all<EntryRow>();
  return (results ?? []).map(parseRow);
}

export async function streak(db: D1Database, tz: string): Promise<number> {
  const days = await outdoorDates(db);
  return computeStreak(days, localNowISO(tz).slice(0, 10));
}

export async function weeklyStats(db: D1Database, tz: string, days = 7): Promise<WeekStats> {
  const end = localNowISO(tz).slice(0, 10);
  const start = addDaysISO(end, -(days - 1));
  return summarizeWeek(await entriesSince(db, start), start, end);
}

export async function totals(db: D1Database): Promise<{ walks: number; daysOut: number }> {
  const row = await db
    .prepare("SELECT COUNT(*) AS walks, COUNT(DISTINCT local_date) AS days FROM entries WHERE outdoors = 1")
    .first<{ walks: number; days: number }>();
  return { walks: Number(row?.walks ?? 0), daysOut: Number(row?.days ?? 0) };
}
