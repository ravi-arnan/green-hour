/**
 * The nudge: pick the best outdoor window today from open weather data.
 *
 * Port of skills/_lib/greenhour/weather.py. Open-Meteo is free, keyless and
 * open; the scoring is deliberately simple enough to audit at a glance.
 *
 * Time handling: Open-Meteo returns naive local timestamps ("2026-10-07T10:00").
 * We treat those as "pseudo-UTC" (Date.UTC of the wall-clock components) so
 * arithmetic is consistent and no timezone conversion is needed downstream.
 */

const FORECAST_URL = "https://api.open-meteo.com/v1/forecast";

/** WMO weather codes, trimmed to the ones worth naming. */
const WMO: Record<number, string> = {
  0: "clear",
  1: "mostly clear",
  2: "partly cloudy",
  3: "overcast",
  45: "foggy",
  48: "freezing fog",
  51: "light drizzle",
  53: "drizzle",
  55: "heavy drizzle",
  61: "light rain",
  63: "rain",
  65: "heavy rain",
  71: "light snow",
  73: "snow",
  75: "heavy snow",
  80: "rain showers",
  81: "rain showers",
  82: "violent rain showers",
  95: "thunderstorm",
};

export function describeCode(code: number | null | undefined): string {
  if (code == null) return "unknown";
  return WMO[code] ?? `weather code ${code}`;
}

export interface HourlyPayload {
  time: string[];
  temperature_2m: number[];
  precipitation_probability: number[];
  weather_code: number[];
  wind_speed_10m: number[];
  is_day: number[];
}

export interface Window {
  start: string;
  end: string;
  label: string;
  tempC: number;
  precipProb: number;
  windKmh: number;
  code: number;
  score: number;
}

export function naiveToMs(iso: string): number {
  const [datePart, timePart = "00:00"] = iso.split("T");
  const [y, mo, d] = datePart!.split("-").map(Number);
  const [h, mi] = timePart.split(":").map(Number);
  return Date.UTC(y!, (mo ?? 1) - 1, d ?? 1, h ?? 0, mi ?? 0);
}

export function msToNaive(ms: number): string {
  const dt = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    `${dt.getUTCFullYear()}-${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())}` +
    `T${p(dt.getUTCHours())}:${p(dt.getUTCMinutes())}`
  );
}

/** The current wall-clock time in `tz`, as a naive local ISO string. */
export function localNowISO(tz: string, now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00";
  const hour = get("hour") === "24" ? "00" : get("hour");
  return `${get("year")}-${get("month")}-${get("day")}T${hour}:${get("minute")}`;
}

/** Higher is better. Comfort around 21 °C, dry, not windy. */
export function scoreHour(tempC: number, precipProb: number, windKmh: number): number {
  return -3 * precipProb - 2 * Math.abs(tempC - 21) - 1.5 * Math.max(0, windKmh - 20);
}

export function bestWindow(
  hourly: HourlyPayload,
  nowLocal: string,
  horizonHours = 8,
): Window | null {
  const times = hourly.time ?? [];
  if (times.length === 0) return null;

  const currentMs = Math.floor(naiveToMs(nowLocal) / 3_600_000) * 3_600_000;
  const horizonMs = currentMs + horizonHours * 3_600_000;

  let best: Window | null = null;
  for (let i = 0; i < times.length; i++) {
    const slotMs = naiveToMs(times[i]!);
    if (slotMs < currentMs) continue;
    if (slotMs > horizonMs) break;
    if (!hourly.is_day?.[i]) continue;

    const precip = Number(hourly.precipitation_probability?.[i] ?? 0);
    if (precip >= 70) continue;
    const temp = Number(hourly.temperature_2m?.[i] ?? 0);
    const wind = Number(hourly.wind_speed_10m?.[i] ?? 0);
    const code = Number(hourly.weather_code?.[i] ?? 0);
    const score = scoreHour(temp, precip, wind);

    if (best === null || score > best.score) {
      const end = msToNaive(slotMs + 3_600_000);
      best = {
        start: times[i]!,
        end,
        label: `${times[i]!.slice(11, 16)}–${end.slice(11, 16)}`,
        tempC: temp,
        precipProb: Math.round(precip),
        windKmh: wind,
        code,
        score,
      };
    }
  }
  return best;
}

export function nudgeMessage(w: Window): string {
  return (
    `🌿 ${Math.round(w.tempC)} °C, ${describeCode(w.code)}, ` +
    `${w.precipProb}% rain — clearest window is ${w.label}. Go find some grass.`
  );
}

export function noWindowMessage(reason = "nothing dry in the next stretch"): string {
  return `🌧️ No good window today (${reason}). Read a book instead — the grass will wait.`;
}

/** Fetch just the fields we score on, for one day. Keeps the payload small. */
export async function fetchHourly(
  lat: string,
  lon: string,
  tz: string,
): Promise<HourlyPayload> {
  const url = new URL(FORECAST_URL);
  url.searchParams.set("latitude", lat);
  url.searchParams.set("longitude", lon);
  url.searchParams.set(
    "hourly",
    "temperature_2m,precipitation_probability,weather_code,wind_speed_10m,is_day",
  );
  url.searchParams.set("timezone", tz);
  url.searchParams.set("forecast_days", "2");

  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`open-meteo ${res.status}`);
  const data = (await res.json()) as { hourly?: HourlyPayload };
  if (!data.hourly?.time) throw new Error("open-meteo returned no hourly data");
  return data.hourly;
}
