import { describe, expect, it } from "vitest";

import {
  bestWindow,
  describeCode,
  localNowISO,
  nudgeMessage,
  scoreHour,
  type HourlyPayload,
  type Window,
} from "../src/weather";

interface Row {
  time: string;
  temp?: number;
  precip?: number;
  code?: number;
  wind?: number;
  isDay?: number;
}

function payload(rows: Row[]): HourlyPayload {
  return {
    time: rows.map((r) => r.time),
    temperature_2m: rows.map((r) => r.temp ?? 20),
    precipitation_probability: rows.map((r) => r.precip ?? 0),
    weather_code: rows.map((r) => r.code ?? 1),
    wind_speed_10m: rows.map((r) => r.wind ?? 5),
    is_day: rows.map((r) => r.isDay ?? 1),
  };
}

const NOW = "2026-10-06T10:00";

describe("describeCode", () => {
  it("names known WMO codes", () => {
    expect(describeCode(0)).toBe("clear");
    expect(describeCode(61)).toBe("light rain");
  });

  it("falls back for unknown codes", () => {
    expect(describeCode(9999)).toBe("weather code 9999");
    expect(describeCode(null)).toBe("unknown");
  });
});

describe("bestWindow", () => {
  it("picks the most comfortable hour", () => {
    const window = bestWindow(
      payload([
        { time: "2026-10-06T10:00", temp: 8, precip: 60, wind: 30 },
        { time: "2026-10-06T12:00", temp: 21, precip: 0, wind: 4 },
        { time: "2026-10-06T14:00", temp: 30, precip: 0, wind: 4 },
      ]),
      NOW,
    );
    expect(window).not.toBeNull();
    expect(window!.start).toBe("2026-10-06T12:00");
    expect(window!.tempC).toBe(21);
  });

  it("skips rainy and night hours", () => {
    const window = bestWindow(
      payload([
        { time: "2026-10-06T11:00", precip: 90 },
        { time: "2026-10-06T12:00", isDay: 0 },
      ]),
      NOW,
    );
    expect(window).toBeNull();
  });

  it("ignores hours already past", () => {
    const window = bestWindow(
      payload([
        { time: "2026-10-06T08:00", temp: 21 },
        { time: "2026-10-06T11:00", temp: 30 },
      ]),
      NOW,
    );
    expect(window!.start).toBe("2026-10-06T11:00");
  });

  it("respects the horizon", () => {
    const window = bestWindow(
      payload([
        { time: "2026-10-06T11:00", temp: 30 },
        { time: "2026-10-06T19:00", temp: 21 },
      ]),
      NOW,
      4,
    );
    expect(window!.start).toBe("2026-10-06T11:00");
  });

  it("returns null for an empty payload", () => {
    expect(bestWindow({ ...payload([]), time: [] }, NOW)).toBeNull();
  });
});

describe("scoreHour", () => {
  it("prefers dry, comfortable and calm", () => {
    expect(scoreHour(21, 0, 5)).toBeGreaterThan(scoreHour(8, 50, 30));
  });
});

describe("localNowISO", () => {
  it("formats the wall clock in the requested zone", () => {
    const at = new Date("2026-10-06T10:30:00Z");
    expect(localNowISO("UTC", at)).toBe("2026-10-06T10:30");
    expect(localNowISO("Australia/Sydney", at)).toBe("2026-10-06T21:30");
  });
});

describe("nudgeMessage", () => {
  it("is a single line naming the window", () => {
    const window: Window = {
      start: "2026-10-06T16:00",
      end: "2026-10-06T17:00",
      label: "16:00–17:00",
      tempC: 19.4,
      precipProb: 10,
      windKmh: 8,
      code: 2,
      score: 0,
    };
    const message = nudgeMessage(window);
    expect(message).not.toContain("\n");
    expect(message).toContain("16:00–17:00");
    expect(message).toContain("19 °C");
    expect(message).toContain("partly cloudy");
  });
});
